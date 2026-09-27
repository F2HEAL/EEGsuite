"""
psd_contrast_peak_finder.py - Advanced Peak Detection for Tactile EEG

Performs high-resolution PSD analysis on the contrast between FOT and IFNFN
conditions, specifically targeting the steady-state stimulation period.
Implements robust preprocessing (PREP) and automatic harmonic peak detection.

Mathematical Pipeline:
    1. Robust PREP Preprocessing (RANSAC + Average Ref)
    2. Epoching with 500ms safety margin (analyzes 0.5s to 5.0s)
    3. Baseline Normalization (dB ratio vs pre-stim rest)
    4. Condition Contrasting (FOT_dB - IFNFN_dB)
    5. Peak Detection & SNR Calculation at Stim Freq + Harmonics
"""

import logging
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import mne
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from pyprep.prep_pipeline import PrepPipeline

# ============================================================================
# CONSTANTS & CONFIG
# ============================================================================
RANDOM_SEED: int = 42

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("PeakFinder")

@dataclass
class PeakFinderConfig:
    """Configuration for high-resolution PSD contrast peak detection."""

    # --- Time Windows (seconds) ---
    epoch_tmin: float = -1.5
    epoch_tmax: float = 5.5
    baseline_tmin: float = -1.0
    baseline_tmax: float = -0.5
    stim_tmin: float = 0.5  # Ignore first 500ms onset artifact
    stim_tmax: float = 5.0

    # --- Frequency Parameters (Hz) ---
    stim_freq: float = 32.0
    fmin: float = 2.0
    fmax: float = 200.0
    n_fft: int = 8192  # High resolution for peak detection

    # --- Analysis Modes (aligned with tfr_contrast.py) ---
    # "logratio", "ratio", "percent", "zscore"
    baseline_mode: str = "logratio"
    # "ratio" (subtract dB/normalized), "absolute" (subtract raw power)
    contrast_mode: str = "ratio"

    # --- Peak Detection ---
    snr_threshold_db: float = 2.0  # Threshold for detection
    harmonic_tolerance_hz: float = 5.0  # Window around harmonics

    # --- Preprocessing ---
    montage: str = "standard_1020"
    notch_freqs: List[float] = field(default_factory=lambda: [50.0, 100.0])
    # Default Somatosensory Weighted Laplacians
    virtual_channels: Optional[Dict[str, Any]] = field(
        default_factory=lambda: {
            "C3_lap": {
                "base": "C3",
                "weights": {"FC3": 2.0, "CP3": 2.0, "Cz": 1.0, "T7": 1.0},
                "divisor": 6.0,
            },
            "C4_lap": {
                "base": "C4",
                "weights": {"FC4": 2.0, "CP4": 2.0, "Cz": 1.0, "T8": 1.0},
                "divisor": 6.0,
            },
        }
    )

    @classmethod
    def from_yaml(cls, yaml_dict: Dict[str, Any]) -> "PeakFinderConfig":
        """Build config from nested YAML dict, ignoring unknown keys."""
        flat = {}
        for section in yaml_dict.values():
            if isinstance(section, dict):
                flat.update(section)
        flat.update(
            {k: v for k, v in yaml_dict.items() if not isinstance(v, dict)}
        )
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in flat.items() if k in known_fields}
        return cls(**filtered)

# ============================================================================
# ANALYSIS CLASS
# ============================================================================

