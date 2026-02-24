# 🛡️ Hardware Validation: EM Interference & Filtering

This report documents the effectiveness of the hardware filtering applied to the voice-coil stimulator (VCS) wire to mitigate electromagnetic interference (EMI) in EEG measurements.

## 📝 Executive Summary
To validate the hardware (HW) filter, the system was "misused" by placing EEG sensors directly into the electromagnetic field of the voice-coil stimulator. This allowed for a direct measurement of the EM cross-talk between the stimulator and the EEG leads, comparing the raw output of the Class D amplifier against the filtered output.

**The results show that the HW filter provides a massive $\approx 35\text{ dB}$ reduction in background noise floor and a $40\text{ dB}$ suppression of the stimulation frequency.**

---

## 📊 Comparative Analysis

### 1. Baseline: Without Hardware Filter
In this configuration, the EEG leads capture the raw EM signature of the Class D amplifier and the voice-coil drive signal.

![EMI without Filter](assets/emi_no_filter.png)

*   **Peak Power (32 Hz)**: $\approx 325\text{ dB}$
*   **Broadband Noise Floor**: $\approx 300\text{ dB}$
*   **Observations**: The noise floor is significantly elevated by high-frequency switching noise. The wide variance (shaded area) indicates high EM instability.

### 2. Validation: With Hardware Filter
With the HW filter installed at the output of the Class D amplifier, the EM leakage is drastically reduced.

![EMI with HW Filter](assets/emi_with_filter.png)

*   **Peak Power (32 Hz)**: $\approx 285\text{ dB}$ (**$40\text{ dB}$ reduction**)
*   **Broadband Noise Floor**: $\approx 265\text{ dB}$ (**$35\text{ dB}$ reduction**)
*   **Observations**: The signal is significantly cleaner. The reduction in variance indicates a much more deterministic and stable EM environment.

---

## 🔬 Quantitative Findings

| Metric | No Filter | With HW Filter | Improvement |
| :--- | :--- | :--- | :--- |
| **Stimulus Peak (32 Hz)** | $325\text{ dB}$ | $285\text{ dB}$ | **$-40\text{ dB}$** |
| **System Noise Floor** | $300\text{ dB}$ | $265\text{ dB}$ | **$-35\text{ dB}$** |
| **Power Reduction** | Baseline | $1/3162$ of original | **$>3,000\times$ quieter** |

---

## 💡 Qualitative Interpretation

1.  **Class D Carrier Cleanup**: The 35 dB drop in the noise floor indicates that the filter is successfully trapping high-frequency PWM harmonics before they can radiate into the EEG leads.
2.  **Increased Dynamic Range**: By lowering the floor, the system has "unmasked" the rest of the spectrum. For example, the **50 Hz mains peak** is now clearly visible in the filtered plot, whereas it was completely buried under the amplifier's noise in the unfiltered setup.
3.  **Deterministic Stability**: The tighter variance in the filtered data suggests the EMI is now stable and predictable, which makes it much easier to handle in software if any residual interference remains.

## 🎯 Conclusion
The hardware filter is **exceptionally effective**. It provides a power reduction of more than 3,000 times in the background EM noise floor. This level of isolation is critical for ensuring that future EEG measurements reflect actual brain activity rather than stimulator interference.
