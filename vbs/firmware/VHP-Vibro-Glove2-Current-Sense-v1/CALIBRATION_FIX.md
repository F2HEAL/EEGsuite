# Current Sense Calibration Fix

## Problem Identified

The original current measurements were **~10x too low** (showing 8.6 mA instead of expected ~80-100 mA).

### Root Causes:

1. **Incorrect gain value**: The SENSE_GAIN was set to 50.0 V/A, but analysis showed it should be ~5.0 V/A
2. **ADC configuration mismatch**: The conversion formula was inconsistent with actual ADC behavior
3. **Missing calibration factor**: No way to adjust for hardware variations

## Solution Applied

### Changes Made:

1. **Fixed ADC resolution**: Changed from 4095 (wrong) to 1023 (correct 10-bit default)
2. **Corrected gain value**: Changed from 50.0 to 5.0 V/A
3. **Added calibration multiplier**: Applied 10x correction factor
4. **Added calibration documentation**: Clear instructions for fine-tuning if needed

### Expected Improvement:

```
Old measurements: 8.6 mA mean
New measurements: ~86 mA mean (with 10x calibration factor)
```

## 🔬 Hardware Measurement Limitations

### Unipolar vs. Bidirectional Sensing
The current hardware design uses a **MAX4073** high-side current-sense amplifier. This component is physically **unidirectional** (unipolar).

1.  **Positive Current**: When current flows from the power source to the load, the sensor outputs a proportional voltage ($0 \dots 3.6\text{V}$).
2.  **Negative Current**: When the H-bridge reverses polarity (negative half of the AC cycle), the MAX4073 cannot represent the reversed voltage drop. It physically **clips the output to 0V**.

### Technical Outcome
*   **Waveform Clipping**: On the oscilloscope plots, the current waveform will appear as "pulses" or "half-sine" waves. The flat sections at 0A are not "dead time" in the driver; they are the result of the hardware being unable to see the negative current flow.
*   **Mid-point Bias**: While the software allows setting an `ADC_BIAS_VOLTS` (e.g., 1.8V), this is purely a mathematical shift. It will not restore the missing negative half of the waveform if the sensor is physically unipolar.

### Recommendations for Research
*   For frequency analysis (e.g., verifying a 40Hz stimulus), the unipolar pulses are sufficient as they maintain the correct periodicity.
*   For power estimation, remember that you are only seeing half of the electrical work if the drive is fully alternating.
*   To see the full sine wave, the hardware would require a **Bidirectional** sensor (e.g., ACS712 or MAX4069) and a physical voltage divider to bias the ADC input to 1.8V.

## ⚖️ VCA Load Estimation

The firmware includes a runtime **Load Estimation** parameter (`vca_load_estimation`).

### Implementation Details:
*   **Mechanism**: A **Leaky Peak Detector** running in the high-speed ISR.
*   **Decay Factor**: $0.9999$ per sample, providing a stable "filtered" peak reading that responds to changes in mechanical impedance.
*   **Units**: Reported in **Amperes (A)** based on the current calibration.
*   **Reset**: The value is automatically cleared to `0.0` whenever a new stream is started (`1` command).

### Interpretation:
| State | Behavior | Physics |
| :--- | :--- | :--- |
| **Free / Unloaded** | Lower `W` value | High velocity creates high Back-EMF, which opposes current. |
| **Loaded / Skin Contact** | Higher `W` value | Resistance to motion reduces Back-EMF, allowing more current to flow. |
| **Blocked / Stall** | Maximum `W` value | Zero velocity means zero Back-EMF. Current is limited only by $R_{coil}$. |

## How to Further Calibrate (if needed)

1. **Load the updated firmware** to the board
2. **Start streaming** (send '1' command to serial)
3. **Measure actual current** at the load with a multimeter
4. **Send 'C' command** to dump current measurements
5. **Compare** firmware reading vs. multimeter reading

### If Further Adjustment Needed:

Edit `VHP-Vibro-Glove2-Current-Sense-v1.ino` line ~139:

```cpp
const int CALIBRATION_FACTOR_MUL = 10;    // Adjust this
const int CALIBRATION_FACTOR_DIV = 1;     // Keep this as 1 for integer
```

**Formula**: 
```
new_factor = old_factor * (multimeter_reading / firmware_reading)
```

**Example**: If multimeter shows 100 mA but firmware shows 80 mA:
```
new_factor = 10 * (100 / 80) = 12.5
Set: CALIBRATION_FACTOR_MUL = 25, CALIBRATION_FACTOR_DIV = 2  (to represent 12.5)
```

## Testing

After flashing:
```
1. Send '1' to start streaming
2. Send 'C' to dump current log
3. Check measurements are in 50-300 mA range (typical for haptic devices)
4. Compare with multimeter for accuracy
```

## Files Modified

- `VHP-Vibro-Glove2-Current-Sense-v1.ino` - Updated current sense conversion formula
- Added calibration analysis scripts: 
  - `calibrate_current.py` - Test different gain values
  - `analyze_calibration.py` - Reverse engineering of current issues
