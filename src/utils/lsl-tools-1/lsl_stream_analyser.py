# lsl_stream_analyser.py
from pylsl import resolve_streams, StreamInlet
import time
import numpy as np
import sys
import argparse
from pathlib import Path

# Default stream name if not specified via command line
DEFAULT_STREAM_NAME = "BrainFlowEEG"

def debug_lsl_stream(stream_name=DEFAULT_STREAM_NAME):
    """Debug and inspect an LSL stream with comprehensive metadata extraction."""
    
    print(f"Looking for LSL stream: {stream_name}")
    
    # Find all streams
    streams = resolve_streams()
    print(f"Found {len(streams)} LSL stream(s):")
    
    for i, stream in enumerate(streams):
        print(f"\n[{i}] {stream.name()}")
        print(f"    Type: {stream.type()}")
        print(f"    Channels: {stream.channel_count()}")
        print(f"    Sample Rate: {stream.nominal_srate()} Hz")
        print(f"    Source ID: {stream.source_id()}")
        print(f"    Hostname: {stream.hostname()}")
        print(f"    Protocol Version: {stream.version()}")
        print(f"    Created at: {stream.created_at()}")
        print(f"    UID: {stream.uid()}")
        print(f"    Session ID: {stream.session_id()}")
    
    # Try to connect to the specific stream
    target_streams = [s for s in streams if s.name() == stream_name]
    
    if not target_streams:
        print(f"\n[!] Stream '{stream_name}' not found!")
        print("Available streams:")
        for stream in streams:
            print(f"  - {stream.name()} (type: {stream.type()})")
        return False, None, None
    
    print(f"\nFound target stream: {stream_name}")
    stream = target_streams[0]
    
    # Create inlet to get FULL metadata
    try:
        inlet = StreamInlet(stream)
        print("StreamInlet created successfully")
        
        # Get complete stream info
        info = inlet.info()
        print(f"\nCOMPLETE STREAM METADATA:")
        print(f"  Name: {info.name()}")
        print(f"  Type: {info.type()}")
        print(f"  Channel Count: {info.channel_count()}")
        print(f"  Nominal Sample Rate: {info.nominal_srate()} Hz")
        print(f"  Source ID: {info.source_id()}")
        print(f"  Hostname: {info.hostname()}")
        print(f"  Protocol Version: {info.version()}")
        print(f"  Created at: {info.created_at()}")
        print(f"  UID: {info.uid()}")
        print(f"  Session ID: {info.session_id()}")
        
        # Channel-specific information
        print(f"\nCHANNEL INFORMATION:")
        desc = info.desc()
        channels = desc.child("channels")
        if channels.empty():
            print("  No detailed channel information available")
        else:
            channel = channels.first_child()
            ch_idx = 0
            while not channel.empty():
                print(f"  Channel {ch_idx + 1}:")
                name = channel.child("label")
                if not name.empty():
                    print(f"    Label: {name.first_child().value()}")
                unit = channel.child("unit")
                if not unit.empty():
                    print(f"    Unit: {unit.first_child().value()}")
                type_node = channel.child("type")
                if not type_node.empty():
                    print(f"    Type: {type_node.first_child().value()}")
                channel = channel.next_sibling()
                ch_idx += 1
        
        # Stream description/metadata
        print(f"\nSTREAM DESCRIPTION:")
        if not desc.empty():
            # Try to get various description fields
            for field in ["manufacturer", "model", "subject", "session", "experiment"]:
                node = desc.child(field)
                if not node.empty():
                    value = node.first_child()
                    if not value.empty():
                        print(f"  {field.capitalize()}: {value.value()}")
        
        # Get channel names if available
        print(f"\nCHANNEL NAMES:")
        ch_names = []
        channels = desc.child("channels")
        if not channels.empty():
            channel = channels.first_child()
            while not channel.empty():
                name = channel.child("label")
                if not name.empty():
                    ch_name = name.first_child().value()
                    ch_names.append(ch_name)
                    print(f"  Channel {len(ch_names)}: {ch_name}")
                channel = channel.next_sibling()
        
        if not ch_names:
            print("  Using default channel names (no labels in stream)")
            ch_names = [f"Channel_{i+1}" for i in range(info.channel_count())]
        
        # Get a sample to verify data flow
        print(f"\nTESTING DATA FLOW:")
        sample, timestamp = inlet.pull_sample(timeout=5.0)
        if sample:
            print(f"Received sample with {len(sample)} channels")
            print(f"  First few values: {sample[:5]}")
            print(f"  Timestamp: {timestamp}")
            
            # Test multiple samples
            print(f"\nTESTING CONTINUOUS DATA:")
            samples, timestamps = inlet.pull_chunk(timeout=2.0, max_samples=10)
            if samples:
                print(f"Received {len(samples)} samples in chunk")
                print(f"  Sample shape: {len(samples)}x{len(samples[0])}")
                print(f"  Timestamps range: {timestamps[0]:.3f} to {timestamps[-1]:.3f}")
            else:
                print("[!] No chunk data received")
                
            return True, info, ch_names
        else:
            print("[!] No sample received within timeout")
            return False, None, None
            
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None

