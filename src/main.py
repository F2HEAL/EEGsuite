import argparse
import sys
import logging
from pathlib import Path

# Add the project root to sys.path to allow 'from src...' imports
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.utils.logger import setup_logger
from src.utils.paths import initialize_directories, CONFIG_DIR, set_cloud_root
from src.utils.config import EEGConfig

def main():
    """Unified CLI for EEGsuite."""
    parser = argparse.ArgumentParser(description="F2H EEG Suite")
    parser.add_argument(
        "--data-root",
        type=str,
        help="Override the root directory for data, logs, and reports"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start LSL Server")
    server_parser.add_argument("-c", "--config", type=str, required=True, help="Hardware config file")

    # Sweep command
    sweep_parser = subparsers.add_parser("sweep", help="Run Sweep Protocol")
    sweep_parser.add_argument("-p", "--protocol", type=str, required=True, help="Protocol config file")
    sweep_parser.add_argument("-d", "--device", type=str, required=True, help="Hardware config file")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze recorded data")
    analyze_parser.add_argument("-f", "--file", type=str, required=True, help="CSV file to analyze")
    analyze_parser.add_argument("-s", "--start", type=float, default=0.0, help="Start time (sec)")
    analyze_parser.add_argument("-d", "--duration", type=float, default=60.0, help="Duration (sec)")
    analyze_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Initialize paths and directories
    if args.data_root:
        set_cloud_root(Path(args.data_root))

    try:
        initialize_directories()
    except Exception as e:
        print(f"❌ Critical Error: Could not initialize data directories: {e}")
        sys.exit(1)

    logger = setup_logger()

    if args.command == "server":
        from src.streaming.server import LSLServer
        config_path = Path(args.config)
        from src.utils.config import load_yaml
        config = load_yaml(config_path)
        server = LSLServer(config)
        server.run()

    elif args.command == "sweep":
        logger.info("Initializing Sweep command...")
        from src.recording.sweep import EEGSweep
        logger.info("Loading configuration...")
        cfg = EEGConfig(hardware_path=Path(args.device), protocol_path=Path(args.protocol))
        logger.info("Setting up Sweep engine...")
        sweep = EEGSweep(cfg)
        sweep.connect_lsl()
        sweep.connect_vhp()
        sweep.run_sweep()

    elif args.command == "analyze":
        logger.info("Starting native analysis for %s", args.file)
        from src.analysis.offline.visualizer import EEGVisualizer
        from src.utils.paths import REPORT_DIR
        
        # Load default analysis config
        from src.utils.config import load_yaml
        analysis_config_path = CONFIG_DIR / "analysis" / "default_offline.yaml"
        config = load_yaml(analysis_config_path) if analysis_config_path.exists() else {}
        
        viz = EEGVisualizer(config)
        viz.load_data(Path(args.file))
        
        report_path = viz.generate_report(
            csv_file=Path(args.file),
            output_dir=REPORT_DIR,
            start=args.start,
            duration=args.duration
        )
        logger.info("✅ Analysis complete. Report: %s", report_path)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()


