#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
sweep_only.py - Send VHP stimulation sweep commands via serial without EEG recording.

Uses CH_WEBUI_[1>8] channel naming convention.
Reads protocol and hardware config from YAML files and delivers stimulation patterns.
No EEG data collection, no CSV output, no user prompts.

Usage:
    python -m src.recording.sweep_only `
        --protocol config/protocols/sweep_only_default.yaml `
        --hardware config/hardware/vbs_only.yaml
"""

import logging
import time
import sys
import serial
import yaml
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

RANDOM_SEED: int = 42

# Channel naming convention: CH_WEBUI_[1>8]
CH_WEBUI_1: int = 1
CH_WEBUI_2: int = 2
CH_WEBUI_3: int = 3
CH_WEBUI_4: int = 4
CH_WEBUI_5: int = 5
CH_WEBUI_6: int = 6
CH_WEBUI_7: int = 7
CH_WEBUI_8: int = 8

CHANNEL_MAP: Dict[str, int] = {
    "CH_WEBUI_1": CH_WEBUI_1,
    "CH_WEBUI_2": CH_WEBUI_2,
    "CH_WEBUI_3": CH_WEBUI_3,
    "CH_WEBUI_4": CH_WEBUI_4,
    "CH_WEBUI_5": CH_WEBUI_5,
    "CH_WEBUI_6": CH_WEBUI_6,
    "CH_WEBUI_7": CH_WEBUI_7,
    "CH_WEBUI_8": CH_WEBUI_8,
}

logger = logging.getLogger(__name__)

def format_time_hms(seconds: float) -> str:
    """Converts seconds into human-readable format."""
    total_seconds: int = int(seconds)
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        return f"{total_seconds // 60}m{total_seconds % 60:02d}s"
    return f"{total_seconds // 3600}h{(total_seconds % 3600) // 60:02d}m"


class SerialCommunicator:
    """Handles serial communication with the VHP device."""
    
    BAUDRATE: int = 115200
    TIMEOUT: float = 0.1

    def __init__(self, port: str) -> None:
        self.port = port
        try:
            self.ser = serial.Serial(port=port, baudrate=self.BAUDRATE, timeout=self.TIMEOUT)
            if not self.ser.is_open:
                self.ser.open()
            logger.info("✅ Serial port %s opened at %d baud", port, self.BAUDRATE)
            time.sleep(0.5)
        except serial.SerialException as e:
            logger.error("❌ Could not open serial port %s: %s", port, e)
            raise

    def send_command(self, cmd: str, wait_resp: bool = False) -> None:
        """
        Send command to VHP device.
        
        Args:
            cmd: Command string (e.g., "C5", "V80", "F40", "1", "0")
            wait_resp: If True, read and log device response
        """
        full_cmd = f"{cmd}\n"
        self.ser.write(full_cmd.encode("utf-8"))
        self.ser.flush()
        
        if wait_resp:
            time.sleep(0.05)
            if self.ser.in_waiting:
                resp = self.ser.read_all().decode("utf-8", errors="ignore").strip()
                logger.info("VHP: %s → %s", cmd, resp)
            else:
                logger.info("VHP: %s", cmd)
        else:
            logger.info("VHP: %s", cmd)

    def set_channel(self, channel: int) -> None:
        """
        Set active channel using CH_WEBUI convention (1-8).
        
        Args:
            channel: Channel number from protocol (CH_WEBUI_1 through CH_WEBUI_8).
        """
        self.send_command(f"C{channel}")
        time.sleep(0.05)

    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)."""
        self.send_command(f"V{volume}")
        time.sleep(0.05)

    def set_frequency(self, frequency: int) -> None:
        """Set frequency in Hz."""
        self.send_command(f"F{frequency}")
        time.sleep(0.05)

    def start_stream(self) -> None:
        """Start stimulation."""
        self.send_command("1", wait_resp=False)

    def stop_stream(self) -> None:
        """Stop stimulation."""
        self.send_command("0", wait_resp=False)

    def close(self) -> None:
        """Close serial connection."""
        if hasattr(self, "ser") and self.ser.is_open:
            self.send_command("0", wait_resp=False)  # Ensure device is silenced
            time.sleep(0.1)
            self.ser.close()
            logger.info("Serial port closed")

    def dump_current_log(self) -> str:
        """
        Send 'C' command and read CSV dump from device.
        
        Returns:
            CSV data as string (including header)
        """
        self.ser.reset_input_buffer()
        time.sleep(0.1)
        self.send_command("C", wait_resp=False)
        time.sleep(0.2)  # Wait for device to send data
        
        csv_data = ""
        while self.ser.in_waiting:
            chunk = self.ser.read(256).decode("utf-8", errors="ignore")
            csv_data += chunk
            time.sleep(0.05)
        
        return csv_data


