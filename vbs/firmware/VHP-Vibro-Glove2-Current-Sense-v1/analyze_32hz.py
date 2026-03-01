#!/usr/bin/env python3
"""Analyze current waveform for expected 40 Hz stimulus sine wave component."""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

# Read the current data
with open('putty.log', 'r') as f:
    data = []
    for line in f:
        # Check if line contains comma and is not a header
        if ',' in line and "SampleIndex" not in line:
            parts = line.strip().split(',')
            # Support 2-column (old) or 3-column (new) format
            try:
                if len(parts) == 3:
                    # New format: SampleIndex, Voltage, Current
                    sample_idx = int(parts[0])
                    current_a = float(parts[2])
                    data.append((sample_idx, current_a))
                elif len(parts) == 2:
                    # Old format: SampleIndex, Current
                    sample_idx = int(parts[0])
                    current_a = float(parts[1])
                    data.append((sample_idx, current_a))
            except:
                pass

sample_indices = np.array([d[0] for d in data])
currents = np.array([d[1] for d in data])

# Parameters
fs = 5860  # Sampling rate in Hz
expected_freq = 40  # Expected stimulus frequency (default is 40 Hz, not 32)

# comment: user may adjust below if different stimulus is used
# expected_freq = 32  # was used earlier when firmware default was 32 Hz

print(f"Total samples: {len(currents)}")
print(f"Sampling rate: {fs} Hz")
print(f"Duration: {len(currents)/fs:.2f} seconds")
print(f"Expected stimulus frequency: {expected_freq} Hz")
print(f"Samples per 32 Hz cycle: {fs/expected_freq:.0f}\n")

print("Current statistics:")
print(f"  Mean: {currents.mean():.6f} A")
print(f"  Std Dev: {currents.std():.6f} A")
print(f"  Min: {currents.min():.6f} A")
print(f"  Max: {currents.max():.6f} A")
print(f"  Peak-to-peak: {currents.max() - currents.min():.6f} A\n")

# Remove DC offset to see AC component
current_ac = currents - currents.mean()

# Note: we now target the stimulus frequency (triggered by firmware) which
# defaults to 40 Hz. The variable expected_freq above is set accordingly.

print("AC component (after removing DC):")
print(f"  Amplitude: {current_ac.std():.6f} A")
print(f"  Peak-to-peak: {current_ac.max() - current_ac.min():.6f} A\n")

# Compute FFT to find frequency components
fft_result = np.fft.fft(current_ac)
fft_freqs = np.fft.fftfreq(len(current_ac), 1/fs)
fft_mag = np.abs(fft_result) / len(current_ac)

# Find peaks in FFT (positive frequencies only)
positive_idx = fft_freqs > 0
positive_freqs = fft_freqs[positive_idx]
positive_mag = fft_mag[positive_idx]

# Find dominant frequencies
top_10_idx = np.argsort(positive_mag)[-20:][::-1]
print("Top 10 frequency components:")
for i, idx in enumerate(top_10_idx[:10]):
    freq = positive_freqs[idx]
    mag = positive_mag[idx]
    print(f"  {i+1}. {freq:8.2f} Hz: magnitude = {mag:.6f}")

# Check specifically for 32 Hz
freq_resolution = fs / len(current_ac)
closest_32hz_idx = np.argmin(np.abs(positive_freqs - 32))
mag_at_32hz = positive_mag[closest_32hz_idx]
freq_at_peak = positive_freqs[closest_32hz_idx]

print(f"\nAt ~32 Hz region:")
print(f"  Closest peak: {freq_at_peak:.2f} Hz with magnitude {mag_at_32hz:.6f}")
print(f"  Frequency resolution: {freq_resolution:.2f} Hz/bin")

# Plot analysis
fig, axes = plt.subplots(3, 1, figsize=(14, 10))

# Raw current
axes[0].plot(sample_indices, currents, linewidth=0.5)
axes[0].set_ylabel('Current (A)')
axes[0].set_title('Raw Current Measurement')
axes[0].grid(True, alpha=0.3)

# AC component (zoomed to first 5 seconds to see detail)
max_samples_to_plot = min(len(currents), int(5 * fs))
axes[1].plot(sample_indices[:max_samples_to_plot], current_ac[:max_samples_to_plot], linewidth=0.8)
axes[1].set_ylabel('Current AC (A)')
axes[1].set_xlabel('Sample Index')
axes[1].set_title('AC Component (first 5 seconds) - showing 32 Hz sine wave if present')
axes[1].grid(True, alpha=0.3)

# FFT magnitude spectrum (up to 500 Hz)
freq_limit = 500
limit_idx = positive_freqs < freq_limit
axes[2].semilogy(positive_freqs[limit_idx], positive_mag[limit_idx], linewidth=1)
axes[2].axvline(32, color='r', linestyle='--', label='Expected 32 Hz')
axes[2].set_xlabel('Frequency (Hz)')
axes[2].set_ylabel('Magnitude (log scale)')
axes[2].set_title('FFT Spectrum (0-500 Hz)')
axes[2].legend()
axes[2].grid(True, alpha=0.3, which='both')

plt.tight_layout()
plt.savefig('current_analysis_32hz.png', dpi=150, bbox_inches='tight')
print(f"\nPlot saved to: current_analysis_32hz.png")

# Recommendation
if mag_at_32hz < 0.01:
    print("\n⚠️  WARNING: 32 Hz component is very weak or absent!")
    print("Possible causes:")
    print("  1. Current sensing is capturing DC only (no AC modulation)")
    print("  2. 32 Hz stimulus may not be properly driving the voice coil")
    print("  3. Low-pass filtering is removing the 32 Hz signal")
    print("  4. ADC offset/bias needs adjustment")
else:
    print(f"\n✓ 32 Hz component detected with amplitude {mag_at_32hz:.6f} A")
