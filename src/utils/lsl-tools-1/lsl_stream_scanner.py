# lsl_stream_scanner.py
from pylsl import resolve_streams, StreamInlet
import time

def scan_lsl_streams():
    """
    Scan for all available LSL streams and display comprehensive metadata
    """
    print("🔍 Scanning for LSL streams...")
    print("=" * 80)
    
    try:
        # Find all available streams
        streams = resolve_streams()
        
        if not streams:
            print("❌ No LSL streams found!")
            return []
        
        print(f"✅ Found {len(streams)} LSL stream(s)\n")
        
        stream_data = []
        
        for i, stream_info in enumerate(streams):
            print(f"📊 STREAM #{i+1}")
            print("-" * 40)
            
            stream_metadata = extract_stream_metadata(stream_info, i)
            stream_data.append(stream_metadata)
            
            # Try to connect for real-time data verification
            test_stream_connection(stream_info)
            
            print()  # Empty line between streams
        
        return stream_data
        
    except Exception as e:
        print(f"❌ Error during stream scanning: {e}")
        import traceback
        traceback.print_exc()
        return []

def extract_stream_metadata(stream_info, stream_index):
    """
    Extract comprehensive metadata from an LSL stream
    """
    metadata = {
        'index': stream_index,
        'name': stream_info.name(),
        'type': stream_info.type(),
        'channel_count': stream_info.channel_count(),
        'nominal_srate': stream_info.nominal_srate(),
        'source_id': stream_info.source_id(),
        'hostname': stream_info.hostname(),
        'version': stream_info.version(),
        'created_at': stream_info.created_at(),
        'uid': stream_info.uid(),
        'session_id': stream_info.session_id(),
        'channel_names': [],
        'channel_units': [],
        'additional_metadata': {}
    }
    
    # Display basic info
    print(f"  Name: {metadata['name']}")
    print(f"  Type: {metadata['type']}")
    print(f"  Channels: {metadata['channel_count']}")
    print(f"  Sample Rate: {metadata['nominal_srate']} Hz")
    print(f"  Source ID: {metadata['source_id']}")
    print(f"  Hostname: {metadata['hostname']}")
    print(f"  Protocol Version: {metadata['version']}")
    print(f"  Created: {time.ctime(metadata['created_at'])}")
    print(f"  UID: {metadata['uid']}")
    print(f"  Session ID: {metadata['session_id']}")
    
    # Try to get detailed info by creating an inlet
    try:
        inlet = StreamInlet(stream_info, max_buflen=1, processing_flags=0)
        info = inlet.info()
        
        # Get channel details
        desc = info.desc()
        channels = desc.child("channels")
        
        if not channels.empty():
            print(f"  📋 Channel Details:")
            channel = channels.first_child()
            ch_idx = 0
            
            while not channel.empty():
                # Channel label
                name_node = channel.child("label")
                channel_name = f"Channel_{ch_idx + 1}"
                if not name_node.empty():
                    name_val = name_node.first_child()
                    if not name_val.empty():
                        channel_name = name_val.value()
                        metadata['channel_names'].append(channel_name)
                
                # Channel unit
                unit_node = channel.child("unit")
                channel_unit = "unknown"
                if not unit_node.empty():
                    unit_val = unit_node.first_child()
                    if not unit_val.empty():
                        channel_unit = unit_val.value()
                        metadata['channel_units'].append(channel_unit)
                
                # Channel type
                type_node = channel.child("type")
                channel_type = "unknown"
                if not type_node.empty():
                    type_val = type_node.first_child()
                    if not type_val.empty():
                        channel_type = type_val.value()
                
                print(f"    {ch_idx + 1:2d}: {channel_name:15} [{channel_unit:8}] ({channel_type})")
                
                channel = channel.next_sibling()
                ch_idx += 1
        
        # Get additional metadata
        print(f"  🔧 Additional Metadata:")
        metadata_fields = [
            "manufacturer", "model", "subject", "session", "experiment",
            "description", "serial_number", "firmware_version", "hardware_version"
        ]
        
        for field in metadata_fields:
            node = desc.child(field)
            if not node.empty():
                value_node = node.first_child()
                if not value_node.empty():
                    field_value = value_node.value()
                    metadata['additional_metadata'][field] = field_value
                    print(f"    {field.replace('_', ' ').title()}: {field_value}")
        
        if not metadata['additional_metadata']:
            print("    No additional metadata available")
            
    except Exception as e:
        print(f"  ⚠️  Could not retrieve detailed metadata: {e}")
    
    return metadata

