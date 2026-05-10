# Montages

## FREG8 8-Channel Montage

This montage focuses on the central and parietal regions (C3, C4, Cz area).

### Layout

```text
       FC3     FC4
         \     /
    T7----C3--C4----T8
         /     \
       CP3     CP4
```

### Channel Mapping

The FreeEEG32 inputs are mapped as follows. Unused channels should be left floating or grounded depending on hardware revision.

| FreeEEG Channel | 10-20 Location |
|:----------------|:---------------|
| **CH01**        | T7             |
| **CH02**        | C3             |
| CH03            | *NC*           |
| CH04            | *NC*           |
| **CH05**        | T8             |
| **CH06**        | FC4            |
| CH07            | *NC*           |
| CH08            | *NC*           |
| **CH09**        | FC3            |
| **CH10**        | C4             |
| CH11            | *NC*           |
| CH12            | *NC*           |
| **CH13**        | CP3            |
| **CH14**        | CP4            |
| CH15-32         | *NC*           |

### Reference & VCM_Bias

| Pin / Input  | Function         | Location                |
|:-------------|:-----------------|:------------------------|
| **REF**      | Signal Reference | Linked Ears             |
| **VCM/Bias** | VCM / Bias       | GND, between Fpz and Fz |



##  FREG9 9-Channel Montage

### Layout

This montage focuses on the central and parietal regions (C3, C4, Cz area).

```text
       FC3          FC4
          \          /
     T7----C3--Cz--C4----T8
          /          \
        CP3          CP4
```

### Channel Mapping

The FreeEEG32 inputs are mapped as follows. Unused channels should be left floating or grounded depending on hardware revision.

| FreeEEG Channel | 10-20 Location |
|:----------------|:---------------|
| **CH01**        | T7             |
| **CH02**        | C3             |
| CH03            | *NC*           |
| CH04            | *NC*           |
| **CH05**        | T8             |
| **CH06**        | FC4            |
| CH07            | *NC*           |
| CH08            | *NC*           |
| **CH09**        | FC3            |
| **CH10**        | C4             |
| CH11            | *NC*           |
| CH12            | *NC*           |
| **CH13**        | CP3            |
| **CH14**        | CP4            |
| CH15-16         | *NC*           |
| **CH17**        | Cz             |
| CH18-32         | *NC*           |

### Reference & VCM_Bias

| Pin / Input  | Function         | Location                |
|:-------------|:-----------------|:------------------------|
| **REF**      | Signal Reference | M1 + M2 (linked)        |
| **VCM/Bias** | VCM / Bias       | GND, between Fpz and Fz |

#### SNR Optimization (Weighted Laplacian)

For vibrotactile frequency tagging, SNR can be improved by 3–6× using a weighted Laplacian reference.

**S1_left** = C3 − (2·FC3 + 2·CP3 + Cz + T7) / 6
**S1_right** = C4 − (2·FC4 + 2·CP4 + Cz + T8) / 6

| Method | Expected SNR |
| :--- | :--- |
| Raw (REF) | 1× |
| Average Reference | ~1.5× |
| **Weighted Laplacian** | **3–6×** |

## KULLAB 32-Channel EEG Montage


### Electrode Layout

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