class PSDPeakAnalyzer:
    def __init__(self, config: PeakFinderConfig):
        self.cfg = config
        self.results = []

    def _apply_virtual_channels(self, raw: mne.io.Raw) -> None:
        """Compute and add virtual channels from config."""
        if not self.cfg.virtual_channels or not raw:
            return

        for name, params in self.cfg.virtual_channels.items():
            try:
                base_ch = params.get("base")
                weights = params.get("weights", {})
                divisor = params.get("divisor", 1.0)

                if base_ch not in raw.ch_names:
                    logger.warning("Base channel %s for virtual channel %s not found. Skipping.", base_ch, name)
                    continue

                base_data = raw.get_data(picks=[base_ch])[0]
                ref_sum = np.zeros_like(base_data)
                for ref_ch, weight in weights.items():
                    if ref_ch in raw.ch_names:
                        ref_sum += raw.get_data(picks=[ref_ch])[0] * weight
                    else:
                        logger.warning("Ref channel %s for %s not found. Skipping weight.", ref_ch, name)

                virtual_data = base_data - (ref_sum / divisor)
                # Add as 'eeg' type so it's included in PSD/TFR processing by default
                info = mne.create_info([name], raw.info["sfreq"], ch_types=["eeg"])
                new_raw = mne.io.RawArray(
                    virtual_data[np.newaxis, :], info, verbose=False
                )
                raw.add_channels([new_raw], force_update_info=True)
                logger.info("Created virtual channel: %s (type: eeg)", name)

            except Exception as e:
                logger.error("Failed to create virtual channel %s: %s", name, e)

    def preprocess(self, raw: mne.io.Raw, label: str) -> mne.io.Raw:
        """Apply robust PREP pipeline and interpolate bad channels."""
        logger.info("[%s] Running PREP preprocessing...", label)

        # Save non-EEG channels to re-add later
        misc_channels = {}
        for ch_name in raw.ch_names:
            ch_type = raw.get_channel_types([ch_name])[0]
            if ch_type != "eeg":
                misc_channels[ch_name] = (raw.get_data(picks=[ch_name]), ch_type)

        # Select only EEG channels for PREP
        eeg_raw = raw.copy().pick_types(eeg=True)

        # Ensure montage is set
        try:
            montage = mne.channels.make_standard_montage(self.cfg.montage)
            eeg_raw.set_montage(montage, on_missing="ignore")
        except Exception as e:
            logger.warning("[%s] Could not set montage: %s", label, e)
            montage = None

        n_eeg = len(eeg_raw.ch_names)

        # RANSAC requires at least 16 channels. Fall back if fewer.
        use_ransac = n_eeg >= 16
        if not use_ransac:
            logger.warning(
                "[%s] Only %d EEG channels; disabling RANSAC (needs 16+)",
                label,
                n_eeg,
            )

        prep_params = {
            "ref_chs": "eeg",
            "reref_chs": "eeg",
            "line_freqs": self.cfg.notch_freqs,
        }

        try:
            prep = PrepPipeline(
                eeg_raw,
                prep_params,
                montage,
                ransac=use_ransac,
                random_state=RANDOM_SEED,
            )
            prep.fit()
            clean_raw = prep.raw
            # Interpolate bads to keep channel count consistent across conditions
            clean_raw.interpolate_bads(reset_bads=True)
            logger.info("[%s] PREP complete, bad channels interpolated.", label)
        except Exception as e:
            logger.error(
                "[%s] PREP failed: %s. Falling back to average ref.", label, e
            )
            clean_raw = eeg_raw.copy().set_eeg_reference("average")

        # Re-add non-EEG channels
        if misc_channels:
            for ch_name, (ch_data, ch_type) in misc_channels.items():
                info = mne.create_info(
                    [ch_name], clean_raw.info["sfreq"], ch_types=[ch_type]
                )
                new_ch_raw = mne.io.RawArray(ch_data, info, verbose=False)
                clean_raw.add_channels([new_ch_raw], force_update_info=True)

        clean_raw.filter(self.cfg.fmin, self.cfg.fmax, verbose=False)
        return clean_raw

    def get_normalized_psd(
        self, epochs: mne.Epochs, apply_baseline: bool = True
    ) -> mne.time_frequency.Spectrum:
        """
        Calculate PSD and optionally apply baseline normalization.

        Args:
            epochs: MNE Epochs object.
            apply_baseline: Whether to normalize against the rest period.

        Returns:
            Spectrum object with (potentially normalized) power.
        """
        sfreq = epochs.info["sfreq"]
        n_fft = self.cfg.n_fft

        # Determine segment lengths
        stim_samples = int((self.cfg.stim_tmax - self.cfg.stim_tmin) * sfreq)
        base_samples = int(
            (self.cfg.baseline_tmax - self.cfg.baseline_tmin) * sfreq
        )

        n_per_seg_stim = min(n_fft, stim_samples)
        n_per_seg_base = min(n_fft, base_samples)

        # Stim Window PSD (using picks=None to include all available channels)
        spec_stim = epochs.compute_psd(
            method="welch",
            n_fft=n_fft,
            n_per_seg=n_per_seg_stim,
            tmin=self.cfg.stim_tmin,
            tmax=self.cfg.stim_tmax,
            picks=None,
            verbose=False,
        ).average()

        if not apply_baseline:
            return spec_stim

        # Baseline Window PSD
        spec_base = epochs.compute_psd(
            method="welch",
            n_fft=n_fft,
            n_per_seg=n_per_seg_base,
            tmin=self.cfg.baseline_tmin,
            tmax=self.cfg.baseline_tmax,
            picks=None,
            verbose=False,
        ).average()

        # Apply Normalization logic
        data_stim = spec_stim.get_data()
        data_base = spec_base.get_data()

        if self.cfg.baseline_mode == "logratio":
            # 10 * log10(Stim / Base) -> dB
            normalized = 10 * np.log10(
                np.maximum(data_stim, 1e-20) / np.maximum(data_base, 1e-20)
            )
        elif self.cfg.baseline_mode == "ratio":
            normalized = data_stim / np.maximum(data_base, 1e-20)
        elif self.cfg.baseline_mode == "percent":
            normalized = (data_stim - data_base) / np.maximum(data_base, 1e-20)
        else:
            normalized = data_stim

        spec_stim._data = normalized
        return spec_stim

        spec_stim._data = normalized
        return spec_stim

    def detect_peaks(self, freqs: np.ndarray, psd_data: np.ndarray, ch_name: str):
        """
        Detect harmonic peaks using algorithmic search and direct probing.

        Args:
            freqs: Frequency bins.
            psd_data: Contrast PSD data (units depend on contrast_mode).
            ch_name: Name of the channel.
        """
        is_db = self.cfg.contrast_mode == "ratio"

        for h in range(1, 5):  # Check Fundamental + up to 4th Harmonic
            target_f = self.cfg.stim_freq * h
            if target_f > self.cfg.fmax:
                break

            # Search in a +/- tolerance window
            search_mask = (freqs >= target_f - self.cfg.harmonic_tolerance_hz) & (
                freqs <= target_f + self.cfg.harmonic_tolerance_hz
            )

            if not np.any(search_mask):
                continue

            # Find the highest point in this narrow window
            idx_in_mask = np.argmax(psd_data[search_mask])
            peak_f = freqs[search_mask][idx_in_mask]
            peak_val = psd_data[search_mask][idx_in_mask]

            # Calculate local SNR using a Median-based noise floor
            noise_range = (freqs >= peak_f - 3.0) & (freqs <= peak_f + 3.0)
            signal_region = (freqs >= peak_f - 1.0) & (freqs <= peak_f + 1.0)
            noise_mask = noise_range & ~signal_region

            if np.any(noise_mask):
                noise_floor = np.median(psd_data[noise_mask])

                if is_db:
                    # In dB mode, SNR is subtraction
                    snr = peak_val - noise_floor
                else:
                    # In linear mode, SNR is ratio (converted to dB for display)
                    # Use a small floor to avoid div by zero
                    snr = 10 * np.log10(
                        np.abs(peak_val) / np.maximum(np.abs(noise_floor), 1e-20)
                    )

                if snr >= self.cfg.snr_threshold_db:
                    self.results.append(
                        {
                            "Channel": ch_name,
                            "Harmonic": f"f{h}",
                            "Target Hz": target_f,
                            "Actual Hz": round(peak_f, 2),
                            "Val": round(peak_val, 4),
                            "SNR (dB)": round(snr, 2),
                            "Status": "DETECTED",
                        }
                    )

    def plot_contrast_spectrum(
        self, freqs: np.ndarray, contrast_data: np.ndarray, ch_names: List[str],
        output_path: Path
    ):
        """Plot contrast spectrum for all channels."""
        n_ch = len(ch_names)
        fig, axes = plt.subplots(n_ch, 1, figsize=(12, 3 * n_ch), sharex=True)
        if n_ch == 1:
            axes = [axes]

        y_label = (
            "Power Change (dB)"
            if self.cfg.contrast_mode == "ratio"
            else "Power Diff (\u03BCV\u00B2/Hz)"
        )

        for i, ch in enumerate(ch_names):
            ax = axes[i]
            ax.plot(freqs, contrast_data[i], label=f"{ch} Contrast")
            ax.axhline(0, color="black", alpha=0.3)

            # Mark harmonics
            for h in range(1, 4):
                f_h = self.cfg.stim_freq * h
                ax.axvline(f_h, color="red", linestyle="--", alpha=0.4)
                if i == 0:
                    ax.text(
                        f_h, ax.get_ylim()[1], f"f{h}", color="red", ha="center"
                    )

            # Highlight detected peaks
            ch_res = [r for r in self.results if r["Channel"] == ch]
            for r in ch_res:
                ax.plot(r["Actual Hz"], r["Val"], "ro")

            ax.set_ylabel(y_label)
            ax.legend(loc="upper right")
            ax.grid(True, alpha=0.2)

        axes[-1].set_xlabel("Frequency (Hz)")
        fig.suptitle(
            f"Contrast Spectrum & Detected Peaks (@{self.cfg.stim_freq}Hz) "
            f"[{self.cfg.contrast_mode}]",
            fontsize=14,
        )
        plt.tight_layout()
        plt.savefig(output_path, dpi=120)
        plt.close()
        logger.info("Saved spectrum plot to %s", output_path)

    def run_analysis(
        self,
        fot_path: Path,
        ifnfn_path: Path,
        plot_dir: Optional[Path] = None,
    ) -> pd.DataFrame:
        """Execute full contrast peak detection."""
        # 1. Load
        raw_fot = mne.io.read_raw_fif(fot_path, preload=True, verbose=False)
        raw_ifnfn = mne.io.read_raw_fif(ifnfn_path, preload=True, verbose=False)

        # Pick only EEG channels first to avoid MISC channel interference
        raw_fot.pick_types(eeg=True)
        raw_ifnfn.pick_types(eeg=True)

        # Align channels: pick intersection to ensure broadcastable shapes
        common = sorted(list(set(raw_fot.ch_names) & set(raw_ifnfn.ch_names)))
        if not common:
            logger.error("No common EEG channels found between FOT and IFNFN!")
            return pd.DataFrame()

        logger.info(
            "Aligning FOT and IFNFN to %d common EEG channels.", len(common)
        )
        raw_fot.pick(common)
        raw_ifnfn.pick(common)

        # 2. Preprocess
        raw_fot_clean = self.preprocess(raw_fot, "FOT")
        raw_ifnfn_clean = self.preprocess(raw_ifnfn, "IFNFN")

        # 3. Virtual Channels
        logger.info("Computing Laplacian channels (C3_lap, C4_lap)...")
        self._apply_virtual_channels(raw_fot_clean)
        self._apply_virtual_channels(raw_ifnfn_clean)

        # 4. Epoching
        def _get_epochs(raw):
            events, _ = mne.events_from_annotations(raw, verbose=False)
            return mne.Epochs(
                raw,
                events,
                tmin=self.cfg.epoch_tmin,
                tmax=self.cfg.epoch_tmax,
                baseline=None,
                preload=True,
                verbose=False,
            )

        eps_fot = _get_epochs(raw_fot_clean)
        eps_ifnfn = _get_epochs(raw_ifnfn_clean)

        # 5. Normalized PSD per condition
        # Logic: Contrast = FOT(normalized) - IFNFN(normalized)
        use_baseline = self.cfg.contrast_mode != "absolute"
        psd_fot = self.get_normalized_psd(eps_fot, apply_baseline=use_baseline)
        psd_ifnfn = self.get_normalized_psd(
            eps_ifnfn, apply_baseline=use_baseline
        )

        # 6. Contrast Calculation
        # Use get_data() without picks to ensure we get the full aligned array
        contrast_data = psd_fot.get_data() - psd_ifnfn.get_data()
        freqs = psd_fot.freqs
        ch_names = psd_fot.ch_names

        # 7. Peak Finding
        logger.info(
            "Detecting peaks in contrast spectrum (mode=%s)...",
            self.cfg.contrast_mode,
        )
        for i, ch_name in enumerate(ch_names):
            self.detect_peaks(freqs, contrast_data[i], ch_name)

        # 8. Optional Plotting
        if plot_dir:
            plot_dir.mkdir(parents=True, exist_ok=True)
            plot_file = (
                plot_dir / f"peak_detection_{self.cfg.stim_freq}hz.png"
            )
            self.plot_contrast_spectrum(
                freqs, contrast_data, ch_names, plot_file
            )

        return pd.DataFrame(self.results)

