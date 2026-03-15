"""
tfr_contrast.py — Time–Frequency Contrast Analysis (Section 9 Pipeline)

Implements the four-step analysis pipeline from the EEG Measurement Protocol
for Tactile Stimulation with Strong Electromagnetic Noise:

    Step 1: Full Time–Frequency Transform (Morlet wavelets)
    Step 2: Epoching around triggers with safety margins
    Step 3: Baseline normalization (dB / log-ratio / percent)
    Step 4: Condition contrasting  (FOT − IFNFN)

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
import argparse
import sys
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
# Marker definitions — must match the recording module (sweep.py)
# ---------------------------------------------------------------------------
# Condition-aware markers (new)
MARKER_FOT_STIM_ON   = 101   # Finger-On-Tactor: stimulation onset
MARKER_FOT_STIM_OFF  = 111   # NFOT: stimulation offset
MARKER_FOT_REST      = 100   # FOT: inter-trial rest
MARKER_IFNFN_STIM_ON = 201   # In-Field-ot-Feeling-Nipple: stim onset
MARKER_IFNFN_STIM_OFF = 211  # IFNFN: stimulation offset
MARKER_IFNFN_REST    = 200   # IFNFN: inter-trial rest

# Legacy single-condition markers (backward compatibility)
MARKER_STIM_ON       = 1
MARKER_STIM_OFF      = 11
MARKER_REST          = 0

MARKER_MAP: Dict[float, str] = {
    # New condition-aware markers
    100.0:  "FOT_Rest [100]",
    101.0:  "FOT_Stim_ON [101]",
    111.0:  "FOT_Stim_OFF [111]",
    200.0:  "IFNFN_Rest [200]",
    201.0:  "IFNFN_Stim_ON [201]",
    211.0:  "IFNFN_Stim_OFF [211]",
    # Legacy markers (single-condition recordings)
    0.0:    "Stimulation READY [0]",
    1.0:    "Stimulation ON [1]",
    11.0:   "Stimulation OFF [11]",
    3.0:    "Baseline_VHP_OFF [3]",
    33.0:   "Baseline_VHP_ON [33]",
    31.0:   "Baseline_NoContact [31]",
    333.0:  "Baseline_PreSweep [333]",
}


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------
@dataclass
class TFRContrastConfig:
    """All parameters for the TFR contrast pipeline."""

    # --- Channel / montage ---
    # `channels` must list ALL 32 CSV columns in order, matching the
    # physical FreeEEG32 wiring.  "NC" = Not Connected (dropped after load).
    # This default mirrors config/montages/freg8.yaml exactly.
    montage_profile: str = "freg8"
    channels: List[str] = field(default_factory=lambda: [
        "T7",  "C3",  "NC",  "NC",  "T8",  "FC4", "NC",  "NC",   # CH1-8
        "FC3", "C4",  "NC",  "NC",  "CP3", "CP4", "NC",  "NC",   # CH9-16
        "NC",  "NC",  "NC",  "NC",  "NC",  "NC",  "NC",  "NC",   # CH17-24
        "NC",  "NC",  "NC",  "NC",  "NC",  "NC",  "NC",  "NC",   # CH25-32
    ])
    montage: str = "standard_1020"
    # `pick_channels` selects only the connected electrodes for analysis.
    pick_channels: Optional[List[str]] = field(default_factory=lambda: [
        "T7", "C3", "T8", "FC4", "FC3", "C4", "CP3", "CP4"
    ])

    # --- TFR parameters ---
    tfr_method: str = "morlet"
    tfr_fmin: float = 1.0
    tfr_fmax: float = 60.0
    tfr_fstep: float = 1.0
    n_cycles_mode: str = "adaptive"    # "adaptive" = freqs/2, or fixed int
    n_cycles_fixed: float = 7.0
    tfr_decim: int = 1                 # decimation factor (auto if 0)

    # --- Epoching windows (seconds, relative to STIM-ON) ---
    epoch_tmin: float = -1.5           # start of epoch (must include baseline)
    epoch_tmax: float = 5.0            # end of epoch
    baseline_tmin: float = -1.0        # baseline window start
    baseline_tmax: float = -0.5        # baseline window end
    stim_window_tmin: float = 0.5      # stimulation analysis window start
    stim_window_tmax: float = 4.0      # stimulation analysis window end

    # --- Baseline normalization ---
    baseline_mode: str = "logratio"    # "logratio", "ratio", "percent", "zscore"

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


# ---------------------------------------------------------------------------
# Helper: load CSV into MNE Raw
# ---------------------------------------------------------------------------
EEG_CHANNELS_COUNT = 32


def load_csv_to_raw(
    csv_path: Path,
    channels: List[str],
    montage_name: str,
) -> mne.io.RawArray:
    """
    Load a sweep CSV (timestamp, 32×EEG, marker) into an MNE RawArray
    with annotations derived from markers.
    """
    df = pd.read_csv(csv_path, header=None)

    timestamps = df.iloc[:, 0].values
    eeg_data = df.iloc[:, 1:EEG_CHANNELS_COUNT + 1].values.T  # (ch, samples)
    markers = df.iloc[:, EEG_CHANNELS_COUNT + 1].values

    # Sampling frequency from median ISI
    if len(timestamps) > 1:
        sfreq = 1.0 / np.median(np.diff(timestamps))
    else:
        sfreq = 512.0

    # Channel names — pad or trim to 32, deduplicate "NC" entries
    ch_names = list(channels)
    if len(ch_names) < EEG_CHANNELS_COUNT:
        ch_names += [f"NC{i}" for i in range(len(ch_names), EEG_CHANNELS_COUNT)]
    ch_names = ch_names[:EEG_CHANNELS_COUNT]

    # MNE requires unique channel names — rename duplicate "NC" entries
    nc_counter = 0
    for i, name in enumerate(ch_names):
        if name == "NC":
            ch_names[i] = f"NC{nc_counter}"
            nc_counter += 1

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(eeg_data, info, verbose=False)

    # Drop NC channels
    nc_chans = [ch for ch in raw.ch_names if ch.startswith("NC")]
    if nc_chans:
        raw.drop_channels(nc_chans)

    # Set standard montage
    try:
        montage = mne.channels.make_standard_montage(montage_name)
        raw.set_montage(montage, on_missing="warn")
    except Exception as exc:
        logger.warning("Could not apply montage '%s': %s", montage_name, exc)

    # Build annotations from marker column
    valid_mask = pd.to_numeric(pd.Series(markers), errors="coerce").notna()
    marker_vals = pd.to_numeric(pd.Series(markers), errors="coerce").values

    if np.any(valid_mask):
        idxs = np.where(valid_mask)[0]
        onsets = timestamps[idxs] - timestamps[0]
        descriptions = [
            MARKER_MAP.get(float(marker_vals[i]), f"Event_{int(marker_vals[i])}")
            for i in idxs
        ]
        annots = mne.Annotations(
            onset=onsets,
            duration=[0.01] * len(onsets),
            description=descriptions,
        )
        raw.set_annotations(annots)
        logger.info(
            "Loaded %s: %d samples @ %.1f Hz, %d annotations",
            csv_path.name, raw.n_times, sfreq, len(annots),
        )
    else:
        logger.info(
            "Loaded %s: %d samples @ %.1f Hz (no markers found)",
            csv_path.name, raw.n_times, sfreq,
        )

    return raw


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
        self.tfr_fot = None      # AverageTFR after baseline norm
        self.tfr_ifnfn = None
        self.tfr_contrast = None # FOT − IFNFN

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def load_two_files(self, fot_path: Path, ifnfn_path: Path) -> None:
        """Load separate FOT and IFNFN recordings (fully-blocked protocol)."""
        logger.info("Loading FOT file: %s", fot_path)
        self.raw_fot = load_csv_to_raw(
            fot_path, self.cfg.channels, self.cfg.montage
        )
        logger.info("Loading IFNFN file: %s", ifnfn_path)
        self.raw_ifnfn = load_csv_to_raw(
            ifnfn_path, self.cfg.channels, self.cfg.montage
        )
        self._apply_picks(self.raw_fot)
        self._apply_picks(self.raw_ifnfn)

    def load_single_file(self, csv_path: Path) -> None:
        """
        Load a single CSV that contains interleaved FOT/IFNFN trials
        (alternating or randomized protocol).  Condition is determined
        by marker codes 101/201.
        """
        raw = load_csv_to_raw(csv_path, self.cfg.channels, self.cfg.montage)
        self._apply_picks(raw)
        # Both conditions share the same Raw — epoching separates them
        self.raw_fot = raw
        self.raw_ifnfn = raw

    def _apply_picks(self, raw: mne.io.RawArray) -> None:
        """Optionally sub-select channels."""
        picks = self.cfg.pick_channels
        if picks:
            valid = [ch for ch in picks if ch in raw.ch_names]
            if valid:
                raw.pick_channels(valid)
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
            self.cfg.fmin, self.cfg.fmax, self.cfg.notch_freqs,
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
            logger.error("Raw data is None — cannot compute TFR.")
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
                    event_name, self.cfg.legacy_stim_event,
                )
                event_name = self.cfg.legacy_stim_event
            else:
                logger.error(
                    "Event '%s' not found. Available: %s",
                    event_name, list(event_id.keys()),
                )
                return None

        target_id = event_id[event_name]
        n_trials = np.sum(events[:, 2] == target_id)
        logger.info(
            "Condition '%s': %d trials found.", event_name, n_trials
        )
        if n_trials == 0:
            return None

        # --- Step 2: Epoching ---
        epochs = mne.Epochs(
            raw,
            events,
            event_id=target_id,
            tmin=self.cfg.epoch_tmin,
            tmax=self.cfg.epoch_tmax,
            baseline=None,            # We apply TFR-level baseline later
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
            decim = max(1, int(raw.info["sfreq"] / 200))

        power = epochs.compute_tfr(
            method=self.cfg.tfr_method,
            freqs=freqs,
            n_cycles=n_cycles,
            decim=decim,
            return_itc=False,
            n_jobs=1,
            verbose=False,
        )

        # --- Step 3: Baseline normalization on the TFR ---
        power.apply_baseline(
            baseline=(self.cfg.baseline_tmin, self.cfg.baseline_tmax),
            mode=self.cfg.baseline_mode,
            verbose=False,
        )

        # Average across all epochs → AverageTFR (channels × freqs × times)
        power = power.average()

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
            logger.error("No data loaded. Call load_two_files() or load_single_file() first.")
            return False

        # Preprocess
        raw_fot_clean = self.preprocess(self.raw_fot)
        raw_ifnfn_clean = self.preprocess(self.raw_ifnfn)

        # Steps 1–3 per condition
        self.tfr_fot = self.compute_condition_tfr(
            raw_fot_clean, self.cfg.fot_event
        )
        self.tfr_ifnfn = self.compute_condition_tfr(
            raw_ifnfn_clean, self.cfg.ifnfn_event
        )

        if self.tfr_fot is None or self.tfr_ifnfn is None:
            logger.error(
                "Pipeline incomplete — could not compute TFR for both conditions."
            )
            return False

        # Step 4: Contrast = FOT − IFNFN
        self.tfr_contrast = self.tfr_fot.copy()
        self.tfr_contrast._data = self.tfr_fot.data - self.tfr_ifnfn.data
        logger.info("✅ Contrast TFR computed (FOT − IFNFN).")
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
            self.tfr_fot = self.compute_condition_tfr(
                raw_clean, self.cfg.fot_event
            )
            return self.tfr_fot is not None
        else:
            raw_clean = self.preprocess(self.raw_ifnfn)
            self.tfr_ifnfn = self.compute_condition_tfr(
                raw_clean, self.cfg.ifnfn_event
            )
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
            ax.axvspan(bl_min, bl_max, color="#3B82F6", alpha=0.08,
                       label="_baseline")
            # Excluded zone (red tint)
            ax.axvspan(bl_max, stim_min, color="#EF4444", alpha=0.06,
                       label="_excluded")
            # Stimulation window (green tint)
            ax.axvspan(stim_min, stim_max, color="#10B981", alpha=0.06,
                       label="_stim")

            # Stim ON marker line
            ax.axvline(0, color="#EF4444", linestyle="--", linewidth=1.2, alpha=0.8)

            # Labels at top of plot
            ylim = ax.get_ylim()
            label_y = ylim[1]  # top of axis
            label_kwargs = dict(
                fontsize=7, fontweight="bold", ha="center", va="bottom",
                alpha=0.7, clip_on=True,
            )
            mid_bl = (bl_min + bl_max) / 2
            mid_ex = (bl_max + stim_min) / 2
            mid_st = (stim_min + stim_max) / 2

            ax.text(mid_bl, label_y, "BASELINE", color="#3B82F6", **label_kwargs)
            ax.text(mid_ex, label_y, "EXCL.", color="#EF4444", **label_kwargs)
            ax.text(mid_st, label_y, "STIMULATION", color="#10B981", **label_kwargs)
            ax.text(0, label_y, "STIM ON", color="#EF4444",
                    fontsize=6, ha="center", va="top", alpha=0.6)

    # ------------------------------------------------------------------
    # Visualization helpers
    # ------------------------------------------------------------------
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
        # Show full epoch so baseline and post-stim are visible
        _tmin = tmin or self.cfg.epoch_tmin + 0.1
        _tmax = tmax or self.cfg.epoch_tmax - 0.1

        n_channels = len(tfr.ch_names)
        fig, axes = plt.subplots(
            n_channels, 1,
            figsize=(14, 3.5 * n_channels),
            squeeze=False,
        )

        for idx, ch_name in enumerate(tfr.ch_names):
            ax = axes[idx, 0]
            # Build plot kwargs — vlim replaces vmin/vmax in newer MNE
            plot_kwargs = dict(
                picks=[ch_name],
                baseline=None,          # already applied
                tmin=_tmin,
                tmax=_tmax,
                fmin=_fmin,
                fmax=_fmax,
                axes=ax,
                show=False,
                colorbar=True,
                cmap=cmap,
                verbose=False,
            )
            if vmin is not None and vmax is not None:
                plot_kwargs["vlim"] = (vmin, vmax)
            tfr.plot(**plot_kwargs)
            self._annotate_periods(ax)
            ax.set_title(f"{title} — {ch_name}")

        fig.suptitle(title, fontsize=14, fontweight="bold", y=1.01)
        plt.tight_layout()
        return fig

    def plot_contrast(self, **kwargs) -> Optional[plt.Figure]:
        """Plot the FOT − IFNFN contrast TFR."""
        return self.plot_tfr(
            self.tfr_contrast,
            title="Contrast: FOT − IFNFN (Isolated Neural Response)",
            cmap="RdBu_r",
            **kwargs,
        )

    def plot_both_conditions(
        self,
        channel: Optional[str] = None,
        fmin: Optional[float] = None,
        fmax: Optional[float] = None,
    ) -> Optional[plt.Figure]:
        """Side-by-side FOT / IFNFN / Contrast for one channel."""
        if self.tfr_fot is None or self.tfr_ifnfn is None or self.tfr_contrast is None:
            return None

        ch = channel or self.tfr_fot.ch_names[0]
        _fmin = fmin or self.cfg.tfr_fmin
        _fmax = fmax or self.cfg.tfr_fmax
        # Show full epoch
        _tmin = self.cfg.epoch_tmin + 0.1
        _tmax = self.cfg.epoch_tmax - 0.1

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
                verbose=False,
            )
            self._annotate_periods(ax)
            ax.set_title(label)

        fig.suptitle(
            f"TFR Condition Comparison — {ch}", fontsize=13, fontweight="bold"
        )
        plt.tight_layout()
        return fig

    def plot_stim_band_timecourse(
        self,
        freq_band: Tuple[float, float] = (20.0, 25.0),
        channel: Optional[str] = None,
    ) -> Optional[plt.Figure]:
        """
        Plot the time-course of power in a specific frequency band
        for both conditions + contrast.  Useful for seeing the stimulation
        frequency response (e.g. ~22 Hz) evolve over time.
        """
        if self.tfr_fot is None or self.tfr_ifnfn is None:
            return None

        ch = channel or self.tfr_fot.ch_names[0]
        ch_idx_fot = self.tfr_fot.ch_names.index(ch)
        ch_idx_ifnfn = self.tfr_ifnfn.ch_names.index(ch)

        # Frequency indices
        freqs = self.tfr_fot.freqs
        freq_mask = (freqs >= freq_band[0]) & (freqs <= freq_band[1])

        # Extract and average across the frequency band
        fot_data = self.tfr_fot.data[ch_idx_fot, freq_mask, :].mean(axis=0)
        ifnfn_data = self.tfr_ifnfn.data[ch_idx_ifnfn, freq_mask, :].mean(axis=0)
        contrast_data = fot_data - ifnfn_data
        times = self.tfr_fot.times

        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # Top: both conditions
        axes[0].plot(times, fot_data, color="#2ecc71", label="FOT", linewidth=1.5)
        axes[0].plot(times, ifnfn_data, color="#e74c3c", label="IFNFN", linewidth=1.5)
        axes[0].axhline(0, color="gray", linestyle=":", alpha=0.3)
        axes[0].set_ylabel(f"Power ({self.cfg.baseline_mode})")
        axes[0].set_title(
            f"{ch} — {freq_band[0]:.0f}-{freq_band[1]:.0f} Hz Band Power"
        )
        axes[0].legend()
        axes[0].grid(True, alpha=0.2)
        self._annotate_periods(axes[0])

        # Bottom: contrast
        axes[1].plot(times, contrast_data, color="#3498db", linewidth=2)
        axes[1].fill_between(
            times, contrast_data, 0,
            where=contrast_data > 0, color="#3498db", alpha=0.15,
        )
        axes[1].fill_between(
            times, contrast_data, 0,
            where=contrast_data < 0, color="#e74c3c", alpha=0.15,
        )
        axes[1].axhline(0, color="gray", linestyle=":", alpha=0.5)
        axes[1].set_xlabel("Time (s)")
        axes[1].set_ylabel(f"Delta Power ({self.cfg.baseline_mode})")
        axes[1].set_title("Contrast (FOT - IFNFN): Isolated Neural Response")
        axes[1].grid(True, alpha=0.2)
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
        out = Path(output_dir or self.cfg.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        img_dir = out / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        png_dir = out / "png"
        png_dir.mkdir(parents=True, exist_ok=True)
        csv_dir = out / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)

        sections: List[str] = []
        plot_counter = 0

        def _save_fig(fig, name: str, dpi_html: int = 120, dpi_png: int = 200):
            """Save figure to both img/ (for HTML) and png/ (standalone)."""
            nonlocal plot_counter
            plot_counter += 1
            # Sanitize name for filesystem
            safe = name.replace(" ", "_").replace("/", "-").replace(":", "")
            safe = f"{plot_counter:02d}_{safe}"

            # HTML-embedded version (smaller)
            html_path = img_dir / f"{safe}.png"
            fig.savefig(html_path, bbox_inches="tight", dpi=dpi_html)

            # Standalone high-res version
            png_path = png_dir / f"{safe}.png"
            fig.savefig(png_path, bbox_inches="tight", dpi=dpi_png)

            plt.close(fig)
            return f"img/{safe}.png"

        def _add(title: str, fig=None, text: str = "", caption: str = "",
                 fig_name: str = ""):
            block = f"<div class='section'><h2>{html.escape(title)}</h2>"
            if text:
                block += f"<p>{html.escape(text)}</p>"
            if fig is not None:
                rel_path = _save_fig(fig, fig_name or title)
                block += f'<img src="{rel_path}" class="plot">'
                if caption:
                    block += f'<p class="caption">{html.escape(caption)}</p>'
            block += "</div>"
            sections.append(block)

        # --- Export TFR data as CSV ---
        self._export_csv(csv_dir)

        # --- Pipeline info ---
        info_text = (
            f"Baseline mode: {self.cfg.baseline_mode} | "
            f"Baseline window: [{self.cfg.baseline_tmin}, {self.cfg.baseline_tmax}]s | "
            f"Stim window: [{self.cfg.stim_window_tmin}, {self.cfg.stim_window_tmax}]s | "
            f"Frequencies: {self.cfg.tfr_fmin} - {self.cfg.tfr_fmax} Hz"
        )
        n_fot = "N/A"
        n_ifnfn = "N/A"
        if self.tfr_fot is not None:
            n_fot = str(getattr(self.tfr_fot, 'nave', '?'))
        if self.tfr_ifnfn is not None:
            n_ifnfn = str(getattr(self.tfr_ifnfn, 'nave', '?'))
        info_text += f" | FOT trials: {n_fot} | IFNFN trials: {n_ifnfn}"
        _add("Pipeline Configuration", text=info_text)

        # --- Individual condition TFRs ---
        if self.tfr_fot is not None:
            fig = self.plot_tfr(self.tfr_fot, title="FOT (Tactile + EM Noise)")
            _add(
                "Step 1-3: FOT Condition TFR",
                fig=fig,
                fig_name="TFR_FOT",
                caption="Morlet TFR, baseline-normalized. Contains both neural response and EM artifact.",
            )
        if self.tfr_ifnfn is not None:
            fig = self.plot_tfr(self.tfr_ifnfn, title="IFNFN (EM Noise Only)")
            _add(
                "Step 1-3: IFNFN Condition TFR",
                fig=fig,
                fig_name="TFR_IFNFN",
                caption="Control condition - same EM noise, no tactile stimulation.",
            )

        # --- Contrast ---
        if self.tfr_contrast is not None:
            fig = self.plot_contrast()
            _add(
                "Step 4: Contrast (FOT - IFNFN)",
                fig=fig,
                fig_name="TFR_Contrast",
                caption="Isolated neural response: EM noise cancelled by subtraction.",
            )

            # Side-by-side per channel
            for ch in (self.tfr_fot.ch_names if self.tfr_fot else []):
                fig_comp = self.plot_both_conditions(channel=ch)
                if fig_comp:
                    _add(
                        f"Condition Comparison - {ch}",
                        fig=fig_comp,
                        fig_name=f"Comparison_{ch}",
                        caption=f"Left: FOT | Center: IFNFN | Right: Contrast for {ch}",
                    )

            # Band time-courses for stimulation-relevant frequencies
            for band_name, band_range in [
                ("Beta_13-30Hz", (13.0, 30.0)),
                ("StimFreq_20-25Hz", (20.0, 25.0)),
                ("Gamma_30-45Hz", (30.0, 45.0)),
            ]:
                for ch in (self.tfr_fot.ch_names if self.tfr_fot else []):
                    fig_tc = self.plot_stim_band_timecourse(
                        freq_band=band_range, channel=ch
                    )
                    if fig_tc:
                        _add(
                            f"Band Time-Course: {band_name} - {ch}",
                            fig=fig_tc,
                            fig_name=f"Band_{band_name}_{ch}",
                            caption=(
                                f"Top: FOT vs IFNFN power in {band_name}. "
                                f"Bottom: difference = isolated neural modulation."
                            ),
                        )

        # --- Assemble HTML with proper encoding ---
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TFR Contrast Report</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f5f5f5; }}
.container {{ max-width: 1400px; margin: auto; background: white;
              padding: 30px; border-radius: 8px;
              box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
h1 {{ color: #2c3e50; border-bottom: 2px solid #2ecc71; padding-bottom: 10px; }}
h2 {{ color: #27ae60; margin-top: 30px; }}
.section {{ margin: 25px 0; }}
.plot {{ max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; border-radius: 4px; }}
.caption {{ font-style: italic; color: #7f8c8d; text-align: center; margin-bottom: 20px; }}
.info {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #2ecc71;
         border-radius: 4px; margin: 15px 0; font-size: 0.9em; }}
.footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee;
           color: #bbb; font-size: 0.8em; text-align: center; }}
</style>
</head>
<body>
<div class="container">
<h1>TFR Contrast Analysis &mdash; Section 9 Pipeline</h1>
<p><em>FOT &minus; IFNFN contrast isolates the neural response to tactile stimulation
under strong electromagnetic noise.</em></p>
<div class="info">
Output directories: <code>png/</code> (standalone high-res plots) |
<code>csv/</code> (TFR numerical data) |
<code>img/</code> (report images)
</div>
{"".join(sections)}
<div class="footer">
Generated by EEGsuite tfr_contrast.py | {plot_counter} plots |
{len(list(csv_dir.glob('*.csv')))} CSV files exported
</div>
</div>
</body>
</html>"""

        report_path = out / filename
        report_path.write_text(html_content, encoding="utf-8")
        logger.info(
            "Report saved: %s (%d plots in png/, %d CSVs in csv/)",
            report_path, plot_counter, len(list(csv_dir.glob("*.csv"))),
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
            stim_mask = (times >= self.cfg.stim_window_tmin) & \
                        (times <= self.cfg.stim_window_tmax)

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
            logger.info("Exported %s (per-channel, %d files)", name,
                        len(tfr.ch_names))

        # Frequency profiles (compact: one row per channel)
        _save_band_avg(self.tfr_fot, "tfr_fot_stim_avg")
        _save_band_avg(self.tfr_ifnfn, "tfr_ifnfn_stim_avg")
        _save_band_avg(self.tfr_contrast, "tfr_contrast_stim_avg")

        # Full time-frequency matrices (one file per channel)
        _save_full(self.tfr_fot, "tfr_fot_full")
        _save_full(self.tfr_ifnfn, "tfr_ifnfn_full")
        _save_full(self.tfr_contrast, "tfr_contrast_full")

    def validate(self) -> str:
        """Validates current state of Analyzer."""
        # Check that TFR objects exist
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

        # Check that channels are correct (should be picked channels only)
        expected_chs = {"T7", "C3", "T8", "FC4", "FC3", "C4", "CP3", "CP4"}
        actual_chs = set(self.tfr_fot.ch_names)
        if actual_chs != expected_chs:
            return f"Channel mismatch: expected {expected_chs}, got {actual_chs}"

        return None




# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="TFR Contrast Analysis (Section 9 Pipeline)"
    )
    parser.add_argument(
        "--fot", type=Path, required=True,
        help="CSV file for FOT condition",
    )
    parser.add_argument(
        "--ifnfn", type=Path, required=True,
        help="CSV file for IFNFN condition",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Analysis YAML config (optional)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports"),
        help="Output directory for report",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Build config
    if args.config and args.config.exists():
        import yaml
        with open(args.config) as f:
            cfg = TFRContrastConfig.from_yaml(yaml.safe_load(f))
    else:
        cfg = TFRContrastConfig()

    cfg.output_dir = str(args.output)

    # Run pipeline
    analyzer = TFRContrastAnalyzer(cfg)
    analyzer.load_two_files(args.fot, args.ifnfn)

    if analyzer.run_pipeline():
        report = analyzer.generate_report()
        print(f"\n✅ Report: {report}")
    else:
        print("\n❌ Pipeline failed. Check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
