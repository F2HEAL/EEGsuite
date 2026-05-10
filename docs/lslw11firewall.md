
# Firewall Configuration for Lab Streaming Layer (LSL)

This guide provides the necessary steps to configure the Firewall (Windows 11 or Linux) to allow seamless EEG data streaming via the **Lab Streaming Layer (LSL)** protocol.

## Introduction

LSL relies on **UDP Multicast** for stream discovery and **TCP/UDP** for data transmission. By default, many security policies block these communications.

## Terminology

*   **Acquisition Node (Outlet)**: The computer physically connected to the EEG hardware (e.g., FreeEEG32). It broadcasts the data stream.
*   **Visualization/Analysis Node (Inlet)**: The computer(s) receiving the data for real-time monitoring or recording.

## Windows 11 Configuration

### 1. Set Network Profile to "Private"
Windows blocks LSL discovery on "Public" networks. Ensure your connection is set to **Private**.

1.  Open **Settings** > **Network & internet**.
2.  Select your active connection (**Ethernet** or **Wi-Fi**).
3.  Change **Network profile type** to **Private**.

### 2. Configure Firewall Port Exceptions
LSL requires specific ports to be open on **both** the Acquisition and Visualization nodes.

*   **UDP Port 16571**: Required for stream discovery.
*   **TCP & UDP Ports 16572–16604**: Required for data transmission.

#### Automated Setup (Recommended)
Run the following command in an **Administrative PowerShell** terminal to automatically create the necessary firewall rules:

```powershell
# Create inbound rule for LSL Discovery
New-NetFirewallRule -DisplayName "LSL Discovery (UDP-In)" -Direction Inbound -LocalPort 16571 -Protocol UDP -Action Allow

# Create inbound rule for LSL Data
New-NetFirewallRule -DisplayName "LSL Data (TCP/UDP-In)" -Direction Inbound -LocalPort 16572-16604 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "LSL Data (TCP/UDP-In)" -Direction Inbound -LocalPort 16572-16604 -Protocol UDP -Action Allow
```

---

## Linux Configuration (UFW)

If you use `ufw` (Uncomplicated Firewall) on Linux (e.g., Ubuntu), run the following:

```bash
# Allow LSL Discovery
sudo ufw allow 16571/udp

# Allow LSL Data (TCP & UDP)
sudo ufw allow 16572:16604/tcp
sudo ufw allow 16572:16604/udp
```
