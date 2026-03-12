#!/usr/bin/env python3
"""
test_tfr_contrast.py — Generate mock EEG data and test the TFR contrast pipeline.

Creates synthetic FOT and IFNFN recordings with:
  - Background 1/f EEG noise (realistic spectral shape)
  - 10 Hz alpha oscillation (present in both conditions, should cancel)
  - 22 Hz EM tactor artifact (present in both conditions, should cancel)
  - 22 Hz NEURAL response (present ONLY in FOT, should SURVIVE the contrast)

If the pipeline works correctly:
  - FOT TFR shows a blob at 22 Hz during stimulation
  - IFNFN TFR also shows a 22 Hz blob (EM artifact)
  - Contrast (FOT - IFNFN) shows ONLY the neural 22 Hz component

Usage:
    python test_tfr_contrast.py

    This will:
    1. Generate mock CSV files in test_output/
    2. Run the full 4-step pipeline
    3. Generate an HTML report in test_output/report/
    4. Print validation results
"""

import sys
import logging
import numpy as np
import csv
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration for the synthetic data
# ---------------------------------------------------------------------------
SFREQ = 512.0            # Sampling rate (Hz) — matches FreeEEG32
N_CHANNELS = 32           # Total CSV columns for EEG
N_TRIALS = 30             # Trials per condition (30 is enough for testing)
STIM_FREQ = 22.0          # Stimulation frequency (Hz)

# Timing (seconds) — matches protocol defaults
T_PRE = 1.5               # Pre-stim baseline
T_STIM = 4.0              # Stimulation duration
T_POST = 1.0              # Post-stim
T_TRIAL = T_PRE + T_STIM + T_POST  # Total trial duration

# Signal amplitudes (arbitrary units, relative)
AMP_BACKGROUND = 20.0     # 1/f background noise
AMP_ALPHA = 5.0           # 10 Hz alpha (shared, should cancel)
AMP_EM_ARTIFACT = 15.0    # 22 Hz EM noise from tactor (shared, should cancel)
AMP_NEURAL = 3.0          # 22 Hz neural response (FOT only, should survive)

# FREG8 channel mapping (must match tfr_contrast.py defaults)
FREG8_CHANNELS = [
    "T7",  "C3",  "NC",  "NC",  "T8",  "FC4", "NC",  "NC",
    "FC3", "C4",  "NC",  "NC",  "CP3", "CP4", "NC",  "NC",
    "NC",  "NC",  "NC",  "NC",  "NC",  "NC",  "NC",  "NC",
    "NC",  "NC",  "NC",  "NC",  "NC",  "NC",  "NC",  "NC",
]

# Which channels are real (not NC) — these get signals
ACTIVE_CHANNELS = [i for i, ch in enumerate(FREG8_CHANNELS) if ch != "NC"]
# Channels where neural response is strongest (somatosensory: C3, C4, CP3, CP4)
NEURAL_CHANNELS = [i for i, ch in enumerate(FREG8_CHANNELS) if ch in ("C3", "C4", "CP3", "CP4")]

# Marker codes — must match tfr_contrast.py
MARKER_FOT_REST = 100
MARKER_FOT_STIM_ON = 101
MARKER_FOT_STIM_OFF = 111
MARKER_IFNFN_REST = 200
MARKER_IFNFN_STIM_ON = 201
MARKER_IFNFN_STIM_OFF = 211


# ---------------------------------------------------------------------------
# Signal generators
# ---------------------------------------------------------------------------
def generate_pink_noise(n_samples: int, rng: np.random.Generator) -> np.ndarray:
    """Generate 1/f (pink) noise — realistic EEG background spectrum."""
    white = rng.standard_normal(n_samples)
    # Apply 1/f filter in frequency domain
    freqs = np.fft.rfftfreq(n_samples)
    freqs[0] = 1  # avoid division by zero
    fft = np.fft.rfft(white)
    fft *= 1.0 / np.sqrt(freqs)
    return np.fft.irfft(fft, n=n_samples)


