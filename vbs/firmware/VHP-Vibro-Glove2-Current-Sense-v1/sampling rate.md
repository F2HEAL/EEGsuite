# Recommended Sampling Rate for 32Hz Sine Wave Visualization

To properly visualize a **32Hz** sine wave current, you must go beyond the theoretical minimum to ensure the waveform appears smooth and accurate.

## Quick Recommendation
For a high-quality visualization, use a sampling rate of **320 Hz to 640 Hz** (10x to 20x the signal frequency).

---

## Sampling Rate Breakdown


| Quality Level | Sampling Rate ($f_s$) | Samples per Cycle | Result |
| :--- | :--- | :--- | :--- |
| **Nyquist (Minimum)** | $64\text{ Hz}$ | 2 | Captures frequency, but looks like a triangle or pulse. |
| **Good Visualization** | **$320 - 640\text{ Hz}$** | **10 - 20** | **Smooth, recognizable sine wave curve.** |
| **High Precision** | $1024+\text{ Hz}$ | 32+ | Excellent for detailed harmonic analysis. |

---

## Technical Considerations

1.  **The Nyquist-Shannon Theorem:** Mathematically, you only need $f_s > 2 \times f_{signal}$. However, at exactly 2x, you only get two points per peak/trough, which makes the wave look "jagged" or like a sawtooth.
2.  **Aliasing:** If your signal contains noise higher than half your sampling rate, it will "alias" into your visualization as ghost frequencies. Using a higher sampling rate ($10x+$) provides a safety buffer.
3.  **Interpolation:** If your plotting software (like MATLAB, Python, or an Oscilloscope) uses linear interpolation, 10-20 points per cycle is the "sweet spot" for a clean visual without wasting memory.

## Summary Formula
For visualization, use:
$$f_s = f_{signal} \times 20$$
For 32Hz:
$$32\text{ Hz} \times 20 = 640\text{ Hz}$$

---

**Response:**
You were absolutely right. The initial plan to sample "once per pulse" (at 32 Hz) would only have given the envelope, not the waveform.

**Correction:**
The `OnPwmSequenceEnd` interrupt actually fires at the end of every *DMA buffer sequence*, not every full stimulation pulse. 
With the current settings (8 samples per buffer, ~46.9 kHz carrier), this interrupt fires at approximately **5,859 Hz**.

**New Implementation:**
*   **Sample Rate**: ~5.86 kHz (1 sample every ~170µs).
*   **Resolution**: ~183 data points per cycle for a 32 Hz sine wave.
*   **Data Type**: Raw instantaneous current (no averaging/filtering).

This will give you exactly what you asked for: a high-resolution, oscilloscope-like trace of the 32 Hz current waveform, capturing the full AC dynamics.
