import argparse
import sys
import logging
from pathlib import Path

# Add the project root to sys.path to allow 'from src...' imports
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.utils.logger import setup_logger
from src.utils.paths import initialize_directories, CONFIG_DIR
from src.utils.config import EEGConfig

def main():
    """Unified CLI for EEGsuite."""
    initialize_directories()
    logger = setup_logger()

    parser = argparse.ArgumentParser(description="F2H EEG Suite")
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
    analyze_parser.add_argument("-s", "--start", type=float, default=7.5, help="Start time (sec)")
    analyze_parser.add_argument("-d", "--duration", type=float, default=2.0, help="Duration (sec)")
    analyze_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

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
        logger.info("Starting analysis for %s", args.file)
        import subprocess
        
        # Path to your existing viz tool
        viz_script = Path("D:/F2H_code/GH/eeg-tools/basic-visualization/src/viz1p_prep_html.py")
        viz_config = Path("D:/F2H_code/GH/eeg-tools/basic-visualization/src/config-currystream.yaml")
        
        if not viz_script.exists():
            logger.error("Visualization script not found at %s", viz_script)
            return

        cmd = [
            sys.executable, str(viz_script),
            "-c", str(viz_config),
            "-f", args.file,
            "--start-time", str(args.start),
            "--duration", str(args.duration)
        ]
        if args.verbose:
            cmd.append("-v")
            
        logger.info("Running: %s", " ".join(cmd))
        subprocess.run(cmd)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()