def generate_sine_burst(
    n_samples: int,
    sfreq: float,
    freq: float,
    amplitude: float,
    onset_sample: int,
    duration_samples: int,
    ramp_samples: int = 50,
) -> np.ndarray:
    """Generate a sine wave burst with smooth onset/offset ramps."""
    signal = np.zeros(n_samples)
    t = np.arange(duration_samples) / sfreq
    burst = amplitude * np.sin(2 * np.pi * freq * t)

    # Apply cosine ramp (smooth onset/offset to avoid edge artifacts)
    if ramp_samples > 0:
        ramp_up = 0.5 * (1 - np.cos(np.pi * np.arange(ramp_samples) / ramp_samples))
        ramp_down = ramp_up[::-1]
        burst[:ramp_samples] *= ramp_up
        burst[-ramp_samples:] *= ramp_down

    end = min(onset_sample + duration_samples, n_samples)
    actual_len = end - onset_sample
    signal[onset_sample:end] = burst[:actual_len]
    return signal


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------
def write_mock_csv(
    filepath: Path,
    condition: str,
    n_trials: int,
    include_neural: bool,
    rng: np.random.Generator,
):
    """
    Write a mock sweep CSV with realistic-ish EEG data.

    Args:
        filepath: Output CSV path
        condition: "FOT" or "IFNFN"
        n_trials: Number of trials
        include_neural: If True, inject 22 Hz neural response during stim
        rng: Numpy random generator for reproducibility
    """
    trial_samples = int(T_TRIAL * SFREQ)
    total_samples = trial_samples * n_trials
    pre_samples = int(T_PRE * SFREQ)
    stim_samples = int(T_STIM * SFREQ)

    # Marker codes
    if condition == "FOT":
        m_rest, m_on, m_off = MARKER_FOT_REST, MARKER_FOT_STIM_ON, MARKER_FOT_STIM_OFF
    else:
        m_rest, m_on, m_off = MARKER_IFNFN_REST, MARKER_IFNFN_STIM_ON, MARKER_IFNFN_STIM_OFF

    # Generate signals for all 32 channels
    eeg_data = np.zeros((N_CHANNELS, total_samples))

    for ch in range(N_CHANNELS):
        if ch in ACTIVE_CHANNELS:
            # 1/f background noise (present everywhere, all time)
            eeg_data[ch] = generate_pink_noise(total_samples, rng) * AMP_BACKGROUND

            # 10 Hz alpha oscillation (continuous, both conditions)
            t = np.arange(total_samples) / SFREQ
            eeg_data[ch] += AMP_ALPHA * np.sin(2 * np.pi * 10.0 * t + rng.uniform(0, 2*np.pi))

            # Per-trial signals
            for trial in range(n_trials):
                trial_start = trial * trial_samples
                stim_onset = trial_start + pre_samples

                # 22 Hz EM artifact during stimulation (BOTH conditions)
                eeg_data[ch] += generate_sine_burst(
                    total_samples, SFREQ, STIM_FREQ, AMP_EM_ARTIFACT,
                    stim_onset, stim_samples,
                )

                # 22 Hz neural response during stimulation (FOT ONLY)
                if include_neural and ch in NEURAL_CHANNELS:
                    eeg_data[ch] += generate_sine_burst(
                        total_samples, SFREQ, STIM_FREQ, AMP_NEURAL,
                        stim_onset, stim_samples,
                        ramp_samples=100,  # slower neural onset
                    )
        else:
            # NC channels: just tiny noise
            eeg_data[ch] = rng.standard_normal(total_samples) * 0.1

    # Build timestamps (simulating LSL timestamps)
    t0 = 1000.0  # arbitrary start
    timestamps = t0 + np.arange(total_samples) / SFREQ

    # Build marker column (mostly empty, value only on first sample of each phase)
    markers = [""] * total_samples
    for trial in range(n_trials):
        trial_start = trial * trial_samples
        stim_onset = trial_start + pre_samples
        stim_offset = stim_onset + stim_samples
        markers[trial_start] = str(m_rest)
        markers[stim_onset] = str(m_on)
        markers[stim_offset] = str(m_off)

    # Write CSV
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        for i in range(total_samples):
            row = [f"{timestamps[i]:.6f}"]
            row += [f"{eeg_data[ch, i]:.4f}" for ch in range(N_CHANNELS)]
            row.append(markers[i])
            writer.writerow(row)

    n_marker_rows = sum(1 for m in markers if m != "")
    print(f"  Wrote {filepath.name}: {total_samples} samples, {n_trials} trials, "
          f"{n_marker_rows} markers, neural={include_neural}")


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    rng = np.random.default_rng(seed=42)

    # ------------------------------------------------------------------
    # Step 1: Generate mock data
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 1: Generating mock EEG data")
    print("=" * 60)
    print(f"  Sampling rate: {SFREQ} Hz")
    print(f"  Trials per condition: {N_TRIALS}")
    print(f"  Stim frequency: {STIM_FREQ} Hz")
    print(f"  Trial timing: {T_PRE}s pre + {T_STIM}s stim + {T_POST}s post = {T_TRIAL}s total")
    print(f"  Active channels: {[FREG8_CHANNELS[i] for i in ACTIVE_CHANNELS]}")
    print(f"  Neural response channels: {[FREG8_CHANNELS[i] for i in NEURAL_CHANNELS]}")
    print()

    fot_path = output_dir / "mock_FOT.csv"
    ifnfn_path = output_dir / "mock_IFNFN.csv"

    # FOT: has EM artifact + neural response
    write_mock_csv(fot_path, "FOT", N_TRIALS, include_neural=True, rng=rng)
    # IFNFN: has EM artifact only (no neural)
    write_mock_csv(ifnfn_path, "IFNFN", N_TRIALS, include_neural=False, rng=rng)

    # ------------------------------------------------------------------
    # Step 2: Run the pipeline
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 2: Running TFR contrast pipeline")
    print("=" * 60)

    # Import the module under test
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from src.analysis.offline.tfr_contrast import TFRContrastAnalyzer, TFRContrastConfig

    cfg = TFRContrastConfig(
        # Use wider freq range to see the full picture
        tfr_fmin=5.0,
        tfr_fmax=45.0,
        tfr_fstep=1.0,
        # Speed up for testing
        tfr_decim=2,
        # Protocol-matching windows
        epoch_tmin=-1.5,
        epoch_tmax=5.0,
        baseline_tmin=-1.0,
        baseline_tmax=-0.5,
        stim_window_tmin=0.5,
        stim_window_tmax=4.0,
        baseline_mode="logratio",
        # Output
        output_dir=str(output_dir / "report"),
    )

    analyzer = TFRContrastAnalyzer(cfg)
    print("\nLoading mock data...")
    analyzer.load_two_files(fot_path, ifnfn_path)

    print("Running 4-step pipeline...")
    success = analyzer.run_pipeline()

    if not success:
        print("\n❌ Pipeline FAILED. See log output above.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 3: Validate results
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 3: Validating results")
    print("=" * 60)

    # Check that TFR objects exist
    assert analyzer.tfr_fot is not None, "FOT TFR is None"
    assert analyzer.tfr_ifnfn is not None, "IFNFN TFR is None"
    assert analyzer.tfr_contrast is not None, "Contrast TFR is None"
    print("  ✅ All three TFR objects created (FOT, IFNFN, contrast)")

    # Check shapes match
    assert analyzer.tfr_fot.data.shape == analyzer.tfr_ifnfn.data.shape, \
        f"Shape mismatch: FOT {analyzer.tfr_fot.data.shape} vs IFNFN {analyzer.tfr_ifnfn.data.shape}"
    assert analyzer.tfr_fot.data.shape == analyzer.tfr_contrast.data.shape, \
        "Contrast shape doesn't match conditions"
    print(f"  ✅ TFR shapes match: {analyzer.tfr_fot.data.shape} "
          f"(channels × freqs × times)")

    # Check that channels are correct (should be picked channels only)
    expected_chs = {"T7", "C3", "T8", "FC4", "FC3", "C4", "CP3", "CP4"}
    actual_chs = set(analyzer.tfr_fot.ch_names)
    assert actual_chs == expected_chs, f"Channel mismatch: expected {expected_chs}, got {actual_chs}"
    print(f"  ✅ Channels correct: {sorted(actual_chs)}")

    # Check that the contrast shows a signal at the stim frequency
    freqs = analyzer.tfr_contrast.freqs
    times = analyzer.tfr_contrast.times

    # Find the 22 Hz frequency index
    stim_freq_idx = np.argmin(np.abs(freqs - STIM_FREQ))
    actual_freq = freqs[stim_freq_idx]
    print(f"  ℹ️  Stim frequency bin: {actual_freq:.1f} Hz (target: {STIM_FREQ} Hz)")

    # Find time indices for the stimulation window
    stim_time_mask = (times >= 1.0) & (times <= 3.5)
    baseline_time_mask = (times >= -1.0) & (times <= -0.5)

    # For neural channels (C3, C4, CP3, CP4), contrast at 22 Hz should be positive
    neural_ch_names = ["C3", "C4", "CP3", "CP4"]
    for ch_name in neural_ch_names:
        ch_idx = analyzer.tfr_contrast.ch_names.index(ch_name)
        stim_power = analyzer.tfr_contrast.data[ch_idx, stim_freq_idx, stim_time_mask].mean()
        base_power = analyzer.tfr_contrast.data[ch_idx, stim_freq_idx, baseline_time_mask].mean()

        print(f"  {ch_name} @ {actual_freq:.0f} Hz — contrast stim power: {stim_power:+.3f}, "
              f"baseline: {base_power:+.3f}")

        # The stim power should be clearly above baseline in the contrast
        if stim_power > base_power + 0.01:
            print(f"    ✅ Neural response detected in contrast (stim > baseline)")
        else:
            print(f"    ⚠️  Neural response weak or absent — check amplitudes")

    # For a non-neural channel (T7), contrast should be weaker
    t7_idx = analyzer.tfr_contrast.ch_names.index("T7")
    t7_stim = analyzer.tfr_contrast.data[t7_idx, stim_freq_idx, stim_time_mask].mean()
    t7_c3_stim = analyzer.tfr_contrast.data[
        analyzer.tfr_contrast.ch_names.index("C3"),
        stim_freq_idx,
        stim_time_mask
    ].mean()
    print(f"\n  T7 (non-neural) contrast at {actual_freq:.0f} Hz: {t7_stim:+.3f}")
    print(f"  C3 (neural)     contrast at {actual_freq:.0f} Hz: {t7_c3_stim:+.3f}")
    if abs(t7_c3_stim) > abs(t7_stim):
        print(f"  ✅ Neural channel (C3) shows stronger contrast than non-neural (T7)")
    else:
        print(f"  ⚠️  Expected C3 > T7 in contrast — signals may need tuning")

    # Check that 10 Hz alpha is largely cancelled in the contrast
    alpha_freq_idx = np.argmin(np.abs(freqs - 10.0))
    alpha_contrast = np.abs(analyzer.tfr_contrast.data[:, alpha_freq_idx, stim_time_mask]).mean()
    alpha_fot = np.abs(analyzer.tfr_fot.data[:, alpha_freq_idx, stim_time_mask]).mean()
    print(f"\n  10 Hz alpha — FOT power: {alpha_fot:.3f}, Contrast power: {alpha_contrast:.3f}")
    if alpha_contrast < alpha_fot:
        print(f"  ✅ Alpha (10 Hz) reduced in contrast (shared signal cancelled)")
    else:
        print(f"  ⚠️  Alpha not fully cancelled — expected with random noise")

    # ------------------------------------------------------------------
    # Step 4: Generate report
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 4: Generating HTML report")
    print("=" * 60)

    report_path = analyzer.generate_report(
        output_dir=output_dir / "report",
        filename="mock_contrast_report.html",
    )
    print(f"  ✅ Report: {report_path}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"\nFiles generated:")
    print(f"  Mock FOT data:   {fot_path}")
    print(f"  Mock IFNFN data: {ifnfn_path}")
    print(f"  HTML report:     {report_path}")
    print(f"\nOpen the HTML report in a browser to visually verify:")
    print(f"  - FOT TFR should show 22 Hz blob during stimulation")
    print(f"  - IFNFN TFR should also show 22 Hz blob (EM artifact)")
    print(f"  - Contrast should show 22 Hz ONLY on neural channels (C3, C4, CP3, CP4)")
    print(f"  - 10 Hz alpha should be minimal in the contrast")


if __name__ == "__main__":
    main()
