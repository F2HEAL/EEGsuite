"""
tfr_contrast.py - Time-Frequency Contrast Analysis (Section 9 Pipeline)

Implements the four-step analysis pipeline from the EEG Measurement Protocol
for Tactile Stimulation with Strong Electromagnetic Noise:

    Step 1: Full Time-Frequency Transform (Morlet wavelets)
    Step 2: Epoching around triggers with safety margins
    Step 3: Baseline normalization (dB / log-ratio / percent)
    Step 4: Condition contrasting (FOT - IFNFN)

The contrast cancels EM tactor noise, environmental noise, and non-task
brain activity, isolating the neural response attributable to tactile
stimulation.

Usage (standalone):
    python -m src.analysis.offline.tfr_contrast \\
        --fot  data/raw/250115-1200_FOT.csv \\
        --ifnfn data/raw/250115-1200_IFNFN.csv \\
        --config config/analysis/contrast_offline.yaml

Usage (from main.py):
    python -m src.main contrast \\
        --fot  data/raw/250115-1200_FOT.csv \\
        --ifnfn data/raw/250115-1200_IFNFN.csv
"""

import logging
import html
import gc
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import mne
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Marker definitions - must match the recording module (sweep.py)
# ---------------------------------------------------------------------------
# Condition-aware markers (new)
MARKER_FOT_STIM_ON = 101  # Finger-On-Tactor: stimulation onset
MARKER_FOT_STIM_OFF = 111  # NFOT: stimulation offset
MARKER_FOT_REST = 100  # FOT: inter-trial rest
MARKER_IFNFN_STIM_ON = 201  # In-Field-ot-Feeling-Nipple: stim onset
MARKER_IFNFN_STIM_OFF = 211  # IFNFN: stimulation offset
MARKER_IFNFN_REST = 200  # IFNFN: inter-trial rest

# Legacy single-condition markers (backward compatibility)
MARKER_STIM_ON = 1
MARKER_STIM_OFF = 11
MARKER_REST = 0

MARKER_MAP: Dict[float, str] = {
    # New condition-aware markers
    100.0: "FOT_Rest [100]",
    101.0: "FOT_Stim_ON [101]",
    111.0: "FOT_Stim_OFF [111]",
    200.0: "IFNFN_Rest [200]",
    201.0: "IFNFN_Stim_ON [201]",
    211.0: "IFNFN_Stim_OFF [211]",
    # Legacy markers (single-condition recordings)
    0.0: "Stimulation READY [0]",
    1.0: "Stimulation ON [1]",
    11.0: "Stimulation OFF [11]",
    3.0: "Baseline_VHP_OFF [3]",
    33.0: "Baseline_VHP_ON [33]",
    31.0: "Baseline_NoContact [31]",
    333.0: "Baseline_PreSweep [333]",
}


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------
@dataclass
class TFRContrastConfig:
    """All parameters for the TFR contrast pipeline."""

    # --- Channel / montage ---
    # The profile name (e.g., "freg8", "freg9"). The actual definitions
    # (channels, pick_channels, virtual_channels) are loaded from
    # config/montages/{profile}.yaml during startup.
    montage_profile: str = "freg8"
    channels: List[str] = field(default_factory=list)
    montage: str = "standard_1020"
    pick_channels: Optional[List[str]] = None
    virtual_channels: Optional[Dict[str, Any]] = None

    # --- TFR parameters ---
    tfr_method: str = "morlet"
    tfr_fmin: float = 1.0
    tfr_fmax: float = 60.0
    tfr_fstep: float = 1.0
    n_cycles_mode: str = "adaptive"  # "adaptive" = freqs/2, or fixed int
    n_cycles_fixed: float = 7.0
    tfr_decim: int = 0  # decimation factor (auto if 0)

    # --- Epoching windows (seconds, relative to STIM-ON) ---
    epoch_tmin: float = -1.5  # start of epoch (must include baseline)
    epoch_tmax: float = 5.0  # end of epoch
    baseline_tmin: float = -1.0  # baseline window start
    baseline_tmax: float = -0.5  # baseline window end
    stim_window_tmin: float = 0.5  # stimulation analysis window start
    stim_window_tmax: float = 4.0  # stimulation analysis window end

    # --- Baseline normalization ---
    baseline_mode: str = "logratio"  # "logratio", "ratio", "percent", "zscore"

    # --- Stimulation frequency (for summary analysis) ---
    stim_freq: float = 42.0  # Hz — must match your VHP protocol

    # --- Filtering ---
    fmin: float = 0.5
    fmax: float = 100.0
    notch_freqs: List[float] = field(default_factory=lambda: [50.0, 100.0])

    # --- Condition event names ---
    fot_event: str = "FOT_Stim_ON [101]"
    ifnfn_event: str = "IFNFN_Stim_ON [201]"
    # Fallback for single-condition files (legacy)
    legacy_stim_event: str = "Stimulation ON [1]"

    # --- Output ---
    output_dir: str = "reports"

    @classmethod
    def from_yaml(cls, yaml_dict: Dict[str, Any]) -> "TFRContrastConfig":
        """Build config from a (possibly nested) YAML dict, ignoring unknown keys."""
        flat = {}
        for section in yaml_dict.values():
            if isinstance(section, dict):
                flat.update(section)
            else:
                # Top-level scalar
                pass
        # Also include top-level keys directly
        flat.update({k: v for k, v in yaml_dict.items() if not isinstance(v, dict)})

        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in flat.items() if k in known_fields}
        return cls(**filtered)

    def apply_montage_yaml(self, montage_path: Path, overwrite: bool = True) -> None:
        """
        Load a montage YAML (e.g. config/montages/freg8.yaml) and apply
        its fields to this config.
        Keeps this config aligned with the montage definitions used by
        EEGVisualizer and the rest of the repo.
        """
        try:
            import yaml

            with open(montage_path, "r") as f:
                m = yaml.safe_load(f)

            # Helper to check if a value should be overwritten
            def _should_set(key: str, current_val: Any, default_val: Any) -> bool:
                if overwrite:
                    return True
                if current_val == default_val:
                    return True
                return False

            if "channels" in m and _should_set("channels", self.channels, []):
                self.channels = m["channels"]
            if "pick_channels" in m and _should_set(
                "pick_channels", self.pick_channels, None
            ):
                self.pick_channels = m["pick_channels"]
            if "montage" in m and _should_set("montage", self.montage, "standard_1020"):
                self.montage = m["montage"]
            if "name" in m and _should_set("name", self.montage_profile, "freg8"):
                self.montage_profile = m["name"]
            if "virtual_channels" in m and _should_set(
                "virtual_channels", self.virtual_channels, None
            ):
                self.virtual_channels = m["virtual_channels"]

            logger.info(
                "Applied montage '%s' from %s: %d channels, picks=%s",
                m.get("name", "?"),
                montage_path.name,
                len(self.channels),
                self.pick_channels,
            )
        except Exception as exc:
            logger.warning("Could not load montage YAML %s: %s", montage_path, exc)