def analyze_sample_rate_drift(timestamps, nominal_rate, duration):
    """Analyze sample rate drift from timestamp data."""
    if len(timestamps) < 2:
        return {"error": "Insufficient timestamps for drift analysis"}
    
    # Calculate actual sample rates between consecutive samples
    inter_sample_intervals = np.diff(timestamps)
    instantaneous_rates = 1.0 / inter_sample_intervals
    
    # Calculate expected vs actual timing
    expected_duration = len(timestamps) / nominal_rate
    actual_duration = timestamps[-1] - timestamps[0]
    total_drift = actual_duration - expected_duration
    drift_ppm = (total_drift / expected_duration) * 1e6  # Parts per million
    
    # Statistics
    stats = {
        'nominal_rate': nominal_rate,
        'actual_mean_rate': len(timestamps) / actual_duration,
        'rate_error_percent': ((len(timestamps) / actual_duration - nominal_rate) / nominal_rate) * 100,
        'total_drift_seconds': total_drift,
        'drift_ppm': drift_ppm,
        'drift_per_minute': (total_drift / actual_duration) * 60,  # seconds per minute
        'instantaneous_rates_mean': np.mean(instantaneous_rates),
        'instantaneous_rates_std': np.std(instantaneous_rates),
        'instantaneous_rates_min': np.min(instantaneous_rates),
        'instantaneous_rates_max': np.max(instantaneous_rates),
        'intervals_mean': np.mean(inter_sample_intervals),
        'intervals_std': np.std(inter_sample_intervals),
        'intervals_cv': (np.std(inter_sample_intervals) / np.mean(inter_sample_intervals)) * 100,
        'jitter_ms': np.std(inter_sample_intervals) * 1000,  # RMS jitter in milliseconds
        'n_samples': len(timestamps),
        'duration_actual': actual_duration,
        'duration_expected': expected_duration
    }
    
    return stats

