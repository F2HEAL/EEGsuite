# 🧠 KULLAB 32-Channel EEG Montage

This document describes the specific 32-channel EEG electrode layout used during measurements at **KULLAB**.

## 📍 Electrode Layout

The following ASCII diagram represents the physical placement of electrodes on the scalp (Frontal at the top):

```text
             FRONTAL
     F7----F3---Fz----F4---F8
     | \        |        / |
    FC5 FC1----FC2----FC6  |
     |    \     |     /    |
FT9--T7----C3---Cz---C4----T8--FT10
     |      \   |   /      |
    CP5-----CP1---CP2-----CP6
     |        \ | /        |
TP9--P7----P3---Pz----P4---P8--TP10
      \     |       |     /    
       \ O1--PO9 PO10-O2 /
        \  \  |   |   / /
         \  \ |   |  / /
          \__\| Iz| /_/
               \__/
```

## 🔢 Channel List (Order)

The hardware acquisition order for this montage is:

1.  **Row 1 (Frontal)**: F7, F3, Fz, F4, F8
2.  **Row 2**: FC5, FC1, FC2, FC6
3.  **Row 3 (Central)**: FT9, T7, C3, Cz, C4, T8, FT10
4.  **Row 4**: CP5, CP1, CP2, CP6
5.  **Row 5 (Parietal)**: TP9, P7, P3, Pz, P4, P8, TP10
6.  **Row 6 (Occipital)**: O1, PO9, PO10, O2
7.  **Row 7 (Inion)**: Iz

## 🛠 Integration in EEGsuite

This montage is natively supported in the analysis pipeline. To ensure correct spatial mapping and topographies, the `config/analysis/default_offline.yaml` is pre-configured with these labels.

**Hardware Config Note**: 
Ensure your `config/hardware/freeeeg.yaml` correctly maps these physical inputs to the 32 channels of the FreeEEG32 board.
