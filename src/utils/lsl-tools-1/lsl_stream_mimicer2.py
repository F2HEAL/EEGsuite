from pylsl import StreamInfo, StreamOutlet
import numpy as np
import time
import random

# -----------------------------
# EEG STREAM (SynAmps-style)
# -----------------------------
n_channels = 32
sfreq = 1000  # SynAmps RT typical sampling rate (250, 500, 1000 Hz supported)

info = StreamInfo(
    name='SynAmps_RT_EEG',
    type='EEG',
    channel_count=n_channels,
    nominal_srate=sfreq,
    channel_format='float32',
    source_id='synamps_rt_mock_01'
)

# Add XML metadata (Curry-like)
channels = info.desc().append_child("channels")
default_labels = [
    "Fp1","Fp2","F7","F3","Fz","F4","F8",
    "T3","C3","Cz","C4","T4",
    "T5","P3","Pz","P4","T6",
    "O1","Oz","O2",
] + [f"EX{i}" for i in range(32-20)]  # mock extra channels

for ch in default_labels:
    ch_info = channels.append_child("channel")
    ch_info.append_child_value("label", ch)
    ch_info.append_child_value("type", "EEG")
    ch_info.append_child_value("unit", "uV")

outlet = StreamOutlet(info)

# -----------------------------------
# MARKER STREAM (optional)
# -----------------------------------
marker_info = StreamInfo(
    'SynAmps_RT_Markers',
    'Markers',
    1,
    0,            # irregular sampling rate
    'string',
    'synamps_rt_markers_01'
)
marker_outlet = StreamOutlet(marker_info)

print("Mock SynAmps RT EEG + Marker LSL stream started…")
print("Press Ctrl+C to stop.")

# -----------------------------------
# STREAMING LOOP
# -----------------------------------
sample_interval = 1.0 / sfreq

try:
    while True:
        # generate mock EEG sample
        sample = np.random.randn(n_channels).astype(np.float32) * 5.0  # ~5 µV noise
        
        outlet.push_sample(sample)
        
        # occasional marker
        if random.random() < 0.001:   # ~1 marker per second
            marker_outlet.push_sample(["Stimulus"])
        
        time.sleep(sample_interval)

except KeyboardInterrupt:
    print("Stopped mock SynAmps stream.")