def test_stream_connection(stream_info):
    """
    Test if we can actually receive data from the stream
    """
    print(f"  🔄 Connection Test:")
    
    try:
        # Create inlet with short timeout
        inlet = StreamInlet(stream_info, max_buflen=1, processing_flags=0)
        
        # Try to get a single sample
        sample, timestamp = inlet.pull_sample(timeout=2.0)
        
        if sample is not None:
            print(f"    ✅ SUCCESS - Received {len(sample)} channel sample")
            print(f"       First 5 values: {sample[:5]}")
            print(f"       Timestamp: {timestamp:.6f}")
            
            # Try to get a chunk of data
            samples, timestamps = inlet.pull_chunk(timeout=1.0, max_samples=5)
            if samples:
                print(f"       Chunk test: {len(samples)} samples received")
            
        else:
            print(f"    ⚠️  No data received (stream might be inactive)")
        
    except Exception as e:
        print(f"    ❌ Connection failed: {e}")

def print_stream_summary(stream_data):
    """
    Print a summary table of all discovered streams
    """
    if not stream_data:
        return
    
    print("\n" + "=" * 80)
    print("📈 STREAM SUMMARY")
    print("=" * 80)
    
    print(f"{'#':<2} {'Name':<20} {'Type':<15} {'Channels':<8} {'Rate (Hz)':<10} {'Status':<10}")
    print("-" * 80)
    
    for stream in stream_data:
        status = "✅ Active" if stream.get('channel_names') else "⚠️  Limited"
        rate = stream['nominal_srate']
        rate_str = f"{rate:.1f}" if rate > 0 else "Irregular"
        
        print(f"{stream['index']+1:<2} {stream['name']:<20} {stream['type']:<15} "
              f"{stream['channel_count']:<8} {rate_str:<10} {status:<10}")

def continuous_monitor(scan_interval=5.0, duration=30.0):
    """
    Continuously monitor for stream changes
    """
    print(f"\n🔄 Continuous Monitoring (every {scan_interval}s for {duration}s)")
    print("Press Ctrl+C to stop monitoring")
    
    start_time = time.time()
    previous_streams = set()
    
    try:
        while time.time() - start_time < duration:
            current_streams = resolve_streams()
            current_names = {s.name() for s in current_streams}
            
            if current_names != previous_streams:
                print(f"\n⏰ {time.strftime('%H:%M:%S')} - Stream changes detected!")
                
                new_streams = current_names - previous_streams
                gone_streams = previous_streams - current_names
                
                if new_streams:
                    print(f"   ➕ New streams: {', '.join(new_streams)}")
                if gone_streams:
                    print(f"   ➖ Gone streams: {', '.join(gone_streams)}")
                
                previous_streams = current_names
            
            time.sleep(scan_interval)
            
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")

def quick_scan():
    """
    Quick scan - just list available streams without detailed metadata
    """
    print("🚀 Quick LSL Stream Scan")
    print("=" * 50)
    
    try:
        streams = resolve_streams()
        
        if not streams:
            print("❌ No LSL streams found!")
            return
        
        print(f"✅ Found {len(streams)} stream(s):\n")
        
        for i, stream in enumerate(streams):
            print(f"{i+1}. {stream.name()} [{stream.type()}]")
            print(f"   Channels: {stream.channel_count()}, Rate: {stream.nominal_srate()} Hz")
            print(f"   Source: {stream.source_id()}")
            print()
            
    except Exception as e:
        print(f"❌ Scan error: {e}")

if __name__ == "__main__":
    import sys
    
    # Check for quick scan option
    if len(sys.argv) > 1 and sys.argv[1] in ['-q', '--quick']:
        quick_scan()
    else:
        # Full comprehensive scan
        stream_data = scan_lsl_streams()
        
        # Print summary
        print_stream_summary(stream_data)
        
        # Optional: Continuous monitoring
        if stream_data:
            try:
                user_input = input("\n🔍 Start continuous monitoring? (y/n): ").lower().strip()
                if user_input in ['y', 'yes']:
                    continuous_monitor(scan_interval=5.0, duration=60.0)
            except KeyboardInterrupt:
                pass
        
        print("\n🎯 Scan complete!")