# ============================================================================
# MAIN ENTRY
# ============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find SSSEP Peaks in Contrast PSD")
    parser.add_argument("--fot", type=Path, required=True)
    parser.add_argument("--ifnfn", type=Path, required=True)
    parser.add_argument("--freq", type=float, default=32.0, help="Stim frequency")
    parser.add_argument("--config", type=Path, help="Path to config YAML")
    parser.add_argument("--plot", type=Path, help="Directory to save plots")
    args = parser.parse_args()

    config_dict = {}
    if args.config and args.config.exists():
        try:
            import yaml
            with open(args.config, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f) or {}
            logger.info("Loaded config from %s", args.config)
        except Exception as e:
            logger.warning("Could not load config: %s", e)

    config = PeakFinderConfig.from_yaml(config_dict)
    if args.freq != 32.0: # Override if provided via CLI
        config.stim_freq = args.freq
        
    analyzer = PSDPeakAnalyzer(config)
    
    df_results = analyzer.run_analysis(args.fot, args.ifnfn, plot_dir=args.plot)
    
    if not df_results.empty:
        print("\n" + "="*60)
        print(f" DETECTED NEURAL PEAKS (FOT-IFNFN Contrast @ {args.freq}Hz)")
        print("="*60)
        print(df_results.to_string(index=False))
        print("="*60)
    else:
        print("\nNo significant neural peaks detected above background noise.")
