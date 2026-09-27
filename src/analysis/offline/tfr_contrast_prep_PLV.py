"""
tfr_contrast_prep_PLV.py - Advanced PREP+PLV+SSSEP Analysis (Section 9 Variant)

Implements an alternative Section 9 pipeline using robust PREP preprocessing
and Phase Locking Value (PLV) / Steady-State Somatosensory Evoked Potential (SSSEP)
metrics for neural response characterization.

    Step 1: PREP-based robust preprocessing (RANSAC channel interpolation)
    Step 2: Epoching around triggers with safety margins
    Step 3: Time-Frequency Transform (Morlet wavelets)
    Step 4: Phase Locking Value (PLV) analysis
    Step 5: SSSEP SNR computation

Usage (standalone):
    python -m src.analysis.offline.tfr_contrast_prep_PLV \\
        --fot <path> --ifnfn <path> --config <yaml> --output <dir>

MEMORY NOTE:
    This script requires ~4-6 GB free RAM for typical EEG recordings.
    Uses lazy imports to minimize startup memory footprint.
"""

import logging
import gc
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# Minimal initial imports (lazy-load heavy ones)
logger = logging.getLogger(__name__)

# ============================================================================
# DETERMINISM MARKER
# ============================================================================
RANDOM_SEED: int = 42

# Module-level imports (will be populated by _import_scientific_stack)
np = None
mne = None
plt = None
tfr_array_morlet = None
PrepPipeline = None


# ============================================================================
# LAZY IMPORTS - Deferred until main() is called
# ============================================================================

def _import_scientific_stack() -> tuple:
    """
    Lazy import of heavy scientific libraries.
    
    This defers loading scipy/mne/numpy until they're actually needed,
    reducing startup memory footprint on constrained systems.
    
    Returns:
        (numpy, mne, plt, tfr_array_morlet, PrepPipeline)
    """
    global np, mne, plt, tfr_array_morlet, PrepPipeline
    
    import numpy as _np
    import mne as _mne
    import matplotlib.pyplot as _plt
    from mne.time_frequency import tfr_array_morlet as _tfr
    from pyprep.prep_pipeline import PrepPipeline as _prep
    
    np = _np
    mne = _mne
    plt = _plt
    tfr_array_morlet = _tfr
    PrepPipeline = _prep
    
    return np, mne, plt, tfr_array_morlet, PrepPipeline


# ============================================================================
# EVENT MARKERS
# ============================================================================
MARKER_FOT_STIM_ON = 101
MARKER_IFNFN_STIM_ON = 201
MARKER_STIM_ON = 1


# ============================================================================
# SIMPLE WRAPPER FUNCTION - Main analysis entry point
# ============================================================================

