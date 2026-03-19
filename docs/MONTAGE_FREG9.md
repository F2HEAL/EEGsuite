# 🧠 FREG9 9-Channel Montage

This document describes the **FREG9** sparse montage, designed for high-SNR motor-cortex measurements using 9 electrodes.

## 📍 Electrode Layout

This montage focuses on the central and parietal regions (C3, C4, Cz area).

```text
       FC3          FC4
          \          /
     T7----C3--Cz--C4----T8
          /          \
        CP3          CP4
```

## 🔢 Channel Mapping

The FreeEEG32 inputs are mapped as follows. Unused channels should be left floating or grounded depending on hardware revision.

| FreeEEG Channel | 10-20 Location |
| :--- | :--- |
| **CH01** | T7 |
| **CH02** | C3 |
| CH03 | *NC* |
| CH04 | *NC* |
| **CH05** | T8 |
| **CH06** | FC4 |
| CH07 | *NC* |
| CH08 | *NC* |
| **CH09** | FC3 |
| **CH10** | C4 |
| CH11 | *NC* |
| CH12 | *NC* |
| **CH13** | CP3 |
| **CH14** | CP4 |
| CH15-16 | *NC* |
| **CH17** | **Cz** |
| CH18-32 | *NC* |

## ⚡ Reference & Ground

| Pin / Input | Function | Location |
| :--- | :--- | :--- |
| **REF** | Signal Reference | M1 + M2 (linked) |
| **GND** | VCM / Bias | Fpz or Fz |

## 🛠 Usage & Re-Referencing

To use this montage in your analysis:

1.  Open `config/analysis/default_offline.yaml`
2.  Set `montage_profile: freg9`

### 🧪 SNR Optimization (Weighted Laplacian)

For vibrotactile frequency tagging, SNR can be improved by 3–6× using a weighted Laplacian reference.

**S1_left** = C3 − (2·FC3 + 2·CP3 + Cz + T7) / 6
**S1_right** = C4 − (2·FC4 + 2·CP4 + Cz + T8) / 6

| Method | Expected SNR |
| :--- | :--- |
| Raw (REF) | 1× |
| Average Reference | ~1.5× |
| **Weighted Laplacian** | **3–6×** |
