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

    # Analyze_contrast command
    analyze_contrast_parser = subparsers.add_parser("analyze_contrast", help="Analyze data by contrast")
    analyze_contrast_parser.add_argument("--fot", type=Path, required=True,help="CSV file for FOT condition",)
    analyze_contrast_parser.add_argument("--ifnfn", type=Path, required=True,help="CSV file for IFNFN condition",)
    analyze_contrast_parser.add_argument("--config", type=Path, default=None,help="Analysis YAML config (optional)",)
    analyze_contrast_parser.add_argument("--output", type=Path, default=Path("reports"),help="Output directory for report",)

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

        # Check if user manually specified channels in the YAML
        if config.get('pick_channels'):
            config['manual_pick_override'] = True

        viz = EEGVisualizer(config)
        viz.load_data(Path(args.file))

        report_path = viz.generate_report(
            csv_file=Path(args.file),
            output_dir=REPORT_DIR,
            start=args.start,
            duration=args.duration
        )
        logger.info("Analysis complete. Report: %s", report_path)
    elif args.command == "analyze_contrast":
        fot_path = args.fot
        ifnfn_path = args.ifnfn

        logger.info(f"Starting contrast analysis for {fot_path} vs {ifnfn_path}")
        from src.analysis.offline.tfr_contrast import TFRContrastAnalyzer, TFRContrastConfig

        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)

        cfg = TFRContrastConfig(
            # Use wider freq range to see the full picture
            tfr_fmin=5.0,
            tfr_fmax=45.0,
            tfr_fstep=1.0,
            # Speed up for testing
            tfr_decim=2,
            # Protocol-matching windows
            epoch_tmin=-1.5,
            epoch_tmax=5.0,
            baseline_tmin=-1.0,
            baseline_tmax=-0.5,
            stim_window_tmin=0.5,
            stim_window_tmax=4.0,
            baseline_mode="logratio",
            # Output
            output_dir=str(output_dir / "report"),
        )

        analyzer = TFRContrastAnalyzer(cfg)
        analyzer.load_two_files(fot_path, ifnfn_path)

        logger.info("Running 4-step pipeline...")
        success = analyzer.run_pipeline()

        if not success:
            logger.error("❌ Pipeline FAILED")
            sys.exit(1)

        invalid = analyzer.validate()
        if invalid:
            logger.error(f"❌ Validation Failed: {invalid}")
            sys.exit(2)
        else:
            logger.info("✅ Analyzer data validated")

        report_path = analyzer.generate_report(
            output_dir=output_dir / "report",
            filename="mock_contrast_report.html",
        )
        print(f"  ✅ Report: {report_path}")




    else:
        parser.print_help()

if __name__ == "__main__":
    main()
