#!/usr/bin/env python3
"""Reverse engineer ADC values and determine calibration factor."""

# Reverse engineer what ADC value would give the old measurements
mean_current = 0.008602

# Old formula: adc_val * (3.6f/4095.0f)/5.0f = current
# So: adc_val = current * 5.0 * 4095 / 3.6
reverse_adc = mean_current * 5.0 * 4095 / 3.6
print(f"Old formula implies ADC raw value ~{reverse_adc:.1f} counts")
print(f"As % of 4095-bit range: {reverse_adc/4095*100:.2f}%")
print(f"As % of 1024-bit range: {reverse_adc/1024*100:.2f}%\n")

# If this is correct, what's the actual current at different gains?
adc_val = reverse_adc
print(f"If actual ADC count is {adc_val:.1f}:")
print(f"  With 4095 resolution, gain=5.0:   {adc_val * (3.6/4095.0) / 5.0:.6f} A")
print(f"  With 4095 resolution, gain=0.5:   {adc_val * (3.6/4095.0) / 0.5:.6f} A (10x higher)")
print(f"  With 1024 resolution, gain=50.0:  {adc_val * (3.6/1024.0) / 50.0:.6f} A")
print(f"  With 1024 resolution, gain=5.0:   {adc_val * (3.6/1024.0) / 5.0:.6f} A (10x higher)\n")

# Typical haptic current draw
print("For reference, typical haptic/voice-coil devices draw:")
print("  - Low power: 50-100 mA")
print("  - Medium power: 100-300 mA")
print("  - High power: 300+ mA")
print(f"\nCurrent measurements showing {mean_current*1000:.1f} mA seem LOW")
print("Check with multimeter - if actual is ~100 mA, multiply readings by 10-15x")
