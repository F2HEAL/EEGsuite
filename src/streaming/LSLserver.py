import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional

from brainflow.board_shim import BoardIds, BoardShim, BrainFlowInputParams, LogLevels
from pylsl import StreamInfo, StreamOutlet

from src.utils.config import load_yaml

logger = logging.getLogger(__name__)

class LSLServer:
    """
    BrainFlow -> LSL bridge.
    Reads data from a BrainFlow-compatible device and streams it via LSL.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.board_shim: Optional[BoardShim] = None
        self.outlet: Optional[StreamOutlet] = None
        # Enable BrainFlow logging for better debugging
        BoardShim.enable_board_logger()
        BoardShim.set_log_level(LogLevels.LEVEL_INFO)

    def setup_board(self) -> None:
        """Configures the BrainFlow board based on provided settings."""
        params = BrainFlowInputParams()
        board_config = self.config.get("Board", {})

        if board_config.get("Master"):
            params.file = board_config["File"]
            params.master_board = BoardIds[board_config["Master"]].value
            board_id = BoardIds[board_config["Id"]].value
        else:
            if board_config.get("Mac"):
                params.mac_address = board_config["Mac"]
            if board_config.get("Serial"):
                params.serial_port = board_config["Serial"]
            board_id = BoardIds[board_config["Id"]].value

        self.board_shim = BoardShim(board_id, params)
        logger.info("Board object created. Attempting to prepare session...")
        
        # Prepare session BEFORE LSL setup to ensure hardware is ready
        self.board_shim.prepare_session()
        logger.info("Session prepared successfully.")

    def setup_lsl(self) -> None:
        """Initializes the LSL outlet with optional channel metadata."""
        if not self.board_shim:
            raise RuntimeError("Board must be set up before LSL.")

        board_id = self.board_shim.get_board_id()
        sampling_rate = BoardShim.get_sampling_rate(board_id)
        eeg_channels = BoardShim.get_eeg_channels(board_id)
        num_channels = len(eeg_channels)
        
        # Use a name from config if available
        stream_name = self.config.get("Board", {}).get("StreamName", "BrainFlowEEG")
        
        info = StreamInfo(
            stream_name,
            "EEG",
            num_channels,
            sampling_rate,
            "float32",
            f"brainflow_{board_id}",
        )

        # Handle Montage / Channel Names
        montage_path = self.config.get("montage_path")
        channel_names = []
        if montage_path:
            try:
                montage_cfg = load_yaml(Path(montage_path))
                channel_names = montage_cfg.get("channels", [])
                logger.info("Loaded montage from %s with %d names", 
                            montage_path, len(channel_names))
            except Exception as e:
                logger.error("Could not load montage file: %s", e)

        # Add metadata to the stream info
        channels_node = info.desc().append_child("channels")
        for i in range(num_channels):
            # Fallback to "Channel X" if montage is missing or too short
            label = channel_names[i] if i < len(channel_names) else f"Channel {i}"
            
            chan_node = channels_node.append_child("channel")
            chan_node.append_child_value("label", str(label))
            chan_node.append_child_value("unit", "microvolts")
            chan_node.append_child_value("type", "EEG")

        self.outlet = StreamOutlet(info)
        logger.info("LSL Stream initialized: %s", stream_name)

    def run(self) -> None:
        """Main loop for streaming data."""
        total_samples: int = 0
        try:
            if not self.board_shim or not self.outlet:
                self.setup_board()
                self.setup_lsl()

            self.board_shim.start_stream()
            stream_name = self.config.get("Board", {}).get("StreamName", "BrainFlowEEG")
            logger.info("* LSL stream '%s' is now active.", stream_name)
            logger.info("* Streaming data... (Press Ctrl+C to stop)")

            while True:
                # get_board_data() retrieves all samples since last call
                data = self.board_shim.get_board_data()
                
                if data.any():
                    # EEG channels are specific indices depending on the board
                    eeg_channels = BoardShim.get_eeg_channels(self.board_shim.get_board_id())
                    eeg_data = data[eeg_channels]
                    num_samples = eeg_data.shape[1]
                    
                    # push_chunk is much more efficient than push_sample in a loop
                    # Transpose from (channels, samples) to (samples, channels)
                    self.outlet.push_chunk(eeg_data.T.tolist())
                    total_samples += num_samples
                    
                time.sleep(0.01) # 100Hz polling is enough for chunks
                
        except KeyboardInterrupt:
            logger.info("Stopping LSL server...")
        except Exception as e:
            logger.error("Unexpected error in LSL server: %s", e)
        finally:
            logger.info("  [Log] Sent %d samples total", total_samples)
            if self.board_shim and self.board_shim.is_prepared():
                logger.info("Releasing BrainFlow session...")
                self.board_shim.stop_stream()
                self.board_shim.release_session()
                logger.info("✅ Port released.")