class VHPSweepOnly:
    """Delivers VHP stimulation sweeps with configurable protocol."""

    def __init__(self, protocol_yaml: Path, hardware_yaml: Path, output_dir: Optional[Path] = None) -> None:
        self.protocol = self._load_yaml(protocol_yaml)
        self.hardware = self._load_yaml(hardware_yaml)
        self.vhp: Optional[SerialCommunicator] = None
        self.start_time: float = 0.0
        self.output_dir = output_dir or Path("data/raw")

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        """Load YAML configuration file."""
        if not path.exists():
            logger.error("Configuration file not found: %s", path)
            sys.exit(1)
        
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        logger.info("Loaded config: %s", path)
        return config

    def connect(self) -> None:
        """Connect to VHP device."""
        serial_port = self.hardware.get("VHP", {}).get("Serial")
        if not serial_port:
            logger.error("❌ Serial port not specified in hardware config")
            sys.exit(1)
        
        try:
            self.vhp = SerialCommunicator(serial_port)
        except serial.SerialException as e:
            logger.error("❌ Failed to connect to VHP: %s", e)
            sys.exit(1)

    def render_progress(self, current: int, total: int) -> None:
        """Render progress bar."""
        if total <= 0:
            return
        
        percent = min(1.0, current / total)
        bar_length = 40
        filled = int(bar_length * percent)
        bar = "█" * filled + "-" * (bar_length - filled)
        elapsed = time.perf_counter() - self.start_time
        eta = (elapsed / current) * (total - current) if current > 0 else 0
        
        sys.stdout.write(f"\rSweep |{bar}| {percent*100:6.2f}% ETA: {format_time_hms(eta)}")
        sys.stdout.flush()

    def run_sweep(self) -> None:
        """Execute the sweep protocol."""
        if not self.vhp:
            logger.error("VHP not connected")
            return

        p = self.protocol
        
        # Extract sweep parameters
        ch_range = range(p["Channel"]["Start"], p["Channel"]["End"] + 1, p["Channel"]["Steps"])
        vol_range = range(p["Volume"]["Start"], p["Volume"]["End"] + 1, p["Volume"]["Steps"])
        freq_range = range(p["Frequency"]["Start"], p["Frequency"]["End"] + 1, p["Frequency"]["Steps"])
        
        num_measurements = p["Measurements"]["Number"]
        duration_on = p["Measurements"]["Duration_on"]
        duration_off = p["Measurements"]["Duration_off"]
        
        # Calculate total stimuli
        total_stimuli = len(ch_range) * len(vol_range) * len(freq_range) * num_measurements
        
        logger.info("Sweep Parameters:")
        logger.info("  Channels (CH_WEBUI): %d (start=CH_WEBUI_%d, end=CH_WEBUI_%d, step=%d)",
                   len(ch_range), p["Channel"]["Start"], p["Channel"]["End"], p["Channel"]["Steps"])
        logger.info("  Volumes: %d (start=%d, end=%d, step=%d)",
                   len(vol_range), p["Volume"]["Start"], p["Volume"]["End"], p["Volume"]["Steps"])
        logger.info("  Frequencies: %d (start=%d, end=%d, step=%d)",
                   len(freq_range), p["Frequency"]["Start"], p["Frequency"]["End"], p["Frequency"]["Steps"])
        logger.info("  Measurements per condition: %d", num_measurements)
        logger.info("  Duration ON: %.3f s, Duration OFF: %.3f s", duration_on, duration_off)
        logger.info("  Total stimuli: %d (Estimated time: %.1f min)", 
                   total_stimuli, total_stimuli * (duration_on + duration_off) / 60.0)
        logger.info("\n--- Starting Sweep ---\n")
        
        current_stimulus = 0
        self.start_time = time.perf_counter()
        
        try:
            for ch in ch_range:
                for vol in vol_range:
                    for freq in freq_range:
                        # Configure
                        self.vhp.set_channel(ch)
                        self.vhp.set_volume(vol)
                        self.vhp.set_frequency(freq)
                        
                        for measurement_idx in range(num_measurements):
                            # Rest period (OFF)
                            time.sleep(duration_off)
                            
                            # Stimulation period (ON)
                            self.vhp.start_stream()
                            time.sleep(duration_on)
                            self.vhp.stop_stream()
                            
                            current_stimulus += 1
                            self.render_progress(current_stimulus, total_stimuli)
        
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Sweep interrupted by user")
            self.vhp.stop_stream()
        
        except Exception as e:
            logger.error("❌ Error during sweep: %s", e)
            self.vhp.stop_stream()
            raise
        
        finally:
            elapsed = time.perf_counter() - self.start_time
            logger.info("\n\n✅ Sweep completed in %s", format_time_hms(elapsed))

    def run_capture(self, duration: float) -> None:
        """
        Run stimulation and capture current measurements for all sweep conditions.
        Saves all channels into a single CSV file with ActiveChannel column.
        
        Args:
            duration: Stimulation duration per condition in seconds
        """
        if not self.vhp:
            logger.error("VHP not connected")
            return
        
        p = self.protocol
        
        # Extract sweep parameters from YAML
        ch_range = range(p["Channel"]["Start"], p["Channel"]["End"] + 1, p["Channel"]["Steps"])
        vol_range = range(p["Volume"]["Start"], p["Volume"]["End"] + 1, p["Volume"]["Steps"])
        freq_range = range(p["Frequency"]["Start"], p["Frequency"]["End"] + 1, p["Frequency"]["Steps"])
        
        total_captures = len(ch_range) * len(vol_range) * len(freq_range)
        
        logger.info("Capture Mode - Multi-Channel Current Measurement (Single File)")
        logger.info("  Channels (CH_WEBUI): %d (start=CH_WEBUI_%d, end=CH_WEBUI_%d, step=%d)",
                   len(ch_range), p["Channel"]["Start"], p["Channel"]["End"], p["Channel"]["Steps"])
        logger.info("  Volumes: %d (start=%d, end=%d, step=%d)",
                   len(vol_range), p["Volume"]["Start"], p["Volume"]["End"], p["Volume"]["Steps"])
        logger.info("  Frequencies: %d (start=%d, end=%d, step=%d)",
                   len(freq_range), p["Frequency"]["Start"], p["Frequency"]["End"], p["Frequency"]["Steps"])
        logger.info("  Duration per condition: %.3f s", duration)
        logger.info("  Total captures: %d (Estimated time: %.1f min)\n",
                   total_captures, total_captures * duration / 60.0)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.start_time = time.perf_counter()
        current_capture = 0
        
        # Collect all CSV data
        all_csv_lines = []
        header_written = False
        total_samples = 0
        
        try:
            for ch in ch_range:
                for vol in vol_range:
                    for freq in freq_range:
                        # Configure device
                        self.vhp.set_channel(ch)
                        self.vhp.set_volume(vol)
                        self.vhp.set_frequency(freq)
                        time.sleep(0.1)
                        
                        # Start measurement
                        self.vhp.start_stream()
                        time.sleep(duration)
                        self.vhp.stop_stream()
                        time.sleep(0.2)
                        
                        # Dump current log
                        csv_output = self.vhp.dump_current_log()
                        
                        if csv_output:
                            lines = csv_output.strip().split("\n")
                            
                            # Write header only on first capture
                            if not header_written and len(lines) > 0:
                                all_csv_lines.append(lines[0])  # Header
                                header_written = True
                            
                            # Append data rows (skip header from subsequent captures)
                            for line in lines[1:]:
                                if line.strip():
                                    all_csv_lines.append(line)
                                    total_samples += 1
                            
                            sample_count = len(lines) - 1
                            logger.info("✅ CH_WEBUI_%d F%dHz V%d%% → %d samples",
                                       ch, freq, vol, sample_count)
                        else:
                            logger.warning("⚠️  CH_WEBUI_%d F%dHz V%d%% → No data received", ch, freq, vol)
                        
                        current_capture += 1
                        self.render_progress(current_capture, total_captures)
            
            # Save all data to single file
            if all_csv_lines:
                timestamp = datetime.now().strftime("%y%m%d-%H%M%S")
                freq_str = f"f{p['Frequency']['Start']}" if len(freq_range) == 1 else "fvary"
                vol_str = f"v{p['Volume']['Start']}" if len(vol_range) == 1 else "vvary"
                filename = self.output_dir / f"capture_{timestamp}_{freq_str}_{vol_str}.csv"
                
                with open(filename, "w") as f:
                    f.write("\n".join(all_csv_lines))
                
                logger.info("\n✅ All captures merged into single file")
                logger.info("   Total samples: %d", total_samples)
                logger.info("   📁 Saved to: %s", filename)

                # Correct channel coverage printout using pandas
                try:
                    df = pd.read_csv(filename)
                    found_channels = sorted(df['ActiveChannel'].unique())
                    # Expected channels from protocol (now 1-based: CH_WEBUI_1 through CH_WEBUI_8)
                    expected_channels = list(range(p['Channel']['Start'], p['Channel']['End'] + 1, p['Channel']['Steps']))
                    webui_names = [f"CH_WEBUI_{ch}" for ch in expected_channels]
                    found_webui_names = [f"CH_WEBUI_{ch}" for ch in found_channels]
                    print(f"\nCHANNEL COVERAGE: Found in CSV: {found_webui_names}")
                    missing = [ch for ch in expected_channels if ch not in found_channels]
                    if missing:
                        missing_names = [f"CH_WEBUI_{ch}" for ch in missing]
                        print(f"⚠️  Missing channels in CSV: {missing_names}")
                    else:
                        print(f"✅ All expected channels present in CSV: {webui_names}")
                except Exception as e:
                    print(f"⚠️  Could not validate channel coverage: {e}")
            else:
                logger.error("❌ No data captured")
        
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Capture interrupted by user")
            self.vhp.stop_stream()
        
        except Exception as e:
            logger.error("❌ Error during capture: %s", e)
            self.vhp.stop_stream()
            raise
        
        finally:
            elapsed = time.perf_counter() - self.start_time
            logger.info("⏱️  Capture sweep completed in %s", format_time_hms(elapsed))


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="VHP stimulation sweep delivery (serial commands only)"
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/protocols/sweep_only_default.yaml"),
        help="Protocol YAML file"
    )
    parser.add_argument(
        "--hardware",
        type=Path,
        default=Path("config/hardware/vbs_only.yaml"),
        help="Hardware YAML file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw"),
        help="Output directory for CSV captures"
    )
    parser.add_argument(
        "--capture",
        type=float,
        default=None,
        help="Capture mode: run single stimulation for N seconds and save CSV"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    
    logger.info("VHP Sweep Only - Starting")
    logger.info("Protocol: %s", args.protocol)
    logger.info("Hardware: %s", args.hardware)
    
    # Run sweep or capture
    try:
        sweep = VHPSweepOnly(args.protocol, args.hardware, args.output)
        sweep.connect()
        
        if args.capture:
            sweep.run_capture(args.capture)
        else:
            sweep.run_sweep()
    finally:
        if sweep.vhp:
            sweep.vhp.close()


if __name__ == "__main__":
    main()
