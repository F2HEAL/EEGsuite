# 🧠 FREG8 8-Channel Montage

This document describes the **FREG8** sparse montage, designed for targeted motor-cortex measurements using only 8 electrodes.

## 📍 Electrode Layout

This montage focuses on the central and parietal regions (C3, C4, Cz area).

```text
       FC3     FC4
         \     /
    T7----C3--C4----T8
         /     \
       CP3     CP4
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
| CH15-32 | *NC* |

## 🛠 Usage

To use this montage in your analysis:

1.  Open `config/analysis/default_offline.yaml`
2.  Set `montage_profile: freg8`

The system will automatically:
1.  Map the raw data to these labels.
2.  **Drop** all the `NC` (Not Connected) channels.
3.  Only display the 8 active channels in reports and topographies.
