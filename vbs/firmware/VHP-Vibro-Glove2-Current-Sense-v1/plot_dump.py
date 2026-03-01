import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import argparse
import glob

def plot_current_log(filename, start_ms=None, stop_ms=None):
    try:
        # Sampling rate constants (46.875 kHz / 8)
        FS = 5859.375 
        MS_PER_SAMPLE = 1000.0 / FS

        # Manually find the header line index
        header_row = None
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                # Search for known headers
                if "SampleIndex,Voltage(V),Current(A)" in line:
                    header_row = i
                    break
                if "SampleIndex,Current(A)" in line:
                    header_row = i
                    break
        
        # Read csv from that header row (or without header if not found)
        if header_row is not None:
            df = pd.read_csv(filename, header=header_row, on_bad_lines='skip')
        else:
            # Skip preamble lines that don't contain commas
            skip_rows = 0
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if ',' in line and len(line.split(',')) >= 2:
                        skip_rows = i
                        break
            
            try:
                temp_df = pd.read_csv(filename, header=None, skiprows=skip_rows, nrows=5, on_bad_lines='skip')
                if len(temp_df.columns) >= 3:
                     df = pd.read_csv(filename, header=None, skiprows=skip_rows, names=['SampleIndex', 'Voltage(V)', 'Current(A)'], on_bad_lines='skip')
                else:
                     df = pd.read_csv(filename, header=None, skiprows=skip_rows, names=['SampleIndex', 'Current(A)'], on_bad_lines='skip')
            except Exception as e:
                print(f"Fallback reading failed: {e}")
                return
        
        # Filter to ensure we only have numeric data
        df = df[pd.to_numeric(df['SampleIndex'], errors='coerce').notnull()].copy()
        df['SampleIndex'] = df['SampleIndex'].astype(int)
        
        # Add Time in ms
        df['Time(ms)'] = df['SampleIndex'] * MS_PER_SAMPLE
        
        # Apply time window if specified
        if start_ms is not None:
            df = df[df['Time(ms)'] >= start_ms]
        if stop_ms is not None:
            df = df[df['Time(ms)'] <= stop_ms]

        if df.empty:
            print(f"No data found in the range {start_ms}ms to {stop_ms}ms")
            return

        # Plot
        fig = plt.figure(figsize=(12, 10))
        
        if 'Voltage(V)' in df.columns:
            # Dual plot
            ax1 = plt.subplot(2, 1, 1)
            ax1.plot(df['Time(ms)'], df['Voltage(V)'], label='Voltage (V)', color='orange', linewidth=0.8)
            ax1.set_title('VHP Oscilloscope Analysis: Voltage')
            ax1.set_ylabel('Voltage (V)')
            ax1.grid(True, which='both', linestyle='--', alpha=0.7)
            ax1.legend()
            
            # Second X-axis on top (Samples)
            ax1_top = ax1.secondary_xaxis('top', functions=(lambda x: x / MS_PER_SAMPLE, lambda x: x * MS_PER_SAMPLE))
            ax1_top.set_xlabel('Sample Index')

            ax2 = plt.subplot(2, 1, 2, sharex=ax1)
            ax2.plot(df['Time(ms)'], df['Current(A)'], label='Current (A)', color='blue', linewidth=0.8)
            ax2.set_title('VHP Oscilloscope Analysis: Current')
            ax2.set_xlabel('Time (ms)')
            ax2.set_ylabel('Current (Amps)')
            ax2.grid(True, which='both', linestyle='--', alpha=0.7)
            ax2.legend()
            
            # Print stats
            print(f"Mean Voltage: {df['Voltage(V)'].mean():.4f} V")
        else:
            # Single plot (Legacy)
            ax1 = plt.subplot(1, 1, 1)
            ax1.plot(df['Time(ms)'], df['Current(A)'], label='Current (A)', linewidth=0.8)
            ax1.set_title('VHP Current Dump Analysis')
            ax1.set_xlabel('Time (ms)')
            ax1.set_ylabel('Current (Amps)')
            ax1.grid(True, which='both', linestyle='--', alpha=0.7)
            ax1.legend()
            
            # Second X-axis on top (Samples)
            ax1_top = ax1.secondary_xaxis('top', functions=(lambda x: x / MS_PER_SAMPLE, lambda x: x * MS_PER_SAMPLE))
            ax1_top.set_xlabel('Sample Index')
        
        # Calculate current stats
        mean_current = df['Current(A)'].mean()
        std_current = df['Current(A)'].std()
        print(f"Mean Current: {mean_current:.6f} A")
        print(f"Std Dev: {std_current:.6f} A")
        
        output_file = filename.replace('.log', '').replace('.csv', '') + ".png"
        
        # Add range info to filename if used
        if start_ms is not None or stop_ms is not None:
            suffix = f"_{int(start_ms or 0)}to{int(stop_ms or df['Time(ms)'].max())}ms"
            output_file = output_file.replace('.png', suffix + ".png")

        plt.tight_layout()
        plt.savefig(output_file)
        print(f"Plot saved to: {output_file}")

    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze VHP current logs.')
    parser.add_argument('filename', nargs='?', help='Log file to process')
    parser.add_argument('--start', type=float, help='Start time in ms')
    parser.add_argument('--stop', type=float, help='Stop time in ms')
    
    args = parser.parse_args()
    
    log_file = args.filename
    if not log_file:
        # Search for any .log or .txt file in the current directory
        potential_files = glob.glob("*.log") + glob.glob("*.txt") + glob.glob("*.csv")
        if potential_files:
            potential_files.sort(key=os.path.getmtime, reverse=True)
            log_file = potential_files[0]
            print(f"No file specified. Using most recent log: {log_file}")
        else:
            print("No log files found in current directory.")
            sys.exit(1)
        
    if os.path.exists(log_file):
        plot_current_log(log_file, start_ms=args.start, stop_ms=args.stop)
    else:
        print(f"File not found: {log_file}")
