# eeg_viewer_main_yaml.py
"""
Main entry point for EEG Viewer Application using YAML configuration.
"""
import argparse
import logging
import yaml
import sys
import os
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

from modules.ui import GraphUI
from modules.plot_manager import PlotManager
from modules.filters import GraphFilters
from modules.lsl_board import LSLBoard

class YamlGraphController:
    def __init__(self, board_shim, yaml_path):
        self.app = QApplication(sys.argv)
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        self.yaml_path = yaml_path
        
        # Load YAML config
        with open(yaml_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.setup_channels()
        
        try:
            if hasattr(self.board_shim, 'get_sampling_rate'):
                self.sampling_rate = self.board_shim.get_sampling_rate(self.board_id)
            else:
                self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        except Exception:
            logging.warning("Could not get sampling rate from board, defaulting to 512Hz")
            self.sampling_rate = 512

        self.filters = GraphFilters(self.sampling_rate, self.exg_channels)
        self.ui = GraphUI(self.filters)
        self.main_widget = QWidget()

        self.plot_manager = PlotManager(
            self.ui, self.board_shim, self.filters,
            self.exg_channels, -1, # virtual_index not used with custom fetchers
            self.sampling_rate, self.main_widget,
            channel_names=self.channel_names,
            data_fetchers=self.data_fetchers
        )

        self.main_widget.setWindowTitle(f"EEG Viewer - {self.config.get('name', 'YAML Config')}")
        self.main_widget.show()

    def setup_channels(self):
        # Map physical channel names to hardware indices (1-based from YAML list)
        all_channels = self.config.get('channels', [])
        name_to_hw_idx = {}
        
        # BrainFlow EXG channels for this board
        if self.board_id in [BoardIds.STREAMING_BOARD, BoardIds.PLAYBACK_FILE_BOARD, -2]:
            # LSL or playback boards don't have static EXG channel lists
            if hasattr(self.board_shim, 'num_channels'):
                bf_exg_channels = list(range(1, self.board_shim.num_channels + 1))
            else:
                bf_exg_channels = list(range(1, len(all_channels) + 1))
        else:
            try:
                bf_exg_channels = BoardShim.get_exg_channels(self.board_id)
            except Exception:
                # Fallback for other unsupported boards
                logging.warning(f"Could not get EXG channels for board {self.board_id}, using fallback mapping")
                bf_exg_channels = list(range(1, len(all_channels) + 1))
        
        for i, name in enumerate(all_channels):
            if name and name != 'NC':
                # Map name to BrainFlow index
                # Assuming 1-based index in 'channels' list matches BF EXG index order
                if i < len(bf_exg_channels):
                    name_to_hw_idx[name] = bf_exg_channels[i]
        
        pick_channels = self.config.get('pick_channels', [])
        virtual_defs = self.config.get('virtual_channels', {})
        
        self.exg_channels = []
        self.channel_names = []
        self.data_fetchers = []
        
        for name in pick_channels:
            if name in name_to_hw_idx:
                # Physical channel
                hw_idx = name_to_hw_idx[name]
                self.exg_channels.append(hw_idx)
                self.channel_names.append(name)
                self.data_fetchers.append(None) # Use default fetching (data[hw_idx])
            elif name in virtual_defs:
                # Virtual channel
                vdef = virtual_defs[name]
                self.exg_channels.append(-1) # Placeholder
                self.channel_names.append(name)
                
                # Create fetcher closure
                self.data_fetchers.append(self.create_virtual_fetcher(vdef, name_to_hw_idx))
            else:
                logging.warning(f"Channel {name} in pick_channels not found in channels or virtual_channels.")

    def create_virtual_fetcher(self, vdef, name_to_hw_idx):
        base_name = vdef['base']
        weights = vdef.get('weights', {})
        divisor = vdef.get('divisor', 1.0)
        
        base_idx = name_to_hw_idx.get(base_name)
        if base_idx is None:
            return lambda data: np.zeros(data.shape[1])
            
        weight_indices = {}
        for w_name, w_val in weights.items():
            w_idx = name_to_hw_idx.get(w_name)
            if w_idx is not None:
                weight_indices[w_idx] = w_val
                
        def fetcher(data):
            # Virtual Signal = base - (sum(weight * weighted_channel) / divisor)
            sig = data[base_idx].copy().astype(float)
            weighted_sum = np.zeros_like(sig)
            for w_idx, w_val in weight_indices.items():
                weighted_sum += data[w_idx] * w_val
            
            sig -= (weighted_sum / divisor)
            return sig
            
        return fetcher

    def run(self):
        self.app.exec_()


def main():
    BoardShim.enable_dev_board_logger()
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('--lsl-stream', type=str, help='LSL stream name or ID to read from')
    parser.add_argument('--serial-port', type=str, help='Serial port for real board')
    parser.add_argument('--board-id', type=int, default=17, help='BrainFlow board ID')
    parser.add_argument('--streamer-params', type=str, default='', help='Optional streamer parameters')
    parser.add_argument('--playback-file', type=str, default=None, help='Path to CSV file for playback mode')
    parser.add_argument('--config', type=str, default='src/modules/freg9.yaml', help='Path to YAML montage file')
    args = parser.parse_args()

    params = BrainFlowInputParams()
    if args.playback_file:
        logging.info("Playback mode activated with file: %s", args.playback_file)
        params.file = args.playback_file
        params.master_board = args.board_id
        board_id = BoardIds.PLAYBACK_FILE_BOARD.value
        board_shim = BoardShim(board_id, params)
    elif args.serial_port:
        logging.info("Serial mode activated on port: %s", args.serial_port)
        params.serial_port = args.serial_port
        board_id = args.board_id
        board_shim = BoardShim(board_id, params)
    elif args.lsl_stream:
        logging.info("LSL mode activated for stream: %s", args.lsl_stream)
        board_shim = LSLBoard(args.lsl_stream, args.board_id)
    else:
        # Default mode if nothing specified: LSL "BrainFlowEEG"
        logging.info("No specific mode requested, defaulting to LSL stream: BrainFlowEEG")
        board_shim = LSLBoard('BrainFlowEEG', args.board_id)

    try:
        board_shim.prepare_session()
        board_shim.start_stream(450000, args.streamer_params)
        
        yaml_path = args.config
        if not os.path.isabs(yaml_path):
            # Check relative to workspace root if needed
            pass
            
        controller = YamlGraphController(board_shim, yaml_path)
        controller.run()
    except Exception:
        logging.warning('Exception occurred during session', exc_info=True)
    finally:
        if board_shim.is_prepared():
            board_shim.release_session()


if __name__ == '__main__':
    main()