def run_prep_plv_analysis(fot_path: Path, ifnfn_path: Path, 
                          config_path: Optional[Path] = None,
                          output_dir: Optional[Path] = None,
                          verbose: bool = False) -> bool:
    """
    Execute PREP+PLV+SSSEP analysis.
    
    This function imports all heavy libraries only when called,
    allowing the script to be imported without exhausting memory.
    
    Args:
        fot_path: Path to FOT condition FIF file
        ifnfn_path: Path to IFNFN condition FIF file
        config_path: Path to analysis config YAML
        output_dir: Output directory for report
        verbose: Enable verbose logging
        
    Returns:
        True if successful, False otherwise
    """
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    logger.info("="*70)
    logger.info("PREP+PLV+SSSEP Analysis (Lazy-Load Version)")
    logger.info("="*70)
    logger.info("Importing scientific stack (this may take a moment)...")
    
    try:
        np, mne, plt, tfr_array_morlet, PrepPipeline = _import_scientific_stack()
    except MemoryError as e:
        logger.error(
            "Failed to import libraries due to memory constraints: %s\n"
            "Your system does not have enough RAM for this analysis.\n"
            "Try: 1) Close other applications\n"
            "     2) Increase pagefile size\n"
            "     3) Use tfr_contrast.py (less memory intensive)",
            e
        )
        return False
    except Exception as e:
        logger.error("Failed to import libraries: %s", e, exc_info=True)
        return False
    
    logger.info("Scientific stack loaded successfully")
    
    # Validate inputs
    if not fot_path.exists():
        logger.error("FOT file not found: %s", fot_path)
        return False
    if not ifnfn_path.exists():
        logger.error("IFNFN file not found: %s", ifnfn_path)
        return False
    
    output_dir = Path(output_dir or "reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Loading configuration...")
    
    # Load config
    config = {}
    if config_path and config_path.exists():
        try:
            import yaml
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
            logger.info("Loaded config from %s", config_path)
        except Exception as e:
            logger.warning("Could not load config: %s", e)
    
    logger.info("Loading FOT file...")
    try:
        raw_fot = mne.io.read_raw_fif(str(fot_path), preload=True)
        raw_fot._data = raw_fot._data.astype(np.float32)
        logger.info("FOT loaded: %d channels, %.1f seconds",
                   raw_fot.info['nchan'], raw_fot.times[-1])
    except Exception as e:
        logger.error("Failed to load FOT file: %s", e, exc_info=True)
        return False
    
    logger.info("Loading IFNFN file...")
    try:
        raw_ifnfn = mne.io.read_raw_fif(str(ifnfn_path), preload=True)
        raw_ifnfn._data = raw_ifnfn._data.astype(np.float32)
        logger.info("IFNFN loaded: %d channels, %.1f seconds",
                   raw_ifnfn.info['nchan'], raw_ifnfn.times[-1])
    except Exception as e:
        logger.error("Failed to load IFNFN file: %s", e, exc_info=True)
        return False
    
    # Instantiate analyzer
    logger.info("Instantiating PrepPLVAnalyzer...")
    analyzer_config = PrepPLVConfig.from_yaml(config)
    analyzer_config.output_dir = str(output_dir)
    analyzer = PrepPLVAnalyzer(analyzer_config)
    
    # Load data into analyzer
    analyzer.raw_fot = raw_fot
    analyzer.raw_ifnfn = raw_ifnfn
    
    # Apply montage if specified in config
    if config_path and config_path.exists():
        try:
            montage_dir = config_path.parent / "montages"
            montage_file = montage_dir / f"{analyzer_config.montage_profile}.yaml"
            if montage_file.exists():
                analyzer_config.apply_montage_yaml(montage_file)
        except Exception as e:
            logger.warning("Could not apply montage: %s", e)
    
    # Run analysis pipeline
    logger.info("Running PREP+PLV+SSSEP pipeline...")
    pipeline_success = analyzer.run_pipeline()
    if not pipeline_success:
        logger.error("Pipeline execution failed")
        return False
    
    # Validate results
    validation_error = analyzer.validate()
    if validation_error:
        logger.error("Validation failed: %s", validation_error)
        return False
    
    # Generate report
    try:
        report_path = analyzer.generate_report(output_dir)
        logger.info("Report generated: %s", report_path)
    except Exception as e:
        logger.warning("Could not generate report: %s", e)
    
    logger.info("Analysis complete (PREP+PLV+SSSEP pipeline finished)")
    
    return True


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="PREP+PLV+SSSEP Analysis (Lazy-Load Version)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--fot",
        type=Path,
        required=True,
        help="MNE FIF file for FOT (Finger-On-Tactor) condition",
    )
    parser.add_argument(
        "--ifnfn",
        type=Path,
        required=True,
        help="MNE FIF file for IFNFN condition",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Analysis config YAML file (optional)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports"),
        help="Output directory for report (default: reports/)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    success = run_prep_plv_analysis(
        args.fot,
        args.ifnfn,
        args.config,
        args.output,
        args.verbose,
    )

    sys.exit(0 if success else 1)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class PrepPLVConfig:
    """Configuration for PREP+PLV+SSSEP pipeline."""

    # Montage / channel selection
    montage_profile: str = "freg8"
    channels: List[str] = field(default_factory=list)
    montage: str = "standard_1020"
    pick_channels: Optional[List[str]] = None
    virtual_channels: Optional[Dict[str, Any]] = None

    # PREP preprocessing parameters
    prep_ransac: bool = True
    prep_channel_wise: bool = True

    # Filtering
    fmin: float = 0.5
    fmax: float = 100.0
    notch_freqs: List[float] = field(default_factory=lambda: [50.0, 100.0])

    # TFR parameters
    tfr_fmin: float = 5.0
    tfr_fmax: float = 60.0
    tfr_fstep: float = 1.0
    n_cycles_mode: str = "adaptive"  # "adaptive" = freqs/2
    n_cycles_fixed: float = 7.0

    # Epoching windows (seconds, relative to STIM-ON)
    epoch_tmin: float = -1.5
    epoch_tmax: float = 5.0
    baseline_tmin: float = -1.0
    baseline_tmax: float = -0.5
    stim_window_tmin: float = 0.5
    stim_window_tmax: float = 5.0

    # Artifact rejection
    reject_p2p: float = 150.0  # µV, peak-to-peak threshold

    # Stimulation frequency
    stim_freq: float = 32.0  # Hz

    # Condition event names
    fot_event: str = "FOT_Stim_ON [101]"
    ifnfn_event: str = "IFNFN_Stim_ON [201]"
    legacy_stim_event: str = "Stimulation ON [1]"

    # Output
    output_dir: str = "reports"

    @classmethod
    def from_yaml(cls, yaml_dict: Dict[str, Any]) -> "PrepPLVConfig":
        """Build config from nested YAML dict, ignoring unknown keys."""
        flat = {}
        for section in yaml_dict.values():
            if isinstance(section, dict):
                flat.update(section)
        flat.update({k: v for k, v in yaml_dict.items()
                     if not isinstance(v, dict)})

        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in flat.items() if k in known_fields}
        return cls(**filtered)

    def apply_montage_yaml(self, montage_path: Path, overwrite: bool = True
                          ) -> None:
        """
        Load a montage YAML and apply its fields to this config.

        Args:
            montage_path: Path to montage YAML file.
            overwrite: If True, overwrite config with montage values.
        """
        try:
            import yaml

            with open(montage_path, "r") as f:
                m = yaml.safe_load(f)

            def _should_set(key: str, current_val: Any,
                           default_val: Any) -> bool:
                if overwrite:
                    return True
                if current_val == default_val:
                    return True
                return False

            if "channels" in m and _should_set("channels",
                                               self.channels, []):
                self.channels = m["channels"]
            if "pick_channels" in m and _should_set(
                "pick_channels", self.pick_channels, None
            ):
                self.pick_channels = m["pick_channels"]
            if "virtual_channels" in m and _should_set(
                "virtual_channels", self.virtual_channels, None
            ):
                self.virtual_channels = m["virtual_channels"]
            if "montage" in m and _should_set("montage",
                                              self.montage, "standard_1020"):
                self.montage = m["montage"]
            if "name" in m and _should_set("name",
                                           self.montage_profile, "freg8"):
                self.montage_profile = m["name"]

            logger.info(
                "Applied montage '%s' from %s: %d channels",
                m.get("name", "?"),
                montage_path.name,
                len(self.channels) if self.channels else 0,
            )
        except Exception as exc:
            logger.warning("Could not load montage YAML %s: %s",
                          montage_path, exc)


# ============================================================================
# CORE ANALYSIS CLASS
# ============================================================================