def print_stream_statistics(stream_name=DEFAULT_STREAM_NAME, duration=10):
    """Collect and print stream statistics over time with proper timing."""
    print(f"\nCOLLECTING STATISTICS FOR {duration} SECONDS:")
    
    target_streams = [s for s in resolve_streams() if s.name() == stream_name]
    if not target_streams:
        print(f"Stream '{stream_name}' not found for statistics")
        return
    
    inlet = StreamInlet(target_streams[0])
    nominal_rate = target_streams[0].nominal_srate()
    start_time = time.time()
    end_time = start_time + duration
    
    sample_count = 0
    chunk_counts = []
    chunk_timings = []
    all_timestamps = []  # Store all timestamps for drift analysis
    
    print("  Collecting data...", end="", flush=True)
    
    while time.time() < end_time:
        chunk_start = time.time()
        samples, timestamps = inlet.pull_chunk(timeout=0.1)  # Smaller timeout for more frequent updates
        chunk_end = time.time()
        
        if samples:
            chunk_counts.append(len(samples))
            sample_count += len(samples)
            chunk_timings.append(chunk_end - chunk_start)
            all_timestamps.extend(timestamps)
    
    actual_duration = time.time() - start_time
    
    if chunk_counts:
        print(" Done!")
        print(f"  Actual collection time: {actual_duration:.2f} seconds")
        print(f"  Total samples: {sample_count}")
        print(f"  Total chunks: {len(chunk_counts)}")
        print(f"  Average samples/sec: {sample_count/actual_duration:.1f}")
        print(f"  Average chunk size: {sum(chunk_counts)/len(chunk_counts):.1f}")
        print(f"  Chunks/sec: {len(chunk_counts)/actual_duration:.1f}")
        
        # Additional statistics
        if len(chunk_counts) > 1:
            print(f"  Chunk size range: {min(chunk_counts)} - {max(chunk_counts)}")
            print(f"  Average chunk interval: {sum(chunk_timings)/len(chunk_timings)*1000:.1f} ms")
            
        # Compare with nominal rate
        if nominal_rate > 0:
            expected_samples = nominal_rate * actual_duration
            efficiency = (sample_count / expected_samples) * 100
            print(f"  Nominal sample rate: {nominal_rate} Hz")
            print(f"  Data efficiency: {efficiency:.1f}%")
        
        # Analyze sample rate drift if we have enough timestamps
        if len(all_timestamps) >= 100:  # Need reasonable number of samples for meaningful analysis
            print(f"\nSAMPLE RATE DRIFT ANALYSIS:")
            drift_stats = analyze_sample_rate_drift(all_timestamps, nominal_rate, actual_duration)
            
            if 'error' not in drift_stats:
                print(f"  Actual mean rate: {drift_stats['actual_mean_rate']:.3f} Hz")
                print(f"  Rate error: {drift_stats['rate_error_percent']:+.3f}%")
                print(f"  Total drift: {drift_stats['total_drift_seconds']:+.6f} seconds")
                print(f"  Drift rate: {drift_stats['drift_ppm']:+.1f} ppm")
                print(f"  Drift per minute: {drift_stats['drift_per_minute']:+.3f} seconds")
                print(f"  Instantaneous rate: {drift_stats['instantaneous_rates_mean']:.2f} +/- {drift_stats['instantaneous_rates_std']:.2f} Hz")
                print(f"  Rate range: {drift_stats['instantaneous_rates_min']:.1f} - {drift_stats['instantaneous_rates_max']:.1f} Hz")
                print(f"  Interval jitter: {drift_stats['jitter_ms']:.3f} ms RMS")
                print(f"  Interval CV: {drift_stats['intervals_cv']:.2f}%")
                
                # Quality assessment
                if abs(drift_stats['rate_error_percent']) < 1.0:
                    quality = "Excellent"
                elif abs(drift_stats['rate_error_percent']) < 5.0:
                    quality = "Good"
                else:
                    quality = "Poor"
                print(f"  Timing quality: {quality}")
    else:
        print(" No data received during statistics collection")

def test_stream_performance(stream_name=DEFAULT_STREAM_NAME, test_duration=5):
    """Alternative performance test with more detailed metrics."""
    print(f"\nPERFORMANCE TEST FOR {test_duration} SECONDS:")
    
    target_streams = [s for s in resolve_streams() if s.name() == stream_name]
    if not target_streams:
        print(f"Stream '{stream_name}' not found")
        return
    
    inlet = StreamInlet(target_streams[0])
    nominal_rate = target_streams[0].nominal_srate()
    
    # Test parameters
    test_intervals = [0.01, 0.05, 0.1, 0.5]  # Different timeout intervals to test
    results = {}
    
    for interval in test_intervals:
        print(f"  Testing with {interval*1000:.0f}ms intervals...", end="", flush=True)
        start_time = time.time()
        end_time = start_time + test_duration
        samples_received = 0
        chunks_received = 0
        timestamps = []
        
        while time.time() < end_time:
            samples, chunk_timestamps = inlet.pull_chunk(timeout=interval, max_samples=1000)
            if samples:
                samples_received += len(samples)
                chunks_received += 1
                timestamps.extend(chunk_timestamps)
        
        actual_duration = time.time() - start_time
        drift_stats = analyze_sample_rate_drift(timestamps, nominal_rate, actual_duration) if len(timestamps) >= 10 else {}
        
        results[interval] = {
            'samples_per_sec': samples_received / actual_duration,
            'chunks_per_sec': chunks_received / actual_duration,
            'avg_chunk_size': samples_received / chunks_received if chunks_received > 0 else 0,
            'drift_stats': drift_stats
        }
        print(f" {samples_received} samples, {results[interval]['samples_per_sec']:.1f} samples/sec")
    
    # Print summary
    print(f"\nPERFORMANCE SUMMARY:")
    for interval, result in results.items():
        drift_info = ""
        if result['drift_stats'] and 'error' not in result['drift_stats']:
            drift_info = f", drift: {result['drift_stats']['rate_error_percent']:+.2f}%"
        
        print(f"  {interval*1000:4.0f}ms timeout: {result['samples_per_sec']:6.1f} samples/sec, "
              f"{result['chunks_per_sec']:5.1f} chunks/sec, "
              f"chunk size: {result['avg_chunk_size']:5.1f}{drift_info}")