# ---------------------------------------------------------------------------
# Core analysis class
# ---------------------------------------------------------------------------
class TFRContrastAnalyzer:
    """
    Implements the Section 9 TFR contrast pipeline.

    Supports two usage modes:
      1. Two-file mode:  separate FOT and IFNFN CSV files (fully blocked).
      2. Single-file mode: one CSV with interleaved condition markers.
    """

    def __init__(self, config: TFRContrastConfig) -> None:
        self.cfg = config
        self.raw_fot: Optional[mne.io.RawArray] = None
        self.raw_ifnfn: Optional[mne.io.RawArray] = None
        self.tfr_fot = None  # AverageTFR after baseline norm
        self.tfr_ifnfn = None
        self.tfr_contrast = None  # FOT − IFNFN

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def load_two_files(self, fot_path: Path, ifnfn_path: Path) -> None:
        """Load separate FOT and IFNFN recordings (fully-blocked protocol)."""
        logger.info("Loading FOT file: %s", fot_path)
        self.raw_fot = mne.io.read_raw_fif(fot_path, preload=True)
        logger.info("Loading IFNFN file: %s", ifnfn_path)
        self.raw_ifnfn = mne.io.read_raw_fif(ifnfn_path, preload=True)
        # Apply virtual channels (e.g. Weighted Laplacian) before picking
        self._apply_virtual_channels(self.raw_fot)
        self._apply_virtual_channels(self.raw_ifnfn)

        self._apply_picks(self.raw_fot)
        self._apply_picks(self.raw_ifnfn)

    def load_single_file(self, raw_path: Path) -> None:
        """
        Load a single CSV that contains interleaved FOT/IFNFN trials
        (alternating or randomized protocol).  Condition is determined
        by marker codes 101/201.
        """
        raw = mne.io.read_raw_fif(raw_path, preload=True)
        self._apply_virtual_channels(raw)
        self._apply_picks(raw)
        # Both conditions share the same Raw — epoching separates them
        self.raw_fot = raw
        self.raw_ifnfn = raw

    def _apply_virtual_channels(self, raw: mne.io.RawArray) -> None:
        """Computes and adds virtual channels (e.g., Weighted Laplacian) from config."""
        if not self.cfg.virtual_channels or not raw:
            return

        for name, params in self.cfg.virtual_channels.items():
            try:
                base_ch = params.get("base")
                weights = params.get("weights", {})
                divisor = params.get("divisor", 1.0)

                if base_ch not in raw.ch_names:
                    logger.warning(
                        "Base channel %s for virtual channel %s not found. Skipping.",
                        base_ch,
                        name,
                    )
                    continue

                # Get data for base channel
                base_data = raw.get_data(picks=[base_ch])[0]

                # Compute weighted average of reference channels
                ref_sum = np.zeros_like(base_data)
                for ref_ch, weight in weights.items():
                    if ref_ch in raw.ch_names:
                        ref_sum += raw.get_data(picks=[ref_ch])[0] * weight
                    else:
                        logger.warning(
                            "Ref channel %s for virtual channel %s not found. Skipping weight.",
                            ref_ch,
                            name,
                        )

                # Laplacian = Base - (WeightedSum / Divisor)
                virtual_data = base_data - (ref_sum / divisor)

                # Add to Raw object
                info = mne.create_info([name], raw.info["sfreq"], ch_types=["eeg"])
                new_raw = mne.io.RawArray(
                    virtual_data[np.newaxis, :], info, verbose=False
                )
                raw.add_channels([new_raw], force_update_info=True)
                logger.info("Created virtual channel: %s", name)

            except Exception as e:
                logger.error("Failed to create virtual channel %s: %s", name, e)

    def _apply_picks(self, raw: mne.io.RawArray) -> None:
        """Optionally sub-select channels."""
        picks = self.cfg.pick_channels
        if picks:
            valid = [ch for ch in picks if ch in raw.ch_names]
            if valid:
                raw.pick(valid)
                logger.info("Picked channels: %s", valid)

    # ------------------------------------------------------------------
    # Step 0: Preprocessing
    # ------------------------------------------------------------------
    def preprocess(self, raw: mne.io.RawArray) -> mne.io.RawArray:
        """Band-pass filter and optional notch."""
        raw_filtered = raw.copy()
        raw_filtered.filter(
            l_freq=self.cfg.fmin,
            h_freq=self.cfg.fmax,
            verbose=False,
        )
        if self.cfg.notch_freqs:
            valid_notch = [f for f in self.cfg.notch_freqs if f < self.cfg.fmax]
            if valid_notch:
                raw_filtered.notch_filter(valid_notch, verbose=False)
        logger.info(
            "Preprocessed: band-pass %.1f–%.1f Hz, notch %s",
            self.cfg.fmin,
            self.cfg.fmax,
            self.cfg.notch_freqs,
        )
        return raw_filtered

    # ------------------------------------------------------------------
    # Steps 1–3: TFR → Epoch → Baseline normalize
    # ------------------------------------------------------------------
    def compute_condition_tfr(
        self,
        raw: mne.io.RawArray,
        event_name: str,
    ) -> Optional[mne.time_frequency.AverageTFR]:
        """
        For one condition:
          1. Create epochs around *event_name* triggers.
          2. Compute Morlet TFR on epochs.
          3. Apply baseline normalization.
          4. Return the averaged (across trials) TFR.
        """
        if raw is None:
            logger.error("Raw data is None - cannot compute TFR.")
            return None

        # --- Get events from annotations ---
        try:
            events, event_id = mne.events_from_annotations(raw, verbose=False)
        except Exception as exc:
            logger.error("Failed to extract events: %s", exc)
            return None

        if event_name not in event_id:
            # Try legacy marker as fallback
            if self.cfg.legacy_stim_event in event_id:
                logger.warning(
                    "Event '%s' not found; falling back to legacy '%s'.",
                    event_name,
                    self.cfg.legacy_stim_event,
                )
                event_name = self.cfg.legacy_stim_event
            else:
                logger.error(
                    "Event '%s' not found. Available: %s",
                    event_name,
                    list(event_id.keys()),
                )
                return None

        target_id = event_id[event_name]
        n_trials = np.sum(events[:, 2] == target_id)
        logger.info("Condition '%s': %d trials found.", event_name, n_trials)
        if n_trials == 0:
            return None

        # --- Step 2: Epoching ---
        epochs = mne.Epochs(
            raw,
            events,
            event_id=target_id,
            tmin=self.cfg.epoch_tmin,
            tmax=self.cfg.epoch_tmax,
            baseline=None,  # We apply TFR-level baseline later
            preload=True,
            verbose=False,
            on_missing="warning",
        )
        if len(epochs) == 0:
            logger.warning("All epochs dropped for '%s'.", event_name)
            return None

        logger.info("Created %d clean epochs for '%s'.", len(epochs), event_name)

        # --- Step 1: TFR on epochs (equivalent to TFR-then-epoch) ---
        freqs = np.arange(self.cfg.tfr_fmin, self.cfg.tfr_fmax, self.cfg.tfr_fstep)

        if self.cfg.n_cycles_mode == "adaptive":
            n_cycles = freqs / 2.0
        else:
            n_cycles = self.cfg.n_cycles_fixed

        # Auto-decimation for memory
        decim = self.cfg.tfr_decim
        if decim == 0:
            # Target ~150Hz for TFR sampling rate. This is plenty for
            # visualization and analysis of power envelopes.
            # Wavelet convolution itself happens at raw sfreq.
            target_sfreq = 150.0
            decim = max(1, int(raw.info["sfreq"] / target_sfreq))

        logger.info("Computing TFR (decim=%d, average=True)...", decim)
        power = epochs.compute_tfr(
            method=self.cfg.tfr_method,
            freqs=freqs,
            n_cycles=n_cycles,
            decim=decim,
            return_itc=False,
            average=True,  # Average across epochs to save memory
            n_jobs=1,
            verbose=False,
        )

        # Convert to float32 to save 50% memory (sufficient for EEG analysis)
        power.data = power.data.astype(np.float32)

        # --- Step 3: Baseline normalization on the TFR ---
        power.apply_baseline(
            baseline=(self.cfg.baseline_tmin, self.cfg.baseline_tmax),
            mode=self.cfg.baseline_mode,
            verbose=False,
        )

        logger.info(
            "TFR computed & normalized (%s, baseline [%.1f, %.1f]s) for '%s'.",
            self.cfg.baseline_mode,
            self.cfg.baseline_tmin,
            self.cfg.baseline_tmax,
            event_name,
        )
        return power

    # ------------------------------------------------------------------
    # Step 4: Contrast
    # ------------------------------------------------------------------
    def run_pipeline(self) -> bool:
        """
        Execute the full 4-step pipeline:
          1–3  per condition → self.tfr_fot, self.tfr_ifnfn
          4    contrast      → self.tfr_contrast
        Returns True on success.
        """
        if self.raw_fot is None:
            logger.error(
                "No data loaded. Call load_two_files() or load_single_file() first."
            )
            return False

        # Preprocess
        raw_fot_clean = self.preprocess(self.raw_fot)
        raw_ifnfn_clean = self.preprocess(self.raw_ifnfn)

        # Steps 1–3 per condition
        self.tfr_fot = self.compute_condition_tfr(raw_fot_clean, self.cfg.fot_event)
        self.tfr_ifnfn = self.compute_condition_tfr(
            raw_ifnfn_clean, self.cfg.ifnfn_event
        )

        if self.tfr_fot is None or self.tfr_ifnfn is None:
            logger.error(
                "Pipeline incomplete - could not compute TFR for both conditions."
            )
            return False

        # Step 4: Contrast = FOT - IFNFN
        self.tfr_contrast = self.tfr_fot.copy()
        self.tfr_contrast._data = self.tfr_fot.data - self.tfr_ifnfn.data
        logger.info("Contrast TFR computed (FOT - IFNFN).")
        return True

    def run_single_condition(self, condition: str = "fot") -> bool:
        """
        Run Steps 1–3 on a single condition only (no contrast).
        Useful for inspecting one recording before the full protocol.
        """
        if self.raw_fot is None:
            logger.error("No data loaded.")
            return False

        if condition == "fot":
            raw_clean = self.preprocess(self.raw_fot)
            self.tfr_fot = self.compute_condition_tfr(raw_clean, self.cfg.fot_event)
            return self.tfr_fot is not None
        else:
            raw_clean = self.preprocess(self.raw_ifnfn)
            self.tfr_ifnfn = self.compute_condition_tfr(raw_clean, self.cfg.ifnfn_event)
            return self.tfr_ifnfn is not None

    # ------------------------------------------------------------------
    # Period annotation helper
    # ------------------------------------------------------------------
    def _annotate_periods(self, ax, orientation: str = "vertical") -> None:
        """
        Draw shaded regions and labels for baseline, excluded zone, stim
        period, and post-stim on any matplotlib axis.

        Args:
            ax: matplotlib Axes object
            orientation: "vertical" for time on x-axis (TFR heatmaps, line plots),
                         "horizontal" for time on y-axis (rare, unused currently)
        """
        bl_min = self.cfg.baseline_tmin
        bl_max = self.cfg.baseline_tmax
        stim_min = self.cfg.stim_window_tmin
        stim_max = self.cfg.stim_window_tmax

        if orientation == "vertical":
            # Baseline region (blue tint)
            ax.axvspan(bl_min, bl_max, color="#3B82F6", alpha=0.08, label="_baseline")
            # Excluded zone (red tint)
            ax.axvspan(bl_max, stim_min, color="#EF4444", alpha=0.06, label="_excluded")
            # Stimulation window (green tint)
            ax.axvspan(stim_min, stim_max, color="#10B981", alpha=0.06, label="_stim")

            # Stim ON marker line
            ax.axvline(0, color="#EF4444", linestyle="--", linewidth=1.2, alpha=0.8)

            # Labels at top of plot
            ylim = ax.get_ylim()
            label_y = ylim[1]  # top of axis
            label_kwargs = dict(
                fontsize=7,
                fontweight="bold",
                ha="center",
                va="bottom",
                alpha=0.7,
                clip_on=True,
            )
            mid_bl = (bl_min + bl_max) / 2
            mid_ex = (bl_max + stim_min) / 2
            mid_st = (stim_min + stim_max) / 2

            ax.text(mid_bl, label_y, "BASELINE", color="#3B82F6", **label_kwargs)
            ax.text(mid_ex, label_y, "ONSET", color="#EF4444", **label_kwargs)
            ax.text(mid_st, label_y, "STIMULATION", color="#10B981", **label_kwargs)
            ax.text(
                0,
                label_y,
                "STIM ON",
                color="#EF4444",
                fontsize=6,
                ha="center",
                va="top",
                alpha=0.6,
            )

    # ------------------------------------------------------------------
    # Visualization helpers
    # ------------------------------------------------------------------
    def _stim_freq_line(self, ax, orientation: str = "horizontal") -> None:
        """Draw a dashed line at the stimulation frequency on TFR heatmaps."""
        sf = self.cfg.stim_freq
        last_sf = int(self.cfg.tfr_fmax / self.cfg.stim_freq) + 1
        for i in range(1, last_sf):
            if i > 1:
                color = "#CC3300"
            else:
                color = "#F59E0B"
            if orientation == "horizontal":
                ax.axhline(
                    i * sf, color=color, linestyle="--", linewidth=0.9, alpha=0.7
                )
                ax.text(
                    ax.get_xlim()[1],
                    i * sf,
                    f" {i * sf:.0f} Hz",
                    fontsize=7,
                    va="center",
                    ha="left",
                    color=color,
                    fontweight="bold",
                    alpha=0.8,
                    clip_on=False,
                )

    def plot_tfr(
        self,
        tfr,
        title: str = "TFR",
        fmin: Optional[float] = None,
        fmax: Optional[float] = None,
        tmin: Optional[float] = None,
        tmax: Optional[float] = None,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        cmap: str = "RdBu_r",
    ) -> Optional[plt.Figure]:
        """Plot a single TFR as a time-frequency heatmap per channel."""
        if tfr is None:
            return None

        _fmin = fmin or self.cfg.tfr_fmin
        _fmax = fmax or self.cfg.tfr_fmax
        _tmin = tmin or self.cfg.epoch_tmin + 0.1
        _tmax = tmax or self.cfg.epoch_tmax - 0.1

        n_channels = len(tfr.ch_names)
        fig, axes = plt.subplots(
            n_channels,
            1,
            figsize=(14, 3.0 * n_channels),
            squeeze=False,
        )

        # Compute shared vlim if not provided — same scale across all channels
        if vmin is None or vmax is None:
            time_mask = (tfr.times >= _tmin) & (tfr.times <= _tmax)
            freq_mask = (tfr.freqs >= _fmin) & (tfr.freqs <= _fmax)
            data_slice = tfr.data[:, freq_mask, :][:, :, time_mask]
            abs_max = np.percentile(np.abs(data_slice), 97)
            vmin = -abs_max
            vmax = abs_max

        for idx, ch_name in enumerate(tfr.ch_names):
            ax = axes[idx, 0]
            tfr.plot(
                picks=[ch_name],
                baseline=None,
                tmin=_tmin,
                tmax=_tmax,
                fmin=_fmin,
                fmax=_fmax,
                axes=ax,
                show=False,
                colorbar=True,
                cmap=cmap,
                vlim=(vmin, vmax),
                verbose=False,
            )
            self._annotate_periods(ax)
            self._stim_freq_line(ax)
            ax.set_title(f"{title} — {ch_name}", fontsize=10)

        fig.suptitle(title, fontsize=13, fontweight="bold", y=1.01)
        plt.tight_layout()
        return fig

    def plot_contrast(self, **kwargs) -> Optional[plt.Figure]:
        """Plot the FOT - IFNFN contrast TFR."""
        return self.plot_tfr(
            self.tfr_contrast,
            title="Contrast (FOT - IFNFN)",
            cmap="RdBu_r",
            **kwargs,
        )

    def plot_both_conditions(
        self,
        channel: Optional[str] = None,
        fmin: Optional[float] = None,
        fmax: Optional[float] = None,
    ) -> Optional[plt.Figure]:
        """Side-by-side FOT / IFNFN / Contrast for one channel with shared color scale."""
        if self.tfr_fot is None or self.tfr_ifnfn is None or self.tfr_contrast is None:
            return None

        ch = channel or self.tfr_fot.ch_names[0]
        _fmin = fmin or self.cfg.tfr_fmin
        _fmax = fmax or self.cfg.tfr_fmax
        _tmin = self.cfg.epoch_tmin + 0.1
        _tmax = self.cfg.epoch_tmax - 0.1

        # Shared color scale across all three panels
        ch_idx = self.tfr_fot.ch_names.index(ch)
        time_mask = (self.tfr_fot.times >= _tmin) & (self.tfr_fot.times <= _tmax)
        freq_mask = (self.tfr_fot.freqs >= _fmin) & (self.tfr_fot.freqs <= _fmax)

        # Compute scaling without large concatenations
        d1 = self.tfr_fot.data[ch_idx, freq_mask, :][:, time_mask]
        d2 = self.tfr_ifnfn.data[ch_idx, freq_mask, :][:, time_mask]
        d3 = self.tfr_contrast.data[ch_idx, freq_mask, :][:, time_mask]
        abs_max = max(
            np.percentile(np.abs(d1), 97),
            np.percentile(np.abs(d2), 97),
            np.percentile(np.abs(d3), 97),
        )

        fig, axes = plt.subplots(1, 3, figsize=(22, 5))

        for ax, tfr, label in zip(
            axes,
            [self.tfr_fot, self.tfr_ifnfn, self.tfr_contrast],
            ["FOT (Tactile + EM)", "IFNFN (EM only)", "Contrast (FOT - IFNFN)"],
        ):
            tfr.plot(
                picks=[ch],
                baseline=None,
                tmin=_tmin,
                tmax=_tmax,
                fmin=_fmin,
                fmax=_fmax,
                axes=ax,
                show=False,
                colorbar=True,
                cmap="RdBu_r",
                vlim=(-abs_max, abs_max),
                verbose=False,
            )
            self._annotate_periods(ax)
            self._stim_freq_line(ax)
            ax.set_title(label, fontsize=10)

        fig.suptitle(f"{ch}", fontsize=13, fontweight="bold")
        plt.tight_layout()
        return fig

    def plot_stim_band_timecourse(
        self,
        freq_band: Tuple[float, float] = (20.0, 25.0),
        channel: Optional[str] = None,
    ) -> Optional[plt.Figure]:
        """
        Plot the time-course of power in a specific frequency band
        for both conditions + contrast.
        """
        if self.tfr_fot is None or self.tfr_ifnfn is None:
            return None

        ch = channel or self.tfr_fot.ch_names[0]
        ch_idx_fot = self.tfr_fot.ch_names.index(ch)
        ch_idx_ifnfn = self.tfr_ifnfn.ch_names.index(ch)

        freqs = self.tfr_fot.freqs
        freq_mask = (freqs >= freq_band[0]) & (freqs <= freq_band[1])

        fot_data = self.tfr_fot.data[ch_idx_fot, freq_mask, :].mean(axis=0)
        ifnfn_data = self.tfr_ifnfn.data[ch_idx_ifnfn, freq_mask, :].mean(axis=0)
        contrast_data = fot_data - ifnfn_data
        times = self.tfr_fot.times

        fig, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True)

        # Top: both conditions
        axes[0].plot(times, fot_data, color="#2563EB", label="FOT", linewidth=1.5)
        axes[0].plot(
            times, ifnfn_data, color="#DC2626", label="IFNFN", linewidth=1.5, alpha=0.8
        )
        axes[0].axhline(0, color="gray", linestyle=":", alpha=0.3)
        axes[0].set_ylabel(f"Power ({self.cfg.baseline_mode})")
        axes[0].set_title(
            f"{ch} — {freq_band[0]:.0f}\u2013{freq_band[1]:.0f} Hz",
            fontsize=11,
        )
        axes[0].legend(framealpha=0.9, fontsize=9)
        axes[0].grid(True, alpha=0.15)
        self._annotate_periods(axes[0])

        # Bottom: contrast
        axes[1].plot(times, contrast_data, color="#1E293B", linewidth=1.8)
        axes[1].fill_between(
            times,
            contrast_data,
            0,
            where=contrast_data > 0,
            color="#2563EB",
            alpha=0.15,
        )
        axes[1].fill_between(
            times,
            contrast_data,
            0,
            where=contrast_data < 0,
            color="#DC2626",
            alpha=0.15,
        )
        axes[1].axhline(0, color="gray", linestyle=":", alpha=0.5)
        axes[1].set_xlabel("Time (s)")
        axes[1].set_ylabel(f"Contrast ({self.cfg.baseline_mode})")
        axes[1].set_title("FOT \u2212 IFNFN", fontsize=10)
        axes[1].grid(True, alpha=0.15)
        self._annotate_periods(axes[1])

        plt.tight_layout()
        return fig

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------
    def generate_report(
        self,
        output_dir: Optional[Path] = None,
        filename: str = "tfr_contrast_report.html",
    ) -> Path:
        """
        Generate a full HTML report with all pipeline visualizations,
        plus standalone PNG plots and CSV data exports.

        Output structure:
            output_dir/
                tfr_contrast_report.html
                img/                        (PNGs embedded in HTML)
                png/                        (standalone high-res PNGs)
                csv/                        (TFR data as CSV)
        """
        from datetime import datetime

        out = Path(output_dir or self.cfg.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        img_dir = out / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        png_dir = out / "png"
        png_dir.mkdir(parents=True, exist_ok=True)
        csv_dir = out / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)

        plot_counter = 0

        def _save_fig(fig, name: str, dpi_html: int = 120, dpi_png: int = 200):
            nonlocal plot_counter
            plot_counter += 1
            safe = name.replace(" ", "_").replace("/", "-").replace(":", "")
            safe = f"{plot_counter:02d}_{safe}"
            html_path = img_dir / f"{safe}.png"
            fig.savefig(html_path, bbox_inches="tight", dpi=dpi_html)
            png_path = png_dir / f"{safe}.png"
            fig.savefig(png_path, bbox_inches="tight", dpi=dpi_png)
            plt.close(fig)
            return f"img/{safe}.png"

        def _fig_block(fig, name: str, caption: str = "") -> str:
            rel = _save_fig(fig, name)
            s = f'<img src="{rel}" class="plot" alt="{html.escape(name)}">'
            if caption:
                s += f'<p class="caption">{html.escape(caption)}</p>'
            return s

        # --- Export TFR data as CSV ---
        self._export_csv(csv_dir)

        # --- Collect data for the report ---
        n_fot = str(getattr(self.tfr_fot, "nave", "?")) if self.tfr_fot else "N/A"
        n_ifnfn = str(getattr(self.tfr_ifnfn, "nave", "?")) if self.tfr_ifnfn else "N/A"
        ch_names = self.tfr_fot.ch_names if self.tfr_fot else []

        # Breakdown into physical and virtual
        virt_names = (
            list(self.cfg.virtual_channels.keys()) if self.cfg.virtual_channels else []
        )
        ch_names_phys = [ch for ch in ch_names if ch not in virt_names]
        ch_names_virt = [ch for ch in ch_names if ch in virt_names]
        n_ch_phys = len(ch_names_phys)
        n_ch_virt = len(ch_names_virt)

        if n_ch_virt > 0:
            montage_text = (
                f"{n_ch_phys} channels (+ {n_ch_virt} virt. channels: "
                f"{', '.join(ch_names_virt)})"
            )
        else:
            montage_text = f"{n_ch_phys} channels"

        # --- Section 1: Channel summary (computed first, shown first) ---
        summary_section = ""
        if self.tfr_contrast is not None:
            summary_df = self.compute_channel_summary(stim_freq=self.cfg.stim_freq)
            if summary_df is not None:
                summary_section = self._build_summary_html(
                    summary_df, stim_freq=self.cfg.stim_freq
                )
                summary_csv_path = csv_dir / "channel_summary.csv"
                summary_df.to_csv(summary_csv_path, index=False)
                logger.info("Exported %s", summary_csv_path.name)

        # --- Section 2: Overview TFR plots ---
        overview_plots = ""
        if self.tfr_fot is not None:
            fig = self.plot_tfr(self.tfr_fot, title="FOT (Tactile + EM Noise)")
            overview_plots += (
                '<div class="subsection">'
                "<h3>FOT Condition (Finger On Tactor)</h3>"
                '<p class="caption">Contains both the neural response and EM artifact from the vibration motor.</p>'
                + _fig_block(fig, "TFR_FOT")
                + "</div>"
            )
        if self.tfr_ifnfn is not None:
            fig = self.plot_tfr(self.tfr_ifnfn, title="IFNFN (EM Noise Only)")
            overview_plots += (
                '<div class="subsection">'
                "<h3>IFNFN Condition (In-Field Not-Feeling Nipple)</h3>"
                '<p class="caption">Control: same EM noise, no tactile contact. Serves as the artifact template.</p>'
                + _fig_block(fig, "TFR_IFNFN")
                + "</div>"
            )
        if self.tfr_contrast is not None:
            fig = self.plot_contrast()
            overview_plots += (
                '<div class="subsection">'
                "<h3>Contrast (FOT &minus; IFNFN)</h3>"
                '<p class="caption">Isolated neural response after EM artifact subtraction.</p>'
                + _fig_block(fig, "TFR_Contrast")
                + "</div>"
            )

        # --- Section 3: Per-channel comparisons (collapsible) ---
        comparison_plots = ""
        if self.tfr_contrast is not None:
            for ch in ch_names:
                fig_comp = self.plot_both_conditions(channel=ch)
                if fig_comp:
                    comparison_plots += (
                        f"<details><summary><strong>{ch}</strong></summary>"
                        + _fig_block(
                            fig_comp,
                            f"Comparison_{ch}",
                            f"Left: FOT | Center: IFNFN | Right: Contrast",
                        )
                        + "</details>"
                    )
                # Force cleanup after each channel figure
                gc.collect()

        # --- Section 4: Band time-courses (collapsible, grouped by band) ---
        band_plots = ""
        if self.tfr_contrast is not None:
            stim_low = self.cfg.stim_freq - 5.0
            stim_high = self.cfg.stim_freq + 5.0
            bands = [
                (
                    f"Stim Frequency ({stim_low:.1f}&ndash;{stim_high:.1f} Hz)",
                    f"StimFreq_{self.cfg.stim_freq}Hz",
                    (stim_low, stim_high),
                ),
                ("Beta (13&ndash;30 Hz)", "Beta_13-30Hz", (13.0, 30.0)),
                ("Gamma (30&ndash;45 Hz)", "Gamma_30-45Hz", (30.0, 45.0)),
            ]
            for band_label, band_id, band_range in bands:
                inner = ""
                for ch in ch_names:
                    fig_tc = self.plot_stim_band_timecourse(
                        freq_band=band_range, channel=ch
                    )
                    if fig_tc:
                        inner += (
                            f"<details><summary>{ch}</summary>"
                            + _fig_block(
                                fig_tc,
                                f"Band_{band_id}_{ch}",
                                "Top: FOT vs IFNFN band power. "
                                "Bottom: contrast (isolated neural modulation).",
                            )
                            + "</details>"
                        )
                if inner:
                    band_plots += (
                        f"<details><summary><strong>{band_label}</strong></summary>"
                        f"{inner}</details>"
                    )

        # --- Assemble HTML ---
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        n_csv = len(list(csv_dir.glob("*.csv")))

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TFR Contrast Report</title>
<style>
:root {{
    --c-text: #1E293B;
    --c-muted: #64748B;
    --c-accent: #2563EB;
    --c-border: #E2E8F0;
    --c-bg: #F8FAFC;
    --c-card: #FFFFFF;
}}
* {{ box-sizing: border-box; }}
body {{
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    margin: 0; padding: 40px;
    background: var(--c-bg); color: var(--c-text);
    line-height: 1.6; font-size: 15px;
}}
.container {{
    max-width: 1400px; margin: 0 auto;
    background: var(--c-card); padding: 40px 48px;
    border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
/* --- Typography --- */
h1 {{
    font-size: 1.6em; font-weight: 700; color: var(--c-text);
    border-bottom: 2px solid var(--c-accent); padding-bottom: 12px;
    margin-bottom: 8px;
}}
h1 .subtitle {{ font-size: 0.55em; font-weight: 400; color: var(--c-muted); display: block; margin-top: 4px; }}
h2 {{
    font-size: 1.2em; font-weight: 600; color: var(--c-text);
    margin: 36px 0 12px; padding-bottom: 6px;
    border-bottom: 1px solid var(--c-border);
}}
h2 .sec-num {{ color: var(--c-accent); margin-right: 6px; }}
h3 {{ font-size: 1.0em; color: var(--c-muted); margin: 20px 0 8px; }}
/* --- Layout --- */
.section {{ margin: 32px 0; }}
.subsection {{ margin: 20px 0; }}
.plot {{
    max-width: 100%; height: auto; margin: 16px 0;
    border: 1px solid var(--c-border); border-radius: 4px;
}}
.caption {{
    font-size: 0.85em; color: var(--c-muted);
    text-align: center; margin: 4px 0 20px;
}}
/* --- Info boxes --- */
.info-box {{
    padding: 14px 18px; border-radius: 6px; margin: 16px 0;
    font-size: 0.9em; line-height: 1.5;
}}
.info-box.neutral {{ background: #F8FAFC; border-left: 4px solid #94A3B8; }}
.info-box.method  {{ background: #F8FAFC; border-left: 4px solid var(--c-accent); }}
/* --- Parameters table --- */
.params-table {{
    border-collapse: collapse; font-size: 0.88em; margin: 12px 0;
}}
.params-table td {{
    padding: 5px 16px 5px 0; border: none; vertical-align: top;
}}
.params-table td:first-child {{
    font-weight: 600; color: var(--c-muted); white-space: nowrap;
}}
/* --- Collapsible sections --- */
details {{
    margin: 6px 0; border: 1px solid var(--c-border);
    border-radius: 4px; overflow: hidden;
}}
details > summary {{
    padding: 10px 16px; cursor: pointer;
    background: #F8FAFC; font-size: 0.92em;
    list-style: none;
}}
details > summary::-webkit-details-marker {{ display: none; }}
details > summary::before {{
    content: "\\25B6\\FE0E"; display: inline-block; margin-right: 8px;
    font-size: 0.75em; transition: transform 0.15s;
}}
details[open] > summary::before {{ transform: rotate(90deg); }}
details[open] > summary {{ border-bottom: 1px solid var(--c-border); }}
details > :not(summary) {{ padding: 12px 16px; }}
/* --- Data table --- */
table {{ border-collapse: collapse; }}
table tbody tr {{ border-bottom: 1px solid #F1F5F9; }}
table tbody tr:nth-child(even) {{ background: #F8FAFC; }}
table tbody tr:hover {{ background: #EFF6FF; }}
table th, table td {{ padding: 8px 10px; }}
/* --- Navigation --- */
.toc {{
    background: #F8FAFC; border: 1px solid var(--c-border);
    border-radius: 6px; padding: 16px 24px; margin: 20px 0;
    font-size: 0.9em; columns: 2; column-gap: 32px;
}}
.toc a {{ color: var(--c-accent); text-decoration: none; }}
.toc a:hover {{ text-decoration: underline; }}
.toc li {{ margin: 3px 0; break-inside: avoid; }}
/* --- Footer --- */
.footer {{
    margin-top: 40px; padding-top: 16px;
    border-top: 1px solid var(--c-border);
    color: var(--c-muted); font-size: 0.8em; text-align: center;
}}
</style>
</head>
<body>
<div class="container">

<h1>
    TFR Contrast Analysis
    <span class="subtitle">
        FOT &minus; IFNFN condition subtraction
        &nbsp;|&nbsp; Generated {timestamp}
    </span>
</h1>

<nav class="toc">
<strong>Contents</strong>
<ol>
<li><a href="#summary">Channel Response Summary</a></li>
<li><a href="#methods">Methods &amp; Parameters</a></li>
<li><a href="#overview">TFR Overview (FOT, IFNFN, Contrast)</a></li>
<li><a href="#comparisons">Per-Channel Condition Comparisons</a></li>
<li><a href="#timecourses">Band Time-Courses</a></li>
<li><a href="#exports">Data Exports</a></li>
</ol>
</nav>

<!-- ============================================================ -->
<div class="section" id="summary">
<h2><span class="sec-num">1.</span> Channel Response Summary</h2>
{summary_section}
</div>

<!-- ============================================================ -->
<div class="section" id="methods">
<h2><span class="sec-num">2.</span> Methods &amp; Parameters</h2>
<div class="info-box method">
    <strong>Pipeline:</strong> Morlet wavelet TFR computed per epoch, then
    baseline-normalized and averaged across trials. The contrast
    (FOT&nbsp;&minus;&nbsp;IFNFN) subtracts the EM artifact common to both
    conditions, isolating the neural component.
</div>
<table class="params-table">
    <tr><td>Montage</td><td>{html.escape(self.cfg.montage_profile)} &mdash;
        {montage_text}: {', '.join(ch_names)}</td></tr>
    <tr><td>TFR method</td><td>Morlet wavelets, {self.cfg.tfr_fmin}&ndash;{self.cfg.tfr_fmax} Hz
        (step {self.cfg.tfr_fstep} Hz), cycles: {self.cfg.n_cycles_mode}</td></tr>
    <tr><td>Baseline normalization</td><td>{self.cfg.baseline_mode},
        window [{self.cfg.baseline_tmin}, {self.cfg.baseline_tmax}]&nbsp;s</td></tr>
    <tr><td>Stimulation window</td><td>[{self.cfg.stim_window_tmin}, {self.cfg.stim_window_tmax}]&nbsp;s
        (relative to stim onset)</td></tr>
    <tr><td>Epoch window</td><td>[{self.cfg.epoch_tmin}, {self.cfg.epoch_tmax}]&nbsp;s</td></tr>
    <tr><td>Filtering</td><td>Band-pass {self.cfg.fmin}&ndash;{self.cfg.fmax} Hz,
        notch {self.cfg.notch_freqs}</td></tr>
    <tr><td>Trials</td><td>FOT: {n_fot} &nbsp;|&nbsp; IFNFN: {n_ifnfn}</td></tr>
    <tr><td>Stim frequency</td><td>{self.cfg.stim_freq} Hz</td></tr>
</table>
</div>

<!-- ============================================================ -->
<div class="section" id="overview">
<h2><span class="sec-num">3.</span> TFR Overview</h2>
<p>Full time&ndash;frequency representations for each condition and their contrast.
Each subplot shows one channel; time is relative to stimulation onset (t&nbsp;=&nbsp;0).</p>
{overview_plots}
</div>

<!-- ============================================================ -->
<div class="section" id="comparisons">
<h2><span class="sec-num">4.</span> Per-Channel Condition Comparisons</h2>
<p>Side-by-side FOT, IFNFN, and Contrast TFR for each channel. Click to expand.</p>
{comparison_plots}
</div>

<!-- ============================================================ -->
<div class="section" id="timecourses">
<h2><span class="sec-num">5.</span> Band Time-Courses</h2>
<p>Power averaged within frequency bands, plotted over time for each channel.
Top panel: both conditions; bottom panel: contrast (isolated neural modulation).
Click a band to expand, then click a channel.</p>
{band_plots}
</div>

<!-- ============================================================ -->
<div class="section" id="exports">
<h2><span class="sec-num">6.</span> Data Exports</h2>
<div class="info-box neutral">
    <strong>{n_csv}</strong> CSV files exported to <code>csv/</code>
    &nbsp;|&nbsp; <strong>{plot_counter}</strong> high-resolution PNGs in <code>png/</code>
    <br>
    Includes per-channel full TFR matrices (frequency &times; time),
    stim-window averages (channel &times; frequency), and the channel summary table.
</div>
</div>

<div class="footer">
    EEGsuite &mdash; TFR Contrast Analysis &nbsp;|&nbsp;
    {plot_counter} plots, {n_csv} CSV files &nbsp;|&nbsp;
    {timestamp}
</div>

</div>
</body>
</html>"""

        report_path = out / filename
        report_path.write_text(html_content, encoding="utf-8")
        logger.info(
            "Report saved: %s (%d plots in png/, %d CSVs in csv/)",
            report_path,
            plot_counter,
            len(list(csv_dir.glob("*.csv"))),
        )
        return report_path

    def _export_csv(self, csv_dir: Path) -> None:
        """
        Export TFR data as CSV files for external analysis.

        Produces:
          - tfr_fot.csv         (channels x freqs, averaged over stim window)
          - tfr_ifnfn.csv       (channels x freqs, averaged over stim window)
          - tfr_contrast.csv    (channels x freqs, averaged over stim window)
          - tfr_fot_full.csv    (freq x time, per channel)
          - tfr_ifnfn_full.csv
          - tfr_contrast_full.csv
        """

        def _save_band_avg(tfr, name: str):
            """Save frequency-profile CSV: mean power during stim window."""
            if tfr is None:
                return
            times = tfr.times
            stim_mask = (times >= self.cfg.stim_window_tmin) & (
                times <= self.cfg.stim_window_tmax
            )

            # Average over the stimulation time window -> (channels, freqs)
            stim_avg = tfr.data[:, :, stim_mask].mean(axis=2)

            df = pd.DataFrame(
                stim_avg,
                index=tfr.ch_names,
                columns=[f"{f:.1f}Hz" for f in tfr.freqs],
            )
            df.index.name = "channel"
            path = csv_dir / f"{name}.csv"
            df.to_csv(path)
            logger.info("Exported %s", path.name)

        def _save_full(tfr, name: str):
            """Save full time x freq CSV per channel."""
            if tfr is None:
                return
            for ch_idx, ch_name in enumerate(tfr.ch_names):
                # (freqs, times) matrix
                df = pd.DataFrame(
                    tfr.data[ch_idx],
                    index=[f"{f:.1f}Hz" for f in tfr.freqs],
                    columns=[f"{t:.3f}s" for t in tfr.times],
                )
                df.index.name = "frequency"
                path = csv_dir / f"{name}_{ch_name}.csv"
                df.to_csv(path)
            logger.info("Exported %s (per-channel, %d files)", name, len(tfr.ch_names))

        # Frequency profiles (compact: one row per channel)
        _save_band_avg(self.tfr_fot, "tfr_fot_stim_avg")
        _save_band_avg(self.tfr_ifnfn, "tfr_ifnfn_stim_avg")
        _save_band_avg(self.tfr_contrast, "tfr_contrast_stim_avg")

        # Full time-frequency matrices (one file per channel)
        _save_full(self.tfr_fot, "tfr_fot_full")
        _save_full(self.tfr_ifnfn, "tfr_ifnfn_full")
        _save_full(self.tfr_contrast, "tfr_contrast_full")

    def compute_channel_summary(
        self,
        stim_freq: float = 42.0,
        freq_tolerance: float = 2.0,
        neural_channels: Optional[List[str]] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Compute per-channel numerical summary of contrast power with
        effect-size estimation and noise-floor-referenced detection.

        For each channel computes:
          - Mean contrast power at stim frequency during stim vs baseline
          - FOT and IFNFN power (to show what was subtracted)
          - EM cancellation ratio: how much EM artifact was removed
          - Beta desynchronization (13-30 Hz, *excluding* stim band)
          - Cohen's d effect size (stim vs baseline time-points)
          - Detection via noise-floor threshold (2 SD above baseline variability)

        Args:
            stim_freq: Expected stimulation frequency in Hz
            freq_tolerance: +/- Hz around stim_freq to average
            neural_channels: Channels expected to show neural response
                             (default: somatosensory C3, C4, CP3, CP4)

        Returns:
            DataFrame with one row per channel and summary columns,
            or None if contrast TFR is not available.
        """
        if self.tfr_contrast is None or self.tfr_fot is None or self.tfr_ifnfn is None:
            return None

        if neural_channels is None:
            neural_channels = ["C3", "C4", "CP3", "CP4"]

        freqs = self.tfr_contrast.freqs
        times = self.tfr_contrast.times

        # Frequency masks
        stim_freq_mask = (freqs >= stim_freq - freq_tolerance) & (
            freqs <= stim_freq + freq_tolerance
        )
        # Beta band EXCLUDING the stim frequency to avoid contamination
        beta_mask = (
            (freqs >= 13.0)
            & (freqs <= 30.0)
            & ~(
                (freqs >= stim_freq - freq_tolerance)
                & (freqs <= stim_freq + freq_tolerance)
            )
        )

        # Time masks
        stim_time_mask = (times >= self.cfg.stim_window_tmin) & (
            times <= self.cfg.stim_window_tmax
        )
        base_time_mask = (times >= self.cfg.baseline_tmin) & (
            times <= self.cfg.baseline_tmax
        )

        if not np.any(stim_freq_mask) or not np.any(stim_time_mask):
            logger.warning("Stim frequency or time window out of TFR range.")
            return None

        rows = []
        for ch_idx, ch_name in enumerate(self.tfr_contrast.ch_names):
            # --- Contrast at stim frequency: time-point distributions ---
            contrast_stim_vals = self.tfr_contrast.data[ch_idx][stim_freq_mask][
                :, stim_time_mask
            ].mean(axis=0)
            contrast_base_vals = self.tfr_contrast.data[ch_idx][stim_freq_mask][
                :, base_time_mask
            ].mean(axis=0)

            contrast_stim_mean = float(contrast_stim_vals.mean())
            contrast_base_mean = float(contrast_base_vals.mean())

            # --- Cohen's d for SSSEP: stim vs baseline at stim freq ---
            pooled_std = np.sqrt(
                (contrast_stim_vals.var() + contrast_base_vals.var()) / 2.0
            )
            if pooled_std > 0:
                cohens_d = (contrast_stim_mean - contrast_base_mean) / pooled_std
            else:
                cohens_d = 0.0

            # --- SSSEP detection: positive entrainment at stim frequency ---
            # Positive contrast + medium effect size = brain entrains to vibration.
            # This proves the stimulus reaches somatosensory cortex.
            sssep_detected = (contrast_stim_mean > 0) and (cohens_d >= 0.5)

            # --- FOT and IFNFN individually at stim frequency ---
            fot_stim = float(
                self.tfr_fot.data[ch_idx][stim_freq_mask][:, stim_time_mask].mean()
            )
            ifnfn_stim = float(
                self.tfr_ifnfn.data[ch_idx][stim_freq_mask][:, stim_time_mask].mean()
            )

            # --- EM cancellation ratio ---
            # Only meaningful when both FOT and IFNFN show enhancement
            # (positive log-ratio). When either is negative, the concept
            # "fraction of FOT that was EM artifact" doesn't apply.
            if fot_stim > 0.01 and ifnfn_stim > 0.01:
                em_cancelled_pct = min((ifnfn_stim / fot_stim) * 100.0, 100.0)
            elif fot_stim > 0.01 and ifnfn_stim <= 0.01:
                em_cancelled_pct = 0.0  # no EM artifact to cancel
            else:
                em_cancelled_pct = np.nan  # FOT shows no enhancement

            # --- Beta band contrast (excluding stim freq) ---
            if np.any(beta_mask):
                beta_stim_vals = self.tfr_contrast.data[ch_idx][beta_mask][
                    :, stim_time_mask
                ].mean(axis=0)
                beta_base_vals = self.tfr_contrast.data[ch_idx][beta_mask][
                    :, base_time_mask
                ].mean(axis=0)
                beta_contrast = float(beta_stim_vals.mean())

                # Cohen's d for beta ERD: stim vs baseline in beta band
                beta_pooled = np.sqrt(
                    (beta_stim_vals.var() + beta_base_vals.var()) / 2.0
                )
                if beta_pooled > 0:
                    beta_d = (
                        float(beta_stim_vals.mean()) - float(beta_base_vals.mean())
                    ) / beta_pooled
                else:
                    beta_d = 0.0
            else:
                beta_contrast = np.nan
                beta_d = 0.0

            # --- Beta ERD detection: desynchronization in beta band ---
            # Negative contrast in beta + medium effect = pathological beta
            # is being disrupted. This is the therapeutic mechanism for PD.
            beta_erd_detected = (beta_contrast < 0) and (beta_d <= -0.5)

            # Classification
            is_neural = ch_name in neural_channels

            rows.append(
                {
                    "Channel": ch_name,
                    "Type": "Somatosensory" if is_neural else "Other",
                    f"Contrast @ {stim_freq:.0f}Hz (stim)": round(
                        contrast_stim_mean, 4
                    ),
                    f"Contrast @ {stim_freq:.0f}Hz (base)": round(
                        contrast_base_mean, 4
                    ),
                    "Stim - Baseline": round(
                        contrast_stim_mean - contrast_base_mean, 4
                    ),
                    "SSSEP d": round(cohens_d, 2),
                    "SSSEP": sssep_detected,
                    f"FOT @ {stim_freq:.0f}Hz": round(fot_stim, 4),
                    f"IFNFN @ {stim_freq:.0f}Hz": round(ifnfn_stim, 4),
                    "EM Cancelled (%)": (
                        round(em_cancelled_pct, 1)
                        if not np.isnan(em_cancelled_pct)
                        else np.nan
                    ),
                    "Beta Contrast": round(beta_contrast, 4),
                    "Beta ERD d": round(beta_d, 2),
                    "Beta ERD": beta_erd_detected,
                }
            )

        df = pd.DataFrame(rows)
        logger.info("Channel summary computed for %.0f Hz.", stim_freq)
        return df

    def _build_summary_html(
        self,
        summary_df: pd.DataFrame,
        stim_freq: float = 42.0,
    ) -> str:
        """
        Render the channel summary DataFrame as a styled HTML section
        with dual-detection (SSSEP + Beta ERD) for vibrotactile therapy context.
        """
        if summary_df is None or summary_df.empty:
            return ""

        stim_col = f"Contrast @ {stim_freq:.0f}Hz (stim)"
        base_col = f"Contrast @ {stim_freq:.0f}Hz (base)"
        fot_col = f"FOT @ {stim_freq:.0f}Hz"
        ifnfn_col = f"IFNFN @ {stim_freq:.0f}Hz"

        # --- Compute aggregate statistics ---
        soma_df = summary_df[summary_df["Type"] == "Somatosensory"]
        other_df = summary_df[summary_df["Type"] == "Other"]
        n_total = len(summary_df)
        n_soma_total = len(soma_df)

        # SSSEP stats
        n_sssep = int(summary_df["SSSEP"].sum())
        n_soma_sssep = int(soma_df["SSSEP"].sum()) if n_soma_total > 0 else 0
        mean_soma_sssep_d = (
            float(soma_df["SSSEP d"].mean()) if n_soma_total > 0 else 0.0
        )
        mean_soma_effect = (
            float(soma_df["Stim - Baseline"].mean()) if n_soma_total > 0 else 0.0
        )
        mean_other_effect = (
            float(other_df["Stim - Baseline"].mean()) if len(other_df) > 0 else 0.0
        )
        topo_specific = mean_soma_effect > mean_other_effect and mean_soma_effect > 0

        # Beta ERD stats
        n_beta_erd = int(summary_df["Beta ERD"].sum())
        n_soma_beta_erd = int(soma_df["Beta ERD"].sum()) if n_soma_total > 0 else 0
        soma_beta_mean = (
            float(soma_df["Beta Contrast"].mean()) if n_soma_total > 0 else 0.0
        )
        soma_beta_d_mean = (
            float(soma_df["Beta ERD d"].mean()) if n_soma_total > 0 else 0.0
        )

        # Effect size label helper
        def _d_label(d):
            ad = abs(d)
            if ad >= 0.8:
                return "large"
            elif ad >= 0.5:
                return "medium"
            elif ad >= 0.2:
                return "small"
            else:
                return "negligible"

        # --- SSSEP verdict ---
        if n_soma_sssep == n_soma_total and n_soma_total > 0 and topo_specific:
            sssep_verdict = (
                f"<strong>SSSEP detected</strong> "
                f"on all {n_soma_total} somatosensory channels with topographic specificity "
                f"(response stronger over somatosensory than non-somatosensory sites). "
                f"Mean effect size: d&nbsp;=&nbsp;{mean_soma_sssep_d:+.2f} ({_d_label(mean_soma_sssep_d)}). "
                "This is consistent with cortical entrainment to the vibrotactile stimulus."
            )
        elif n_soma_sssep > 0:
            sssep_verdict = (
                f"<strong>Partial SSSEP</strong>: "
                f"{n_soma_sssep}/{n_soma_total} somatosensory channels show entrainment "
                f"above the detection threshold. "
                f"Mean effect size: d&nbsp;=&nbsp;{mean_soma_sssep_d:+.2f} ({_d_label(mean_soma_sssep_d)}). "
                "Channels below threshold may require more trials to resolve."
            )
        else:
            sssep_verdict = (
                f"<strong>No SSSEP detected</strong> "
                f"on somatosensory channels (d&nbsp;=&nbsp;{mean_soma_sssep_d:+.2f}). "
                "Possible factors: insufficient trial count, low stimulation amplitude, "
                "poor electrode contact, or absence of cortical entrainment at this frequency."
            )

        # --- Beta ERD verdict ---
        if n_soma_beta_erd > 0:
            beta_verdict = (
                f"<strong>Beta ERD observed</strong> "
                f"on {n_soma_beta_erd}/{n_soma_total} somatosensory channels. "
                f"Mean beta contrast: {soma_beta_mean:+.3f}, "
                f"d&nbsp;=&nbsp;{soma_beta_d_mean:+.2f} ({_d_label(soma_beta_d_mean)}). "
                "Beta desynchronization over sensorimotor cortex during vibrotactile stimulation "
                "is consistent with disruption of resting-state beta oscillations."
            )
        elif soma_beta_mean < -0.01:
            beta_verdict = (
                f"<strong>Trend toward beta ERD</strong> "
                f"(mean&nbsp;=&nbsp;{soma_beta_mean:+.3f}, d&nbsp;=&nbsp;{soma_beta_d_mean:+.2f}) "
                "but below the detection threshold (|d|&nbsp;&lt;&nbsp;0.5). "
                "This effect may become significant with a larger number of trials."
            )
        else:
            beta_verdict = (
                f"<strong>No beta desynchronization observed</strong> "
                f"(mean&nbsp;=&nbsp;{soma_beta_mean:+.3f}). "
                "Absence of beta ERD does not rule out a cortical response; "
                "beta modulation depends on stimulation parameters, cortical state, "
                "and individual variability."
            )

        # --- Summary table rows ---
        table_rows = []
        for _, row in summary_df.iterrows():
            ch_type = row["Type"]
            type_bg = "#3B82F6" if ch_type == "Somatosensory" else "#94A3B8"

            # SSSEP detection styling
            sssep = row["SSSEP"]
            sssep_icon = "&#9745;" if sssep else "&#9744;"
            sssep_color = "#059669" if sssep else "#DC2626"

            # SSSEP d color
            sssep_d = row["SSSEP d"]
            if sssep_d >= 0.8:
                sssep_d_bg = "#D1FAE5"
            elif sssep_d >= 0.5:
                sssep_d_bg = "#FEF3C7"
            elif sssep_d >= 0.2:
                sssep_d_bg = "#FEF9C3"
            else:
                sssep_d_bg = "transparent"

            # Beta ERD detection styling
            beta_erd = row["Beta ERD"]
            beta_icon = "&#9745;" if beta_erd else "&#9744;"
            beta_erd_color = "#059669" if beta_erd else "#DC2626"

            # Beta contrast color (negative = desync = good)
            beta_val = row["Beta Contrast"]
            beta_d_val = row["Beta ERD d"]
            if beta_val < -0.05:
                beta_style = "color:#059669;font-weight:bold;"
            elif beta_val > 0.05:
                beta_style = "color:#DC2626;"
            else:
                beta_style = "color:#6B7280;"

            # EM cancellation
            em_pct = row["EM Cancelled (%)"]
            em_is_nan = pd.isna(em_pct)
            if em_is_nan:
                em_style = "color:#9CA3AF;"
            elif em_pct > 80:
                em_style = "color:#DC2626;"
            elif em_pct > 50:
                em_style = "color:#D97706;"
            else:
                em_style = "color:#059669;"

            table_rows.append(
                f"""<tr>
                <td><strong>{html.escape(row['Channel'])}</strong></td>
                <td><span style="background:{type_bg};color:white;
                    padding:2px 8px;border-radius:3px;font-size:0.8em;">
                    {html.escape(ch_type)}</span></td>
                <td style="text-align:right;">{row[stim_col]:+.4f}</td>
                <td style="text-align:right;">{row['Stim - Baseline']:+.4f}</td>
                <td style="text-align:right;background:{sssep_d_bg};">{sssep_d:+.2f}</td>
                <td style="text-align:center;color:{sssep_color};font-size:1.1em;">{sssep_icon}</td>
                <td style="text-align:right;">{row[fot_col]:+.4f}</td>
                <td style="text-align:right;">{row[ifnfn_col]:+.4f}</td>
                <td style="text-align:right;{em_style}">{"N/A" if em_is_nan else f"{em_pct:.0f}%"}</td>
                <td style="text-align:right;{beta_style}">{beta_val:+.4f}</td>
                <td style="text-align:right;">{beta_d_val:+.2f}</td>
                <td style="text-align:center;color:{beta_erd_color};font-size:1.1em;">{beta_icon}</td>
            </tr>"""
            )

        # --- EM cancellation summary ---
        em_valid = summary_df["EM Cancelled (%)"].dropna()
        mean_em = float(em_valid.mean()) if len(em_valid) > 0 else 0.0
        if mean_em > 60:
            em_summary = (
                f"On average, <strong>{mean_em:.0f}%</strong> of the FOT signal at {stim_freq:.0f}&nbsp;Hz "
                "was EM artifact (cancelled by subtraction). The contrast successfully isolates "
                "the residual neural component."
            )
        else:
            em_summary = (
                f"EM artifact accounts for ~{mean_em:.0f}% of FOT power at {stim_freq:.0f}&nbsp;Hz. "
                "The neural contribution is substantial relative to the artifact."
            )

        section_html = f"""
        <div class="section">
            <h2>Channel Response Summary @ {stim_freq:.0f} Hz</h2>

            <div style="background:#F0F9FF;border:1px solid #BAE6FD;
                         padding:18px;border-radius:6px;margin:15px 0;">
                <strong style="font-size:1.1em;">1. Cortical Entrainment (SSSEP at {stim_freq:.0f} Hz):</strong><br>
                {sssep_verdict}
                {"<br>Topographic specificity confirmed: response is stronger over somatosensory cortex." if topo_specific else ""}
            </div>

            <div style="background:#F0FDF4;border:1px solid #BBF7D0;
                         padding:18px;border-radius:6px;margin:15px 0;">
                <strong style="font-size:1.1em;">2. Beta-Band Modulation (ERD, 13&ndash;30 Hz excl. stim band):</strong><br>
                {beta_verdict}
            </div>

            <div class="info">
                <strong>How to read this table:</strong><br>
                All power values are baseline-normalized ({self.cfg.baseline_mode}).
                <strong>Contrast&nbsp;=&nbsp;FOT&nbsp;&minus;&nbsp;IFNFN</strong> isolates
                the neural component by subtracting EM artifact.
                Two types of neural response are assessed independently:<br><br>

                <table style="border-collapse:collapse;margin:8px 0;font-size:0.9em;">
                <tr>
                    <td style="padding:4px 12px;"><strong>SSSEP</strong> (Steady-State Somatosensory Evoked Potential)</td>
                    <td style="padding:4px 12px;">Positive contrast at {stim_freq:.0f}&nbsp;Hz &mdash;
                        cortical activity entrains to the vibration frequency.
                        Indicates the vibrotactile stimulus is evoking a measurable cortical response.</td>
                </tr>
                <tr>
                    <td style="padding:4px 12px;"><strong>Beta ERD</strong> (Event-Related Desynchronization)</td>
                    <td style="padding:4px 12px;">Negative contrast in the 13&ndash;30&nbsp;Hz beta band &mdash;
                        reduction of beta-band power during stimulation relative to control.
                        Beta ERD over sensorimotor cortex is a well-documented correlate of
                        somatosensory processing.</td>
                </tr>
                </table>
                <br>
                Both use Cohen&rsquo;s d&nbsp;&ge;&nbsp;0.5 (medium effect) as the detection threshold.
                <br><br>
                <strong>Column guide:</strong><br>
                &bull; <strong>Contrast (stim)</strong> &mdash; Isolated neural power at
                    {stim_freq:.0f}&plusmn;2&nbsp;Hz during stimulation window<br>
                &bull; <strong>Stim&minus;Base</strong> &mdash; Net change vs baseline; primary effect measure<br>
                &bull; <strong>SSSEP d / SSSEP</strong> &mdash; Effect size and detection for entrainment<br>
                &bull; <strong>FOT / IFNFN</strong> &mdash; Individual condition power
                    (FOT = neural+EM; IFNFN = EM only)<br>
                &bull; <strong>EM Canc.</strong> &mdash; Fraction of FOT that was EM artifact
                    (only shown when both conditions show enhancement)<br>
                &bull; <strong>Beta / Beta d / Beta ERD</strong> &mdash; Beta-band contrast,
                    effect size, and detection for desynchronization
            </div>

            <table style="border-collapse:collapse;width:100%;margin:20px 0;font-size:0.82em;">
                <thead>
                    <tr style="background:#1E293B;color:white;">
                        <th style="padding:8px;text-align:left;" rowspan="2">Channel</th>
                        <th style="padding:8px;text-align:left;" rowspan="2">Region</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #60A5FA;"
                            colspan="4">Entrainment @ {stim_freq:.0f} Hz (SSSEP)</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #94A3B8;"
                            colspan="3">EM Decomposition</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #34D399;"
                            colspan="3">Beta Desynchronization (13&ndash;30 Hz)</th>
                    </tr>
                    <tr style="background:#334155;color:#E2E8F0;font-size:0.9em;">
                        <th style="padding:6px;text-align:right;">Contrast</th>
                        <th style="padding:6px;text-align:right;">Stim&minus;Base</th>
                        <th style="padding:6px;text-align:right;">d</th>
                        <th style="padding:6px;text-align:center;">Det.</th>
                        <th style="padding:6px;text-align:right;">FOT</th>
                        <th style="padding:6px;text-align:right;">IFNFN</th>
                        <th style="padding:6px;text-align:right;">EM%</th>
                        <th style="padding:6px;text-align:right;">Contrast</th>
                        <th style="padding:6px;text-align:right;">d</th>
                        <th style="padding:6px;text-align:center;">Det.</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(table_rows)}
                </tbody>
            </table>

            <div style="background:#f0fdf4;border-left:4px solid #10B981;
                         padding:15px;border-radius:4px;margin:15px 0;">
                <strong>EM artifact cancellation:</strong> {em_summary}
            </div>

            <div style="background:#FFFBEB;border-left:4px solid #F59E0B;
                         padding:15px;border-radius:4px;margin:15px 0;">
                <strong>Interpretation guide:</strong><br>
                &bull; <strong>SSSEP + Beta ERD on somatosensory channels</strong>:
                    Both cortical entrainment at the stimulation frequency and beta-band
                    desynchronization are present. This pattern is consistent with
                    vibrotactile input engaging somatosensory cortex and modulating
                    ongoing beta oscillations.<br>
                &bull; <strong>SSSEP only (no Beta ERD)</strong>:
                    Cortical entrainment is present but beta oscillations are not
                    significantly modulated. Beta ERD may depend on stimulation duration,
                    frequency, or the individual&rsquo;s baseline beta power.<br>
                &bull; <strong>Beta ERD only (no SSSEP)</strong>:
                    Beta desynchronization is observed without frequency-specific
                    entrainment. The beta modulation may be driven by broadband
                    somatosensory input rather than narrowband entrainment.<br>
                &bull; <strong>Neither detected</strong>:
                    No cortical response exceeds the detection threshold.
                    Factors to consider: trial count (minimum ~30 per condition),
                    electrode impedance, stimulation amplitude, and participant state.<br>
                &bull; <strong>Effects on non-somatosensory channels</strong>:
                    May reflect volume conduction, widespread cortical activation, or
                    residual artifact. Spatial specificity should be considered when
                    interpreting these findings.
            </div>
        </div>
        """
        return section_html

    def validate(self) -> Optional[str]:
        """
        Validates current state of the Analyzer.

        Returns None on success, or a string describing the first error found.
        Validates against the configured pick_channels (not a hardcoded set)
        so it works with any montage (freg8, freg9, kullab, etc.).
        """
        if self.tfr_fot is None:
            return "FOT TFR is None"
        if self.tfr_ifnfn is None:
            return "IFNFN TFR is None"
        if self.tfr_contrast is None:
            return "Contrast TFR is None"

        # Check shapes match
        if self.tfr_fot.data.shape != self.tfr_ifnfn.data.shape:
            return f"Shape mismatch: FOT {self.tfr_fot.data.shape} vs IFNFN {self.tfr_ifnfn.data.shape}"
        if self.tfr_fot.data.shape != self.tfr_contrast.data.shape:
            return "Contrast shape doesn't match conditions"

        # Check channels match the configured picks (if specified)
        if self.cfg.pick_channels:
            expected_chs = set(self.cfg.pick_channels)
            actual_chs = set(self.tfr_fot.ch_names)
            if actual_chs != expected_chs:
                return f"Channel mismatch: expected {expected_chs}, got {actual_chs}"

        # Check FOT and IFNFN have identical channel sets
        if set(self.tfr_fot.ch_names) != set(self.tfr_ifnfn.ch_names):
            return (
                f"FOT/IFNFN channel mismatch: "
                f"{self.tfr_fot.ch_names} vs {self.tfr_ifnfn.ch_names}"
            )

        return None
