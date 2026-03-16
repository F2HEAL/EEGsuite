import numpy as np
import time
from pylsl import StreamInfo, StreamOutlet, local_clock

# -------------------------------------------------------
# CONFIGURATION (SynAmps-like)
# -------------------------------------------------------
n_channels = 32
sfreq = 1000  # Hz (SynAmps default)
chunk_size = 10  # Balanced chunk size for stable rate
stream_name = "SynAmpsRT"
stream_type = "EEG"
manufacturer = "Compumedics Neuroscan"
model = "SynAmps RT"

# Typical 32-channel SynAmps / 10-20 naming
channel_labels = [
    "Fp1","Fp2","F3","F4","C3","C4","P3","P4",
    "O1","O2","F7","F8","T7","T8","P7","P8",
    "Fz","Cz","Pz","Oz","FC1","FC2","CP1","CP2",
    "FC5","FC6","CP5","CP6","TP9","TP10","POz","Iz"
]

# -------------------------------------------------------
# CREATE LSL STREAMINFO WITH METADATA
# -------------------------------------------------------
info = StreamInfo(stream_name, stream_type, n_channels, sfreq, 'float32', "synamps1234")

# Add metadata (very SynAmps-like)
desc = info.desc()
desc.append_child_value("manufacturer", manufacturer)
desc.append_child_value("model", model)

# Channel descriptors
ch = desc.append_child("channels")
for name in channel_labels:
    c = ch.append_child("channel")
    c.append_child_value("label", name)
    c.append_child_value("unit", "microvolts")
    c.append_child_value("type", "EEG")

# -------------------------------------------------------
# CREATE OUTLET
# -------------------------------------------------------
outlet = StreamOutlet(info, chunk_size)

print(">>> Synthetic 32-ch SynAmps LSL stream is LIVE...")
print(">>> Name :", stream_name)
print(">>> Type :", stream_type)
print(">>> Fs   :", sfreq)
print(">>> Chunk size:", chunk_size)
print(">>> Target rate: 1000 samples/sec")
print(">>> Use any LSL viewer (LabRecorder, MNE-LSL, etc.) to see it.\n")

# -------------------------------------------------------
# PERFORMANCE OPTIMIZATIONS
# -------------------------------------------------------
# Pre-allocate arrays
timepoints_template = np.arange(chunk_size) / sfreq
eeg_data = np.zeros((chunk_size, n_channels), dtype='float32')

# Pre-compute phase increments
alpha_freq = 10  # Hz
beta_freq = 20   # Hz
alpha_phase_inc = 2 * np.pi * alpha_freq / sfreq
beta_phase_inc = 2 * np.pi * beta_freq / sfreq

# -------------------------------------------------------
# HIGH-PRECISION TIMING LOOP
# -------------------------------------------------------
sample_count = 0
start_time = time.perf_counter()
next_chunk_time = start_time
alpha_phase = 0.0
beta_phase = 0.0

print(">>> Starting stream with precise timing control...")

try:
    while True:
        current_time = time.perf_counter()
        
        # Wait until it's time for the next chunk
        if current_time < next_chunk_time:
            time.sleep(max(0, next_chunk_time - current_time - 0.001))  # Small buffer
            continue
            
        # Generate synthetic EEG for this chunk
        for ch_id in range(n_channels):
            # Channel-specific phase offsets
            ch_alpha_phase = alpha_phase + ch_id * 0.1
            ch_beta_phase = beta_phase + ch_id * 0.05
            
            # Generate the signal for this channel across all timepoints in chunk
            for t_idx in range(chunk_size):
                global_time = sample_count + t_idx
                alpha_val = 20 * np.sin(ch_alpha_phase + alpha_phase_inc * global_time)
                beta_val = 10 * np.sin(ch_beta_phase + beta_phase_inc * global_time)
                noise_val = np.random.normal(0, 5)
                eeg_data[t_idx, ch_id] = alpha_val + beta_val + noise_val
        
        # Push the chunk with precise timestamp
        outlet.push_chunk(eeg_data.tolist())
        
        # Update counters
        sample_count += chunk_size
        alpha_phase += alpha_phase_inc * chunk_size
        beta_phase += beta_phase_inc * chunk_size
        
        # Schedule next chunk precisely
        next_chunk_time = start_time + (sample_count / sfreq)
        
        # Performance monitoring
        if sample_count % 5000 == 0:  # Report every 5 seconds of data
            elapsed = time.perf_counter() - start_time
            actual_rate = sample_count / elapsed
            drift = (actual_rate - sfreq) / sfreq * 100
            print(f"Rate: {actual_rate:.1f} Hz ({drift:+.2f}% drift)")
            
except KeyboardInterrupt:
    total_time = time.perf_counter() - start_time
    final_rate = sample_count / total_time
    print(f"\n>>> Stream stopped.")
    print(f">>> Final rate: {final_rate:.1f} samples/sec")
    print(f">>> Target rate: {sfreq} samples/sec")
    print(f">>> Duration: {total_time:.2f} seconds")
    print(f">>> Total samples: {sample_count}") 