def measure_sample_rate_drift(stream_name=DEFAULT_STREAM_NAME, measurement_duration=30):
    """Comprehensive sample rate drift measurement over longer duration."""
    print(f"\nCOMPREHENSIVE SAMPLE RATE DRIFT MEASUREMENT ({measurement_duration}s):")
    
    target_streams = [s for s in resolve_streams() if s.name() == stream_name]
    if not target_streams:
        print(f"Stream '{stream_name}' not found")
        return
    
    inlet = StreamInlet(target_streams[0])
    nominal_rate = target_streams[0].nominal_srate()
    
    print(f"  Nominal rate: {nominal_rate} Hz")
    print(f"  Measuring for {measurement_duration} seconds...")
    
    all_timestamps = []
    start_time = time.time()
    end_time = start_time + measurement_duration
    
    # Collect timestamps with minimal processing overhead
    while time.time() < end_time:
        samples, timestamps = inlet.pull_chunk(timeout=0.1, max_samples=1000)
        if samples:
            all_timestamps.extend(timestamps)
    
    actual_duration = time.time() - start_time
    
    if len(all_timestamps) >= 100:
        drift_stats = analyze_sample_rate_drift(all_timestamps, nominal_rate, actual_duration)
        
        print(f"\nPERFORMANCE MEASUREMENT RESULTS:")
        print(f"  Samples collected: {len(all_timestamps)}")
        print(f"  Measurement duration: {actual_duration:.2f} seconds")
        print(f"  Nominal sample rate: {drift_stats['nominal_rate']} Hz")
        print(f"  Actual mean rate: {drift_stats['actual_mean_rate']:.6f} Hz")
        print(f"  Rate error: {drift_stats['rate_error_percent']:+.6f}%")
        print(f"  Total time drift: {drift_stats['total_drift_seconds']:+.6f} seconds")
        print(f"  Drift rate: {drift_stats['drift_ppm']:+.2f} ppm")
        print(f"  Projected drift/hour: {drift_stats['drift_per_minute'] * 60:+.3f} seconds")
        print(f"  Instantaneous rate stability: {drift_stats['instantaneous_rates_std']:.3f} Hz std")
        print(f"  Sample interval jitter: {drift_stats['jitter_ms']:.3f} ms RMS")
        
        # Long-term stability assessment
        if abs(drift_stats['rate_error_percent']) < 0.1:
            stability = "Excellent (laboratory grade)"
        elif abs(drift_stats['rate_error_percent']) < 1.0:
            stability = "Good (research grade)"
        elif abs(drift_stats['rate_error_percent']) < 5.0:
            stability = "Fair (consumer grade)"
        else:
            stability = "Poor (unstable)"
        
        print(f"  Stability assessment: {stability}")
    else:
        print("  Insufficient data for drift analysis")

class Logger(object):
    """Simple logger to redirect stdout to both console and file."""
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze an LSL stream's performance and metadata.")
    parser.add_argument("-s", "--stream", type=str, default=DEFAULT_STREAM_NAME, 
                        help=f"Name of the LSL stream to analyze (default: {DEFAULT_STREAM_NAME})")
    args = parser.parse_args()
    
    stream_name = args.stream

    # Setup file logging
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_filename = f"lsl_stream_analysis_{stream_name.replace(' ', '_')}_{timestamp}.txt"
    
    # Path logic to write to /reports relative to the project root
    # File is at: src/utils/lsl-tools-1/lsl_stream_analyser.py
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    report_dir = project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    log_path = report_dir / log_filename
    
    sys.stdout = Logger(str(log_path))
    
    try:
        success, stream_info, channel_names = debug_lsl_stream(stream_name)
        
        if success:
            print(f"\nStream connection successful!")
            print(f"Channel names: {channel_names}")
            
            # Collect basic statistics with drift analysis
            print_stream_statistics(stream_name, duration=10)
            
            # Optional: Run detailed performance test
            print("\n" + "="*50)
            test_stream_performance(stream_name, test_duration=3)
            
            # Optional: Comprehensive drift measurement
            print("\n" + "="*50)
            measure_sample_rate_drift(stream_name, measurement_duration=10)
        else:
            print(f"\nFailed to connect to stream")
            
    finally:
        # Restore stdout and close file
        if hasattr(sys.stdout, "log"):
            output_path = sys.stdout.log.name
            sys.stdout.log.close()
            sys.stdout = sys.stdout.terminal
            print(f"\nFull debug log saved to: {output_path}")
