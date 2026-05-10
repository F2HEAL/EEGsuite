# EEGsuite Hardware Architecture

## Hardware Connection Schematic

![System Architecture](assets/system_schematic.png)
*Note: Ensure USB Isolators are used as shown to maintain signal integrity.*

For details on the different supported montages see [Montages.md](Montages.md)

## Data Flow Structure

*High-level overview of the EEGsuite data flow and components.*

The hardware setup is designed for maximum signal purity and participant safety:

*   **Acquisition Node (Left)**: The FreeEEG32 is battery-powered (3x1.5V AA) and connected via a USB Isolator. The acquisition laptop should ideally run on DC power (battery) to eliminate 50/60Hz mains interference.
*   **Control Node (Center)**: The Master laptop manages the protocol and stimulation. It communicates with the acquisition node via a local Ethernet switch for low-latency LSL streaming.
*   **Visualization Node**: (Optional) A dedicated PC for real-time monitoring of EEG streams without adding load to the Control Node.
*   **Vibrotactile Stimulator (Right)**: A voice-coil-based actuator delivering precise tactile stimuli. It is electrically isolated from the EEG acquisition branch to prevent electromagnetic leakage.

