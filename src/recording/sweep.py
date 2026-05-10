import logging
import time
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Heavy imports moved inside classes to prevent hanging on startup
# from pylsl import StreamInlet, resolve_stream

from src.utils.paths import RAW_DATA_DIR, DATA_DIR
from src.utils.config import EEGConfig

logger = logging.getLogger(__name__)

RANDOM_SEED: int = 42
PROGRESS_BAR_LENGTH: int = 30

def format_time_hms(seconds: float) -> str:
    """Converts seconds into human-readable format."""
    total_seconds: int = int(seconds)
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        return f"{total_seconds // 60}m{total_seconds % 60:02d}s"
    return f"{total_seconds // 3600}h{(total_seconds % 3600) // 60:02d}m"

def wait_for_space(prompt: str) -> None:
    """Prompts the user and waits for a spacebar press."""
    print(f"\n{prompt}\nPress SPACEBAR then ENTER when ready...")
    
    # Flush stdin to avoid accidental skips if there's buffered input
    try:
        import msvcrt
        while msvcrt.kbhit():
            msvcrt.getch()
    except ImportError:
        # Fallback for non-Windows platforms
        import select
        while select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.readline()
            
    input()

class SerialCommunicator:
    """Handles serial communication with the VHP device."""
    
    BAUDRATE: int = 115200
    TIMEOUT: float = 0.1

    def __init__(self, port: str, silent: bool = False) -> None:
        import serial
        self.port = port
        try:
            self.ser = serial.Serial(port=port, baudrate=self.BAUDRATE, timeout=self.TIMEOUT)
            if not self.ser.is_open:
                self.ser.open()
            if not silent:
                print(f"DEBUG: Serial port {port} opened successfully.")
            time.sleep(2)
        except serial.SerialException as e:
            if not silent:
                logger.error("Could not open serial port %s: %s", port, e)
            raise

    def send_command(self, cmd: str, wait_for_resp: bool = True) -> None:
        """
        Sends a command to the serial device.
        
        Args:
            cmd: The command string to send.
            wait_for_resp: If True, waits 50ms to read and log the device response.
        """
        full_cmd = f"{cmd}\n"
        self.ser.write(full_cmd.encode("utf-8"))
        self.ser.flush()
        
        if not wait_for_resp:
            logger.info("VHP CMD: %s", cmd)
            return

        # Small delay for the device to process response
        time.sleep(0.05)
        if self.ser.in_waiting:
            resp = self.ser.read_all().decode("utf-8").strip()
            logger.info("VHP CMD: %s -> %s", cmd, resp)
        else:
            logger.info("VHP CMD: %s", cmd)

    def is_connected(self) -> bool:
        """Checks if the device is responsive."""
        try:
            return hasattr(self, "ser") and self.ser.is_open
        except:
            return False

    def set_channel(self, channel: int) -> None:
        self.send_command(f"C{channel}")

    def set_volume(self, volume: int) -> None:
        self.send_command(f"V{volume}")

    def set_frequency(self, frequency: int) -> None:
        self.send_command(f"F{frequency}")

    def start_stream(self) -> None:
        # Immediate return for timing precision
        self.send_command("1", wait_for_resp=False)

    def stop_stream(self) -> None:
        # Immediate return for timing precision
        self.send_command("0", wait_for_resp=False)

    def set_test_mode(self, enabled: bool) -> None:
        self.send_command(f"M{1 if enabled else 0}")

    def close(self) -> None:
        if hasattr(self, "ser") and self.ser.is_open:
            self.ser.close()