class PrepPLVAnalyzer:
    """
    PREP+PLV+SSSEP analysis pipeline for Section 9 variant.

    Implements robust preprocessing (PREP with RANSAC channel interpolation)
    followed by Phase Locking Value and Steady-State Somatosensory Evoked
    Potential metrics.
    """

    def __init__(self, config: PrepPLVConfig) -> None:
        """
        Initialize analyzer.

        Args:
            config: PrepPLVConfig dataclass with all pipeline parameters.
        """
        self.cfg = config
        self.raw_fot: Optional[mne.io.RawArray] = None
        self.raw_ifnfn: Optional[mne.io.RawArray] = None
        self.epochs_fot: Optional[mne.Epochs] = None
        self.epochs_ifnfn: Optional[mne.Epochs] = None
        self.tfr_fot: Optional[np.ndarray] = None
        self.tfr_ifnfn: Optional[np.ndarray] = None
        self.plv_fot: Optional[Dict[str, np.ndarray]] = None
        self.plv_ifnfn: Optional[Dict[str, np.ndarray]] = None
        self.sssep_fot: Optional[Dict[str, np.ndarray]] = None
        self.sssep_ifnfn: Optional[Dict[str, np.ndarray]] = None

    # ========================================================================
    # Data loading
    # ========================================================================

    def load_two_files(self, fot_path: Path, ifnfn_path: Path) -> None:
        """
        Load separate FOT and IFNFN recordings (fully-blocked protocol).

        Args:
            fot_path: Path to FOT condition MNE FIF file.
            ifnfn_path: Path to IFNFN condition MNE FIF file.
        """
        logger.info("Loading FOT file: %s", fot_path)
        # Load without preload first to check channels
        raw_fot = mne.io.read_raw_fif(str(fot_path), preload=False)
        
        # Determine which channels to load
        picks_fot = self._get_picks_from_channels(raw_fot.ch_names)
        
        # Select channels if needed, then load data
        if picks_fot is not None:
            raw_fot.pick(picks_fot)
        raw_fot.load_data()
        raw_fot._data = raw_fot._data.astype(np.float32)
        self.raw_fot = raw_fot
        
        logger.info("Loading IFNFN file: %s", ifnfn_path)
        raw_ifnfn = mne.io.read_raw_fif(str(ifnfn_path), preload=False)
        
        picks_ifnfn = self._get_picks_from_channels(raw_ifnfn.ch_names)
        
        # Select channels if needed, then load data
        if picks_ifnfn is not None:
            raw_ifnfn.pick(picks_ifnfn)
        raw_ifnfn.load_data()
        raw_ifnfn._data = raw_ifnfn._data.astype(np.float32)
        self.raw_ifnfn = raw_ifnfn

        # Apply virtual channels (computed from the loaded channels)
        self._apply_virtual_channels(self.raw_fot)
        self._apply_virtual_channels(self.raw_ifnfn)

    def _get_picks_from_channels(self, available_ch_names: List[str]
                                ) -> Optional[List[str]]:
        """
        Determine which channels to load based on config and available channels.

        Args:
            available_ch_names: List of channel names in the raw file.

        Returns:
            List of channel names to pick, or None to load all.
        """
        if not self.cfg.pick_channels:
            logger.info("No channel selection; loading all channels")
            return None

        # Filter to only channels that exist
        available_channels = [
            ch for ch in self.cfg.pick_channels if ch in available_ch_names
        ]

        if not available_channels:
            logger.warning(
                "None of the pick_channels exist in raw data. "
                "Available: %s. Loading all.", available_ch_names
            )
            return None

        missing = set(self.cfg.pick_channels) - set(available_channels)
        if missing:
            logger.info(
                "Skipping %d missing channels: %s",
                len(missing),
                ", ".join(sorted(missing)),
            )

        logger.info("Will load %d channels: %s", len(available_channels),
                   ", ".join(available_channels))

        # Return list of channel names
        return available_channels

    def _apply_virtual_channels(self, raw: mne.io.RawArray) -> None:
        """
        Compute and add virtual channels (e.g., Weighted Laplacian) from config.

        Args:
            raw: MNE Raw object to augment with virtual channels.
        """
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
                            "Ref channel %s for virtual channel %s not found. "
                            "Skipping weight.",
                            ref_ch,
                            name,
                        )

                # Laplacian = Base - (WeightedSum / Divisor)
                virtual_data = base_data - (ref_sum / divisor)

                # Add to Raw object as 'misc' type (not EEG, so doesn't need montage)
                info = mne.create_info([name], raw.info["sfreq"],
                                       ch_types=["misc"])
                new_raw = mne.io.RawArray(
                    virtual_data[np.newaxis, :], info, verbose=False
                )
                raw.add_channels([new_raw], force_update_info=True)
                logger.info("Created virtual channel: %s", name)

            except Exception as e:
                logger.warning("Failed to create virtual channel %s: %s",
                              name, e)

    # ========================================================================
    # PREP preprocessing
    # ========================================================================

    def _preprocess_raw(self, raw: mne.io.RawArray, label: str) -> mne.io.RawArray:
        """
        Apply PREP (Preprocessing Pipeline) robust reference.

        Args:
            raw: MNE Raw object.
            label: Condition label ("FOT" or "IFNFN") for logging.

        Returns:
            Preprocessed Raw object with re-reference and filtering applied.
        """
        logger.info("Running PREP pipeline for %s...", label)

        # Temporarily separate virtual (misc) channels from EEG for PREP
        misc_channels = {}
        eeg_only_raw = raw.copy()
        
        for ch_name in raw.ch_names:
            ch_type = raw.get_channel_types([ch_name])[0]
            if ch_type == "misc":
                misc_channels[ch_name] = raw.get_data(picks=[ch_name])
        
        if misc_channels:
            logger.info("Temporarily removing %d virtual channels for PREP", 
                       len(misc_channels))
            eeg_only_raw.drop_channels(list(misc_channels.keys()))
        
        # Check if we have enough channels for RANSAC (requires 16+)
        n_eeg_channels = len([ch for ch in eeg_only_raw.get_channel_types() 
                              if ch == "eeg"])
        use_ransac = self.cfg.prep_ransac and n_eeg_channels >= 16
        
        if self.cfg.prep_ransac and n_eeg_channels < 16:
            logger.warning(
                "Only %d EEG channels available; RANSAC requires 16+. "
                "Disabling RANSAC and using standard re-referencing.", 
                n_eeg_channels
            )
        
        try:
            montage = mne.channels.make_standard_montage(self.cfg.montage)
        except Exception as e:
            logger.warning("Could not load montage %s: %s. Using default.",
                          self.cfg.montage, e)
            montage = None

        prep_params = {
            "ref_chs": "eeg",
            "reref_chs": "eeg",
            "line_freqs": self.cfg.notch_freqs,
        }

        prep = PrepPipeline(
            eeg_only_raw,
            prep_params,
            montage,
            ransac=use_ransac,
            channel_wise=self.cfg.prep_channel_wise,
            random_state=RANDOM_SEED,
        )

        prep.fit()
        raw_clean = prep.raw

        logger.info("Applying filter: %.1f–%.1f Hz", self.cfg.fmin, self.cfg.fmax)
        raw_clean.filter(self.cfg.fmin, self.cfg.fmax, verbose=False)

        # Re-add virtual channels
        if misc_channels:
            logger.info("Re-adding %d virtual channels after PREP", 
                       len(misc_channels))
            for ch_name, ch_data in misc_channels.items():
                info = mne.create_info([ch_name], raw_clean.info["sfreq"],
                                       ch_types=["misc"])
                virtual_raw = mne.io.RawArray(ch_data, info, verbose=False)
                raw_clean.add_channels([virtual_raw], force_update_info=True)

        return raw_clean

    # ========================================================================
    # Epoching
    # ========================================================================

    def _create_epochs(self, raw: mne.io.RawArray, condition: str
                      ) -> mne.Epochs:
        """
        Extract epochs around stimulation onset.

        Args:
            raw: Preprocessed Raw object.
            condition: Condition label ("FOT" or "IFNFN").

        Returns:
            Epochs object with baseline correction applied.
        """
        logger.info("Creating epochs for %s condition...", condition)

        # Try to get events from annotations first, then from stim channel
        events = None
        try:
            # Convert annotations to events
            # mne.events_from_annotations returns (events, event_id_dict)
            events, events_dict = mne.events_from_annotations(raw, verbose=False)
            logger.info("Converted %d annotations to events: %s", 
                       len(events), list(events_dict.keys()))
        except Exception as e:
            logger.info("Could not convert annotations: %s. Trying find_events...", e)
            try:
                events = mne.find_events(raw, verbose=False)
            except Exception as e2:
                logger.error("Could not find events: %s", e2)
                return None
        
        if events is None or len(events) == 0:
            logger.warning("No events found for %s", condition)
            return None

        logger.info("Found %d events for %s", len(events), condition)

        # Determine event ID based on condition
        if condition == "FOT":
            event_id = MARKER_FOT_STIM_ON
        elif condition == "IFNFN":
            event_id = MARKER_IFNFN_STIM_ON
        else:
            event_id = MARKER_STIM_ON

        # Create epochs - when using annotations, don't filter by event_id
        # since we want all events that were converted
        try:
            epochs = mne.Epochs(
                raw,
                events,
                event_id=None,  # Use all events, don't filter
                tmin=self.cfg.epoch_tmin,
                tmax=self.cfg.epoch_tmax,
                baseline=(self.cfg.baseline_tmin, self.cfg.baseline_tmax),
                preload=True,
                reject=dict(eeg=self.cfg.reject_p2p * 1e-6),
                verbose=False,
            )
        except Exception as e:
            logger.error("Failed to create epochs: %s", e, exc_info=True)
            return None

        n_dropped = len(events) - len(epochs)
        if n_dropped > 0:
            logger.info("Rejected %d/%d epochs for %s (peak-to-peak > %.0f µV)",
                       n_dropped, len(events), condition, self.cfg.reject_p2p)

        return epochs

    # ========================================================================
    # TFR computation
    # ========================================================================

    def _compute_tfr(self, epochs: mne.Epochs, condition: str) -> np.ndarray:
        """
        Compute averaged power Time-Frequency Representation.

        Args:
            epochs: Epochs object.
            condition: Condition label for logging.

        Returns:
            Averaged TFR power array (channels × frequencies × times).
        """
        logger.info("Computing TFR for %s...", condition)

        data = epochs.get_data(picks="all")
        sfreq = epochs.info["sfreq"]

        # Compute frequency range
        freqs = np.arange(self.cfg.tfr_fmin, self.cfg.tfr_fmax,
                         self.cfg.tfr_fstep)

        # Compute n_cycles
        if self.cfg.n_cycles_mode == "adaptive":
            n_cycles = freqs / 2.0
        else:
            n_cycles = self.cfg.n_cycles_fixed

        logger.info("TFR: %d freqs (%.1f–%.1f Hz), %d epochs, adaptive cycles",
                   len(freqs), freqs[0], freqs[-1], len(epochs))

        # Convert to float32 to save memory
        data = data.astype(np.float32)
        
        # Use decim to reduce time resolution and memory usage
        decim = max(1, int(sfreq / 100))  # Target ~100 Hz output
        if decim > 1:
            logger.info("Using decimation factor %d to reduce memory", decim)

        tfr = tfr_array_morlet(
            data,
            sfreq=sfreq,
            freqs=freqs,
            n_cycles=n_cycles,
            output="power",
            decim=decim,
        )

        # Average over trials (channels × freqs × times) to save memory
        # Convert to float32 to reduce memory footprint
        tfr_avg = np.mean(tfr, axis=0).astype(np.float32)

        logger.info("TFR computed: shape=%s, dtype=%s, memory=%.1f MB", 
                   tfr_avg.shape, tfr_avg.dtype,
                   tfr_avg.nbytes / 1e6)

        return tfr_avg

    # ========================================================================
    # PLV (Phase Locking Value)
    # ========================================================================

    def _compute_plv(self, epochs: mne.Epochs, freq: float,
                     condition: str) -> Dict[str, np.ndarray]:
        """
        Compute Phase Locking Value at stimulation frequency.

        Phase Locking Value measures inter-trial phase consistency,
        quantifying how consistent the phase is across trials at a given
        frequency and time point. Values range from 0 (random phase) to
        1 (perfect phase coherence).

        Args:
            epochs: Epochs object.
            freq: Frequency in Hz (typically stim_freq).
            condition: Condition label for logging.

        Returns:
            Dictionary with:
              - "plv": PLV array (channels × times)
              - "n_epochs": Number of trials used
        """
        logger.info("Computing PLV at %.1f Hz for %s...", freq, condition)

        data = epochs.get_data(picks="all")  # trials × channels × times
        sfreq = epochs.info["sfreq"]

        # Compute complex-valued TFR at stimulation frequency
        complex_tfr = tfr_array_morlet(
            data,
            sfreq=sfreq,
            freqs=[freq],
            n_cycles=freq / 2.0,
            output="complex",
        )

        # Extract phase (trials × channels × 1 × times)
        phase = np.angle(complex_tfr)

        # PLV = |mean(exp(i*phase))| over trials
        # Shape: (channels, 1, times)
        plv = np.abs(np.mean(np.exp(1j * phase), axis=0))

        # Squeeze to (channels × times)
        plv = plv.squeeze(axis=1)

        logger.info("PLV computed: shape=%s, range=[%.3f, %.3f]",
                   plv.shape, plv.min(), plv.max())

        return {
            "plv": plv,
            "n_epochs": len(epochs),
        }

    # ========================================================================
    # SSSEP (Steady-State Somatosensory Evoked Potential)
    # ========================================================================

    def _compute_sssep(self, epochs: mne.Epochs, stim_freq: float,
                       condition: str) -> Dict[str, np.ndarray]:
        """
        Compute Steady-State Somatosensory Evoked Potential (SSSEP) metrics.

        SSSEP characterizes the spectral response to sustained stimulation
        at a specific frequency. We compute:
          - Signal: PSD at stim_freq
          - Noise: Mean PSD in ±2 Hz band around stim_freq
          - SNR: 10*log10(Signal/Noise) in dB

        Args:
            epochs: Epochs object.
            stim_freq: Stimulation frequency in Hz.
            condition: Condition label for logging.

        Returns:
            Dictionary with:
              - "signal": Mean PSD at stim_freq (channels,)
              - "snr": SNR in dB (channels,)
              - "freqs": Frequency array (for reference)
        """
        logger.info("Computing SSSEP for %s at %.1f Hz...", condition,
                   stim_freq)

        # Compute Welch PSD on stimulation window
        spectrum = epochs.compute_psd(
            method="welch",
            fmin=stim_freq - 5.0,
            fmax=stim_freq + 5.0,
            tmin=self.cfg.stim_window_tmin,
            tmax=self.cfg.stim_window_tmax,
            picks="all",
            verbose=False,
        )

        psd, freqs = spectrum.get_data(return_freqs=True)
        
        # MNE EpochsSpectrum.get_data() returns (n_epochs, n_channels, n_freqs)
        # We average across epochs first to simplify
        if psd.ndim == 3:
            psd_avg = psd.mean(axis=0)  # Average across epochs -> (channels, freqs)
        else:
            psd_avg = psd  # Already averaged or other format
            
        # Ensure it's 2D (channels, freqs)
        if psd_avg.ndim != 2:
            logger.error("Unexpected PSD shape: %s", psd.shape)
            # Fallback to avoid crash
            return {"signal": np.zeros(len(epochs.ch_names)), 
                    "snr": np.zeros(len(epochs.ch_names)), 
                    "freqs": freqs}

        # Find index closest to stim_freq
        idx_stim = np.argmin(np.abs(freqs - stim_freq))

        # Signal: PSD at stim_freq for each channel
        signal = psd_avg[:, idx_stim]

        # Noise: mean PSD in ±2 Hz band (excluding stim_freq)
        noise_band = (freqs >= stim_freq - 2.0) & (freqs <= stim_freq + 2.0)
        # Create a mask that excludes the stim freq bin
        noise_mask = noise_band.copy()
        noise_mask[idx_stim] = False
        
        if np.any(noise_mask):
            noise = psd_avg[:, noise_mask].mean(axis=1)
        else:
            logger.warning("No noise bins found near %.1f Hz", stim_freq)
            noise = np.full_like(signal, 1e-10)

        # SNR in dB
        snr = 10.0 * np.log10(signal / np.maximum(noise, 1e-10))

        logger.info("SSSEP computed: %d channels, signal_mean=%.2f, snr_mean=%.2f dB",
                   len(snr), signal.mean(), snr.mean())

        return {
            "signal": signal,
            "snr": snr,
            "freqs": freqs,
        }

    # ========================================================================
    # Pipeline execution
    # ========================================================================

    def run_pipeline(self) -> bool:
        """
        Execute the complete PREP+PLV+SSSEP pipeline on both conditions.

        Returns:
            True if successful, False otherwise.
        """
        logger.info("Starting PREP+PLV+SSSEP pipeline...")

        try:
            # ===== FOT CONDITION =====
            logger.info("===== Processing FOT condition =====")
            self.raw_fot = self._preprocess_raw(self.raw_fot, "FOT")
            self.epochs_fot = self._create_epochs(self.raw_fot, "FOT")

            if self.epochs_fot is None or len(self.epochs_fot) == 0:
                logger.error("No valid epochs for FOT condition")
                return False

            self.tfr_fot = self._compute_tfr(self.epochs_fot, "FOT")
            self.plv_fot = self._compute_plv(self.epochs_fot,
                                             self.cfg.stim_freq, "FOT")
            self.sssep_fot = self._compute_sssep(self.epochs_fot,
                                                 self.cfg.stim_freq, "FOT")
            gc.collect()

            # ===== IFNFN CONDITION =====
            logger.info("===== Processing IFNFN condition =====")
            self.raw_ifnfn = self._preprocess_raw(self.raw_ifnfn, "IFNFN")
            self.epochs_ifnfn = self._create_epochs(self.raw_ifnfn, "IFNFN")

            if self.epochs_ifnfn is None or len(self.epochs_ifnfn) == 0:
                logger.error("No valid epochs for IFNFN condition")
                return False

            self.tfr_ifnfn = self._compute_tfr(self.epochs_ifnfn, "IFNFN")
            self.plv_ifnfn = self._compute_plv(self.epochs_ifnfn,
                                               self.cfg.stim_freq, "IFNFN")
            self.sssep_ifnfn = self._compute_sssep(self.epochs_ifnfn,
                                                   self.cfg.stim_freq, "IFNFN")
            gc.collect()

            logger.info("Pipeline completed successfully")
            return True

        except Exception as e:
            logger.error("Pipeline failed: %s", e, exc_info=True)
            return False

    def validate(self) -> Optional[str]:
        """
        Validate that all required outputs were computed.

        Returns:
            Error message if validation fails, None if successful.
        """
        missing = []
        if self.tfr_fot is None:
            missing.append("TFR_FOT")
        if self.tfr_ifnfn is None:
            missing.append("TFR_IFNFN")
        if self.plv_fot is None:
            missing.append("PLV_FOT")
        if self.plv_ifnfn is None:
            missing.append("PLV_IFNFN")
        if self.sssep_fot is None:
            missing.append("SSSEP_FOT")
        if self.sssep_ifnfn is None:
            missing.append("SSSEP_IFNFN")

        if missing:
            return f"Missing outputs: {', '.join(missing)}"

        return None


    # ========================================================================
    # Report generation
    # ========================================================================

    def generate_report(self, output_dir: Path) -> Path:
        """
        Generate HTML report with TFR, PLV, and SSSEP visualizations.

        Args:
            output_dir: Output directory for report.

        Returns:
            Path to generated HTML file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Generating report in %s...", output_dir)

        # Pre-flight validation
        if self.epochs_fot is None or len(self.epochs_fot) == 0:
            logger.error("No valid FOT epochs available for report")
            ch_names = []
        else:
            ch_names = self.epochs_fot.ch_names
        
        n_channels = len(ch_names)
        
        # Check data availability
        data_check = {
            "tfr_fot": self.tfr_fot is not None and self.tfr_fot.size > 0,
            "tfr_ifnfn": self.tfr_ifnfn is not None and self.tfr_ifnfn.size > 0,
            "plv_fot": self.plv_fot is not None,
            "plv_ifnfn": self.plv_ifnfn is not None,
            "sssep_fot": self.sssep_fot is not None,
            "sssep_ifnfn": self.sssep_ifnfn is not None,
        }
        
        logger.info("Data availability: %s", data_check)
        missing_data = [k for k, v in data_check.items() if not v]
        if missing_data:
            logger.warning("Missing data for report sections: %s", 
                          ", ".join(missing_data))

        html_parts = []

        # Header
        html_parts.append("""
        <html>
        <head>
            <title>PREP+PLV+SSSEP Analysis Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1, h2 { color: #333; }
                .section { margin: 30px 0; border: 1px solid #ccc; padding: 15px; }
                img { max-width: 100%; height: auto; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
        <h1>PREP+PLV+SSSEP Analysis Report</h1>
        <p><strong>Method:</strong> This report compares the FOT (Finger On Tactor) condition 
           against the IFNFN (In-Field Not-Feeling Nipple) control. The <strong>Contrast</strong> 
           (FOT &minus; IFNFN) is used to subtract common EM artifacts, isolating the neural response.</p>
        """)

        # Section 1: TFR Comparison
        logger.info("Generating TFR plots for %d channels...", n_channels)
        html_parts.append('<div class="section"><h2>Section 1: Time-Frequency Power (TFR)</h2>')

        if not data_check["tfr_fot"] or not data_check["tfr_ifnfn"]:
            html_parts.append(
                '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                'TFR data not available. Check that pipeline executed successfully.</p>'
            )
            logger.error("Cannot generate TFR plots: tfr_fot=%s, tfr_ifnfn=%s",
                        data_check["tfr_fot"], data_check["tfr_ifnfn"])
        elif n_channels == 0:
            html_parts.append(
                '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                'No channels available. Check epochs data.</p>'
            )
            logger.error("Cannot generate TFR plots: no channels (epochs_fot=%s)", 
                        self.epochs_fot)
        else:
            logger.info("TFR data shapes: fot=%s, ifnfn=%s", 
                       self.tfr_fot.shape if self.tfr_fot is not None else None,
                       self.tfr_ifnfn.shape if self.tfr_ifnfn is not None else None)
            
            # Setup time axis
            sfreq_decim = self.epochs_fot.info["sfreq"] / max(1, int(self.epochs_fot.info["sfreq"] / 100))
            times = np.arange(self.tfr_fot.shape[2]) / sfreq_decim + self.cfg.epoch_tmin
            freqs = np.arange(self.cfg.tfr_fmin, self.cfg.tfr_fmax, self.cfg.tfr_fstep)
            
            # Find baseline indices
            base_idx = (times >= self.cfg.baseline_tmin) & (times <= self.cfg.baseline_tmax)

            for ch_idx, ch_name in enumerate(ch_names):
                try:
                    if ch_idx >= self.tfr_fot.shape[0] or ch_idx >= self.tfr_ifnfn.shape[0]:
                        logger.warning("Channel index %d out of bounds for TFR data", 
                                      ch_idx)
                        continue
                    
                    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

                    def _prepare_plot_data(data_ch):
                        # Baseline normalize (dB)
                        base_pwr = np.mean(data_ch[:, base_idx], axis=1, keepdims=True)
                        # Avoid div by zero
                        base_pwr = np.maximum(base_pwr, 1e-20)
                        return 10 * np.log10(data_ch / base_pwr)

                    tfr_fot_db = _prepare_plot_data(self.tfr_fot[ch_idx])
                    tfr_ifnfn_db = _prepare_plot_data(self.tfr_ifnfn[ch_idx])
                    tfr_contrast_db = tfr_fot_db - tfr_ifnfn_db

                    # Plotting helper
                    def _style_tfr_axis(ax, data, title, vmin_vmax=0.3):
                        im = ax.imshow(
                            data,
                            aspect="auto",
                            origin="lower",
                            cmap="RdBu_r",
                            vmin=-vmin_vmax,
                            vmax=vmin_vmax,
                            extent=[times[0], times[-1], freqs[0], freqs[-1]]
                        )
                        ax.set_title(title)
                        ax.set_xlabel("Time (s)")
                        ax.set_ylabel("Frequency (Hz)")
                        
                        # Add Stim On marker
                        ax.axvline(0, color='red', linestyle='--', alpha=0.6, label='Stim On')
                        
                        # Add Harmonics markers
                        for h in range(1, 6):
                            freq_h = self.cfg.stim_freq * h
                            if freqs[0] <= freq_h <= freqs[-1]:
                                ax.axhline(freq_h, color='orange', linestyle=':', alpha=0.5)
                        
                        plt.colorbar(im, ax=ax, label="Power (dB)")

                    _style_tfr_axis(axes[0], tfr_fot_db, f"{ch_name} - FOT (dB)")
                    _style_tfr_axis(axes[1], tfr_ifnfn_db, f"{ch_name} - IFNFN (dB)")
                    _style_tfr_axis(axes[2], tfr_contrast_db, f"{ch_name} - Contrast (dB)")

                    plt.tight_layout()
                    img_path = output_dir / f"tfr_{ch_name}.png"
                    plt.savefig(img_path, dpi=120, bbox_inches="tight")
                    plt.close()

                    html_parts.append(
                        f'<img src="{img_path.name}" alt="TFR {ch_name}"><br>'
                    )
                    logger.debug("TFR plot saved: %s", img_path)
                    gc.collect()

                except Exception as e:
                    logger.error("Failed to plot TFR for channel %s: %s", 
                                ch_name, e, exc_info=True)

        html_parts.append("</div>")

        # Section 2: PLV Comparison
        logger.info("Generating PLV plots for %d channels...", n_channels)
        html_parts.append('<div class="section"><h2>Section 2: Phase Locking Value (PLV)</h2>')

        if not data_check["plv_fot"] or not data_check["plv_ifnfn"]:
            html_parts.append(
                '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                'PLV data not available. Check that pipeline executed successfully.</p>'
            )
            logger.error("Cannot generate PLV plots: plv_fot=%s, plv_ifnfn=%s",
                        self.plv_fot is not None, self.plv_ifnfn is not None)
        elif n_channels == 0:
            html_parts.append(
                '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                'No channels available.</p>'
            )
        else:
            plv_fot_shape = self.plv_fot["plv"].shape if "plv" in self.plv_fot else None
            plv_ifnfn_shape = self.plv_ifnfn["plv"].shape if "plv" in self.plv_ifnfn else None
            logger.info("PLV data shapes: fot=%s, ifnfn=%s", 
                       plv_fot_shape, plv_ifnfn_shape)
            
            for ch_idx, ch_name in enumerate(ch_names):
                try:
                    if ("plv" not in self.plv_fot or "plv" not in self.plv_ifnfn):
                        logger.warning("PLV dict missing 'plv' key")
                        continue
                    
                    if ch_idx >= self.plv_fot["plv"].shape[0] or ch_idx >= self.plv_ifnfn["plv"].shape[0]:
                        logger.warning("Channel index %d out of bounds for PLV data",
                                      ch_idx)
                        continue
                    
                    fig, axes = plt.subplots(1, 3, figsize=(18, 4))

                    axes[0].plot(self.plv_fot["plv"][ch_idx], label="FOT")
                    axes[0].set_title(f"{ch_name} - FOT PLV")
                    axes[0].set_xlabel("Time (sample)")
                    axes[0].set_ylabel("PLV")
                    axes[0].set_ylim([0, 1])
                    axes[0].grid(True, alpha=0.3)
                    axes[0].legend()

                    axes[1].plot(self.plv_ifnfn["plv"][ch_idx], label="IFNFN")
                    axes[1].set_title(f"{ch_name} - IFNFN PLV")
                    axes[1].set_xlabel("Time (sample)")
                    axes[1].set_ylabel("PLV")
                    axes[1].set_ylim([0, 1])
                    axes[1].grid(True, alpha=0.3)
                    axes[1].legend()

                    # Contrast PLV
                    plv_contrast = self.plv_fot["plv"][ch_idx] - self.plv_ifnfn["plv"][ch_idx]
                    axes[2].plot(plv_contrast, label="Contrast", color="green")
                    axes[2].set_title(f"{ch_name} - Contrast PLV")
                    axes[2].set_xlabel("Time (sample)")
                    axes[2].set_ylabel("PLV Diff")
                    axes[2].set_ylim([-0.5, 0.5])
                    axes[2].grid(True, alpha=0.3)
                    axes[2].legend()

                    plt.tight_layout()
                    img_path = output_dir / f"plv_{ch_name}.png"
                    plt.savefig(img_path, dpi=100, bbox_inches="tight")
                    plt.close()

                    html_parts.append(
                        f'<img src="{img_path.name}" alt="PLV {ch_name}"><br>'
                    )
                    logger.debug("PLV plot saved: %s", img_path)
                    gc.collect()

                except Exception as e:
                    logger.error("Failed to plot PLV for channel %s: %s",
                                ch_name, e, exc_info=True)

        html_parts.append("</div>")

        # Section 3: SSSEP SNR Comparison
        logger.info("Generating SSSEP SNR plot...")
        html_parts.append(
            '<div class="section"><h2>Section 3: SSSEP SNR at Stim '
            f'Frequency ({self.cfg.stim_freq:.1f} Hz)</h2>'
        )

        if not data_check["sssep_fot"] or not data_check["sssep_ifnfn"]:
            html_parts.append(
                '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                'SSSEP data not available. Check that pipeline executed successfully.</p>'
            )
            logger.error("Cannot generate SSSEP plot: sssep_fot=%s, sssep_ifnfn=%s",
                        self.sssep_fot is not None, self.sssep_ifnfn is not None)
        elif n_channels == 0:
            html_parts.append(
                '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                'No channels available.</p>'
            )
        else:
            try:
                if "snr" not in self.sssep_fot or "snr" not in self.sssep_ifnfn:
                    logger.error("SSSEP dicts missing 'snr' key. Keys: fot=%s, ifnfn=%s",
                                list(self.sssep_fot.keys()), list(self.sssep_ifnfn.keys()))
                    html_parts.append(
                        '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                        'SSSEP SNR data structure invalid.</p>'
                    )
                else:
                    fot_snr = self.sssep_fot["snr"]
                    ifnfn_snr = self.sssep_ifnfn["snr"]
                    
                    logger.info("SSSEP SNR shapes: fot=%s, ifnfn=%s",
                               fot_snr.shape, ifnfn_snr.shape)
                    
                    if len(fot_snr) != n_channels or len(ifnfn_snr) != n_channels:
                        logger.error(
                            "SSSEP SNR channel mismatch: n_channels=%d, "
                            "fot_snr.len=%d, ifnfn_snr.len=%d",
                            n_channels, len(fot_snr), len(ifnfn_snr)
                        )
                        html_parts.append(
                            '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                            'Channel count mismatch in SSSEP data.</p>'
                        )
                    else:
                        fig, ax = plt.subplots(figsize=(12, 6))

                        x = np.arange(n_channels)
                        width = 0.25

                        ax.bar(x - width, fot_snr, width,
                               label="FOT", alpha=0.8)
                        ax.bar(x, ifnfn_snr, width,
                               label="IFNFN", alpha=0.8)
                        ax.bar(x + width, fot_snr - ifnfn_snr, width,
                               label="Contrast", alpha=0.8, color="green")

                        ax.set_xlabel("Channel")
                        ax.set_ylabel("SNR (dB)")
                        ax.set_title("SSSEP SNR Comparison & Contrast")
                        ax.set_xticks(x)
                        ax.set_xticklabels(ch_names, rotation=45, ha="right")
                        ax.legend()
                        ax.grid(True, alpha=0.3, axis="y")

                        plt.tight_layout()
                        img_path = output_dir / "sssep_snr_comparison.png"
                        plt.savefig(img_path, dpi=100, bbox_inches="tight")
                        plt.close()

                        html_parts.append(f'<img src="{img_path.name}" alt="SSSEP SNR"><br>')
                        logger.info("SSSEP SNR plot saved: %s", img_path)
                        gc.collect()

            except Exception as e:
                logger.error("Failed to plot SSSEP SNR: %s", e, exc_info=True)
                html_parts.append(
                    f'<p style="color: red;"><strong>⚠ Error:</strong> {str(e)}</p>'
                )

        html_parts.append("</div>")

        # Section 4: Summary Statistics Table
        logger.info("Generating summary table for %d channels...", n_channels)
        html_parts.append(
            '<div class="section"><h2>Section 4: Summary Statistics</h2>'
        )

        try:
            if n_channels == 0:
                html_parts.append(
                    '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                    'No channels available for summary table.</p>'
                )
                logger.error("Cannot generate summary table: no channels")
            elif not data_check["plv_fot"] or not data_check["plv_ifnfn"] or \
                 not data_check["sssep_fot"] or not data_check["sssep_ifnfn"]:
                html_parts.append(
                    '<p style="color: red;"><strong>⚠ Data Error:</strong> '
                    'Insufficient data for summary table. Missing: '
                )
                missing = [k.replace("_", " ").upper() for k, v in data_check.items() if not v]
                html_parts[-1] += ", ".join(missing) + '</p>'
                logger.error("Cannot generate summary table: missing data: %s", missing)
            else:
                html_parts.append("""
                <table>
                    <tr>
                        <th>Channel</th>
                        <th>FOT PLV</th>
                        <th>IFNFN PLV</th>
                        <th>PLV Contrast</th>
                        <th>FOT SNR (dB)</th>
                        <th>IFNFN SNR (dB)</th>
                        <th>SNR Contrast</th>
                    </tr>
                """)

                for ch_idx, ch_name in enumerate(ch_names):
                    try:
                        if ch_idx >= len(self.plv_fot["plv"]) or ch_idx >= len(self.plv_ifnfn["plv"]):
                            logger.warning("Channel index %d out of PLV data bounds", ch_idx)
                            continue
                        if ch_idx >= len(self.sssep_fot["snr"]) or ch_idx >= len(self.sssep_ifnfn["snr"]):
                            logger.warning("Channel index %d out of SSSEP data bounds", ch_idx)
                            continue
                        
                        fot_plv_mean = self.plv_fot["plv"][ch_idx].mean()
                        ifnfn_plv_mean = self.plv_ifnfn["plv"][ch_idx].mean()
                        plv_contrast = fot_plv_mean - ifnfn_plv_mean
                        
                        fot_snr = self.sssep_fot["snr"][ch_idx]
                        ifnfn_snr = self.sssep_ifnfn["snr"][ch_idx]
                        snr_contrast = fot_snr - ifnfn_snr

                        html_parts.append(f"""
                        <tr>
                            <td>{ch_name}</td>
                            <td>{fot_plv_mean:.3f}</td>
                            <td>{ifnfn_plv_mean:.3f}</td>
                            <td style="font-weight:bold; color:{'green' if plv_contrast > 0 else 'red'}">{plv_contrast:+.3f}</td>
                            <td>{fot_snr:.2f}</td>
                            <td>{ifnfn_snr:.2f}</td>
                            <td style="font-weight:bold; color:{'green' if snr_contrast > 0 else 'red'}">{snr_contrast:+.2f}</td>
                        </tr>
                        """)
                        logger.debug("Added row for channel %s", ch_name)
                    except Exception as e:
                        logger.error("Failed to add row for channel %s: %s",
                                    ch_name, e, exc_info=True)

                html_parts.append("</table>")
                logger.info("Summary table generated for %d channels", 
                           min(ch_idx + 1, n_channels))

        except Exception as e:
            logger.error("Failed to generate summary table: %s", e, exc_info=True)
            html_parts.append(
                f'<p style="color: red;"><strong>⚠ Error:</strong> '
                f'Could not generate table: {str(e)}</p>'
            )

        html_parts.append("</div>")

        # Footer
        html_parts.append("</body></html>")

        # Write HTML
        html_content = "\n".join(html_parts)
        report_path = output_dir / "prep_plv_sssep_report.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info("Report saved to %s", report_path)
        return report_path


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def main() -> None:
    """
    Command-line entry point for PREP+PLV+SSSEP analysis.

    Usage:
        python -m src.analysis.offline.tfr_contrast_prep_PLV \\
            --fot <path> --ifnfn <path> --config <yaml> --output <dir>
    """
    parser = argparse.ArgumentParser(
        description="PREP+PLV+SSSEP Analysis for Tactile Stimulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.analysis.offline.tfr_contrast_prep_PLV \\
    --fot data/raw/fot.fif \\
    --ifnfn data/raw/ifnfn.fif \\
    --config config/analysis/contrast_37hz.yaml \\
    --output reports
        """,
    )

    parser.add_argument(
        "--fot",
        type=Path,
        required=True,
        help="MNE FIF file for FOT (Finger-On-Tactor) condition",
    )
    parser.add_argument(
        "--ifnfn",
        type=Path,
        required=True,
        help="MNE FIF file for IFNFN (In-Field-Not-Feeling-Nipple) condition",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Analysis config YAML file (optional; uses defaults if omitted)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports"),
        help="Output directory for report (default: reports/)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("=" * 70)
    logger.info("PREP+PLV+SSSEP Analysis")
    logger.info("=" * 70)

    # Import scientific stack before any use
    logger.info("Importing scientific stack...")
    try:
        _import_scientific_stack()
    except Exception as e:
        logger.error("Failed to import scientific stack: %s", e)
        sys.exit(1)

    # Load config
    if args.config:
        logger.info("Loading config from %s...", args.config)
        try:
            import yaml

            with open(args.config, "r", encoding="utf-8") as f:
                yaml_dict = yaml.safe_load(f) or {}
            cfg = PrepPLVConfig.from_yaml(yaml_dict)
        except Exception as e:
            logger.error("Failed to load config: %s", e)
            sys.exit(1)
    else:
        logger.info("Using default configuration")
        cfg = PrepPLVConfig()

    # Load montage profile from config directory
    if cfg.montage_profile:
        # Find project root: from src/analysis/offline/ go up 3 levels
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        montage_dir = project_root / "config" / "montages"
        profile_path = montage_dir / f"{cfg.montage_profile}.yaml"
        if profile_path.exists():
            logger.info("Loading montage profile: %s", cfg.montage_profile)
            cfg.apply_montage_yaml(profile_path, overwrite=False)
        else:
            logger.warning("Montage profile '%s' not found at %s",
                          cfg.montage_profile, profile_path)

    # Validate input files
    if not args.fot.exists():
        logger.error("FOT file not found: %s", args.fot)
        sys.exit(1)
    if not args.ifnfn.exists():
        logger.error("IFNFN file not found: %s", args.ifnfn)
        sys.exit(1)

    # Create analyzer
    analyzer = PrepPLVAnalyzer(cfg)

    logger.info("Loading data files...")
    try:
        analyzer.load_two_files(args.fot, args.ifnfn)
    except Exception as e:
        logger.error("Failed to load files: %s", e, exc_info=True)
        sys.exit(1)

    # Run pipeline
    logger.info("Running pipeline...")
    success = analyzer.run_pipeline()

    if not success:
        logger.error("Pipeline execution failed")
        sys.exit(1)

    # Validate
    validation_error = analyzer.validate()
    if validation_error:
        logger.error("Validation failed: %s", validation_error)
        sys.exit(2)

    logger.info("Validation passed")

    # Generate report
    try:
        report_path = analyzer.generate_report(args.output)
        logger.info("SUCCESS: Report generated at %s", report_path)
        print(f"Report: {report_path}")
    except Exception as e:
        logger.error("Failed to generate report: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()