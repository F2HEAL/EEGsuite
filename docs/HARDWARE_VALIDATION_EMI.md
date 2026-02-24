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

### 3. Benchmark: Medical-Grade Dual-Coil VCA
To establish a "gold standard," a medical-grade VCA with a balanced dual-coil design was measured under the same conditions.

![EMI Medical Grade](assets/emi_medical_grade.png)

*   **Peak Power (32 Hz)**: **None detected**. The dual-coil design provides perfect electromagnetic cancellation at the source.
*   **Broadband Noise Floor**: $\approx 265\text{ dB}$.
*   **Observations**: The 32 Hz EM signature is completely absent. The dominant feature is now the 50 Hz mains peak, which was previously masked by the Class D noise.

---

## 🔬 Quantitative Findings

| Metric | No Filter | With HW Filter | Medical-Grade |
| :--- | :--- | :--- | :--- |
| **Stimulus Peak (32 Hz)** | $325\text{ dB}$ | $285\text{ dB}$ | **Not Detected** |
| **System Noise Floor** | $300\text{ dB}$ | $265\text{ dB}$ | **$265\text{ dB}$** |
| **Noise Reduction** | Baseline | $-35\text{ dB}$ | **$-35\text{ dB}$** |

---

## 💡 Qualitative Interpretation

1.  **Filter vs. Source Cancellation**: While the Custom HW Filter suppresses the interference by 40 dB, the Medical-Grade VCA eliminates it at the source via its dual-coil architecture.
2.  **Achieving the System Floor**: The fact that both the filtered setup and the medical-grade device share an identical **265 dB noise floor** indicates that we have reached the hardware resolution limit of the EEG acquisition system.
3.  **Class D Carrier Cleanup**: The 35 dB drop in the noise floor confirms that the custom filter effectively matches medical-grade performance in stripping away Class D amplifier switching noise.
4.  **Mains Visibility**: In both the filtered and medical-grade setups, the 50 Hz mains peak becomes the new dominant interference, as the broadband "dirt" from the stimulator has been successfully removed.

## 🎯 Conclusion
The custom hardware filter successfully brings a standard stimulator down to **medical-grade electromagnetic performance** regarding the broadband noise floor. While the medical-grade dual-coil VCA is superior for its inherent cancellation of the 32 Hz stimulus peak, the filtered setup is now sufficiently quiet for high-integrity Parkinson's research measurements.