class EEGSweep:
    """Performs EEG measurements following the sweep protocol."""

    def __init__(self, config: EEGConfig) -> None:
        self.config = config
        self.inlet = None
        self.vhp: Optional[SerialCommunicator] = None
        self.timestamp: str = datetime.now().strftime("%y%m%d-%H%M")
        self.global_start_time: float = 0
        self.baseline_files: List[Path] = []

    def connect_lsl(self) -> None:
        """Resolves and connects to the LSL stream."""
        try:
            from pylsl import StreamInlet, resolve_stream
            resolver = "resolve_stream"
        except ImportError:
            from pylsl import StreamInlet, resolve_streams
            resolve_stream = None
            resolver = "resolve_streams"
        logger.info("Resolving LSL stream: '%s' (Timeout: 5s)...", self.config.stream_name)
        if resolve_stream is not None:
            # Use positional arguments: prop, value, minimum, timeout
            streams = resolve_stream("name", self.config.stream_name, 1, 5.0)
        else:
            # Fall back to resolve_streams() and filter by name for newer pylsl builds
            try:
                all_streams = resolve_streams(5.0)
            except TypeError:
                all_streams = resolve_streams()
            streams = [s for s in all_streams if s.name() == self.config.stream_name]
            logger.debug("Filtered %d streams using %s.", len(streams), resolver)

        
        if not streams:
            logger.error("Could not find LSL stream '%s'.", self.config.stream_name)
            logger.warning("Please ensure your LSL server is running!")
            sys.exit(1)
            
        self.inlet = StreamInlet(streams[0])
        self.num_channels = self.inlet.info().channel_count()
        logger.info("Connected to LSL stream with %d channels.", self.num_channels)
        
        # Verify EEG data is actually flowing - block until data arrives
        logger.info("Verifying EEG data stream...")
        data_verified = False
        while not data_verified:
            _, ts = self.inlet.pull_sample(timeout=2.0)
            if ts is not None:
                logger.info("EEG data flow verified.")
                data_verified = True
            else:
                logger.warning("No EEG data received within 2s.")
                wait_for_space("Check EEG hardware and LSL server. Is the board streaming?")
                logger.info("Retrying EEG verification...")
            
        # Drain stale data
        self.inlet.pull_chunk(timeout=0.0)

    def connect_vhp(self, silent: bool = False) -> None:
        """Connects to the VHP serial device."""
        if self.config.serial_port:
            try:
                self.vhp = SerialCommunicator(self.config.serial_port, silent=silent)
                # Small delay after successful port opening to let firmware stabilize
                time.sleep(1)
                if not silent:
                    logger.info("Connected to VHP on %s", self.config.serial_port)
            except Exception:
                if not silent:
                    logger.warning("VHP device not found on %s. Please check connection and power.", self.config.serial_port)
                self.vhp = None

    def record_to_csv(self, duration: float, writer: Any, marker: Optional[int]) -> None:
        """Records LSL data to CSV for a specified duration using pull_chunk."""
        start_time = time.time()
        marker_written: bool = False
        total_samples = 0

        while (time.time() - start_time) < duration:
            # Use a small timeout to block and wait for data instead of spinning
            samples, timestamps = self.inlet.pull_chunk(timeout=0.1)
            
            if timestamps:
                total_samples += len(timestamps)
                rows: List[List[Any]] = []
                for sample, ts in zip(samples, timestamps):
                    # Only write the marker on the very first sample of this duration block
                    label = str(marker) if (marker is not None and not marker_written) else ""
                    # Ensure sample is a list
                    sample_data = list(sample)
                    rows.append([ts] + sample_data[:self.num_channels] + [label])
                    marker_written = True
                
                writer.writerows(rows)
            # No else: sleep needed here as pull_chunk(timeout=0.1) handles it

        # Final drain
        samples, timestamps = self.inlet.pull_chunk(timeout=0.0)
        if timestamps:
            for sample, ts in zip(samples, timestamps):
                label = str(marker) if (marker is not None and not marker_written) else ""
                writer.writerow([ts] + list(sample)[:self.num_channels] + [label])
                marker_written = True
                total_samples += 1

        if total_samples == 0:
            logger.warning("No samples recorded for marker %s! Is the EEG stream sending data?", marker)
        else:
            logger.info("Recorded %d samples for marker %s", total_samples, marker)

    def render_progress(self, current: int, total: int) -> None:
        """Renders progress bar in terminal."""
        if total <= 0: return
        percent = min(1.0, current / total)
        filled = int(PROGRESS_BAR_LENGTH * percent)
        bar = "#" * filled + "-" * (PROGRESS_BAR_LENGTH - filled)
        elapsed = time.perf_counter() - self.global_start_time
        eta = (elapsed / current) * (total - current) if current > 0 else 0
        sys.stdout.write(f"\rSweep |{bar}| {percent*100:6.2f}% ETA: {format_time_hms(eta)}")
        sys.stdout.flush()

    def write_metadata(self) -> None:
        """Writes measurement metadata to a text file."""
        import yaml
        metadata_path = RAW_DATA_DIR / f"{self.timestamp}_metadata.txt"
        with open(metadata_path, "w") as f:
            f.write(f"Recording on: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
            f.write("*** Hardware Configuration ***\n")
            f.write(yaml.dump(self.config.hardware))
            f.write("\n*** Protocol Configuration ***\n")
            f.write(yaml.dump(self.config.protocol))
            f.write(f"\nBaseline Files: {[p.name for p in self.baseline_files]}\n")
        logger.info("Metadata saved to %s", metadata_path)

    def run_sweep(self) -> None:
        """Executes the full sweep protocol including baselines."""
        if not self.inlet:
            raise RuntimeError("LSL must be connected before sweep.")

        p = self.config.protocol
        
        # Calculate total steps early to avoid UnboundLocalError
        ch_start, ch_end, ch_step = p["Channel"]["Start"], p["Channel"]["End"], p["Channel"]["Steps"]
        freq_start, freq_end, freq_step = p["Frequency"]["Start"], p["Frequency"]["End"], p["Frequency"]["Steps"]
        vol_start, vol_end, vol_step = p["Volume"]["Start"], p["Volume"]["End"], p["Volume"]["Steps"]
        num_cycles = p["Measurements"]["Number"]
        
        # Ensure step is at least 1 to avoid infinite loops/division by zero
        ch_step = max(1, ch_step)
        freq_step = max(1, freq_step)
        vol_step = max(1, vol_step)
        
        total_steps = ((ch_end - ch_start)//ch_step + 1) * \
                      ((freq_end - freq_start)//freq_step + 1) * \
                      ((vol_end - vol_start)//vol_step + 1) * num_cycles

        # --- BASELINE 1: VHP OFF ---
        b1_dur = float(p.get("Baselines", {}).get("Baseline_1", 10.0))
        if b1_dur > 0:
            # Force disconnect for Baseline 1 (Environmental noise requires VHP OFF)
            if self.vhp:
                logger.info("Closing VHP connection for Baseline 1 (OFF phase)...")
                self.vhp.close()
                self.vhp = None

            wait_for_space(f"Calibration Phase | Marker 3: Baseline 1 (VHP OFF).\n"
                           f"Ensure VBS/VHP is powered OFF. Ready to record {b1_dur}s?")
            logger.info("Recording Baseline 1 (VHP OFF phase)...")
            b1_path = RAW_DATA_DIR / f"{self.timestamp}_{self.config.board_id}_baseline_VHP_OFF.csv"
            
            with open(b1_path, "w", newline="") as f:
                writer = csv.writer(f)
                self.record_to_csv(b1_dur, writer, marker=3)
            
            logger.info("Baseline 1 (VHP OFF) completed.")
            self.baseline_files.append(b1_path)

        # Transition to VHP ON (Required for Baseline 2 or Sweep)
        if self.config.serial_port and (not self.vhp or not self.vhp.is_connected()):
            logger.info("VBS/VHP connection required for next phases.")
            wait_for_space("ACTION: Switch the VBS device ON now.\n"
                           "Wait 3 seconds for the device status LED to stabilize.")
            
            logger.info("Attempting to initialize VBS device...")
            while not self.vhp or not self.vhp.is_connected():
                self.connect_vhp(silent=True)
                if not self.vhp or not self.vhp.is_connected():
                    logger.warning("VBS device not detected on %s.", self.config.serial_port)
                    wait_for_space("Ensure VBS is powered ON and connected, then press SPACEBAR to retry.")
            
            logger.info("VBS device connected and initialized.")

        # --- BASELINE 2: NO CONTACT (IFNFN) ---
        b2_dur = float(p.get("Baselines", {}).get("Baseline_2", 10.0))
        if b2_dur > 0:
            wait_for_space(f"Calibration Phase | Marker 31/33: Baseline 2 (No physical contact).\n"
                           f"1. Place finger 1 mm away from tactor nipple (IFNFN).\n"
                           f"2. Press SPACEBAR to record {b2_dur}s baseline.")
            logger.info("Recording Baseline 2 (VHP ON, STIM ON, no contact)...")
            
            b2_path = RAW_DATA_DIR / f"{self.timestamp}_{self.config.board_id}_baseline_NO_CONTACT.csv"
            
            if self.vhp:
                self.vhp.set_channel(ch_start)
                self.vhp.set_volume(vol_start)
                self.vhp.set_frequency(freq_start)
                self.vhp.start_stream()

            with open(b2_path, "w", newline="") as f:
                writer = csv.writer(f)
                self.record_to_csv(b2_dur, writer, marker=31)
                if self.vhp:
                    self.vhp.stop_stream()
                self.record_to_csv(b2_dur, writer, marker=33)
            
            self.baseline_files.append(b2_path)
            logger.info("Baseline 2 completed.")

        # --- SWEEP: CONTACT ---
        wait_for_space(f"Recording Phase | Marker 0/1/11: Sweep (Physical contact). "
                       f"Place finger(s) ON tactors. Ready for sweep ({total_steps} steps)?")
        
        current_step = 0
        self.global_start_time = time.perf_counter()
        
        if self.vhp:
            self.vhp.set_test_mode(True)

        for ch in range(ch_start, ch_end + 1, ch_step):
            for freq in range(freq_start, freq_end + 1, freq_step):
                for vol in range(vol_start, vol_end + 1, vol_step):
                    if self.vhp:
                        self.vhp.set_channel(ch)
                        self.vhp.set_frequency(freq)
                        self.vhp.set_volume(vol)
                    
                    filename = f"{self.config.board_id}_c{ch}_f{freq}_v{vol}.csv"
                    filepath = RAW_DATA_DIR / f"{self.timestamp}_{filename}"
                    
                    with open(filepath, "w", newline="") as f:
                        writer = csv.writer(f)
                        b3_dur = float(p.get("Baselines", {}).get("Baseline_3", 10.0))
                        if b3_dur > 0:
                            self.record_to_csv(b3_dur, writer, marker=333)
                        
                        for _ in range(num_cycles):
                            # Pre-Stim period (Rest)
                            self.record_to_csv(p["Measurements"]["Duration_off"], writer, marker=0)
                            
                            # Stim ON
                            if self.vhp:
                                self.vhp.start_stream()
                            self.record_to_csv(p["Measurements"]["Duration_on"], writer, marker=1)
                            if self.vhp:
                                self.vhp.stop_stream()
                            
                            # Stim OFF period (Post-stim rest)
                            self.record_to_csv(p["Measurements"]["Duration_off"], writer, marker=11)
                            
                            current_step += 1
                            self.render_progress(current_step, total_steps)
        
        print("\nSweep completed.")
        self.write_metadata()
