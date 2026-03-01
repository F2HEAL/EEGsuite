#!/usr/bin/env python3
"""Analyze current measurements and determine correct gain calibration."""

import numpy as np

# Read the putty.log data
with open('putty.log', 'r') as f:
    data = []
    for line in f:
        parts = line.strip().split(',')
        if len(parts) == 2:
            try:
                adc_val = float(parts[0])
                current_old = float(parts[1])
                data.append((adc_val, current_old))
            except:
                pass

# Convert to arrays
adc_vals = np.array([d[0] for d in data])
currents_old = np.array([d[1] for d in data])

print(f"ADC range: {adc_vals.min():.0f} to {adc_vals.max():.0f}")
print(f"ADC mean: {adc_vals.mean():.0f}")
print(f"Current range (old formula): {currents_old.min():.6f} to {currents_old.max():.6f} A")
print(f"Current mean (old): {currents_old.mean():.6f} A\n")

# Test different gain values
print("Current estimates with different gains (using 3.6V ref, 1024 ADC res):")
for gain in [5.0, 10.0, 20.0, 50.0, 100.0]:
    v_ref = 3.6
    adc_res = 1024  # Arduino standard
    voltage = adc_vals * (v_ref / adc_res)
    current = voltage / gain
    print(f"  Gain {gain:6.1f} V/A: mean = {current.mean():.6f} A, range = {current.min():.6f} to {current.max():.6f}")

# Also test with 4095 resolution (in case Arduino is using 12-bit)
print("\nCurrent estimates with different gains (using 3.6V ref, 4095 ADC res):")
for gain in [5.0, 10.0, 20.0, 50.0, 100.0]:
    v_ref = 3.6
    adc_res = 4095  # 12-bit
    voltage = adc_vals * (v_ref / adc_res)
    current = voltage / gain
    print(f"  Gain {gain:6.1f} V/A: mean = {current.mean():.6f} A, range = {current.min():.6f} to {current.max():.6f}")

print("\n" + "="*70)
print("CALIBRATION INSTRUCTIONS:")
print("="*70)
print("1. Measure the actual current draw with a multimeter")
print("2. Compare with the estimates above")
print("3. Update CURRENT_SENSE_GAIN in VHP-Vibro-Glove2-Current-Sense-v1.ino")
print("4. Recompile and test")
print("\nExample: If actual current is ~100 mA but gain=50 shows ~70 mA,")
print("adjust gain to: 50 * (70/100) = 35 V/A")
