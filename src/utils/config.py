import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

def load_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Loads a YAML file and returns its content as a dictionary.

    Args:
        file_path: Path to the YAML file.

    Returns:
        Dictionary containing the YAML content.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    if not file_path.exists():
        logger.error("Configuration file not found: %s", file_path)
        raise FileNotFoundError(f"Config file {file_path} not found.")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config or {}
    except yaml.YAMLError as e:
        logger.error("Error parsing YAML file %s: %s", file_path, e)
        raise

class EEGConfig:
    """Unified configuration handler for EEGsuite."""
    
    def __init__(
        self, 
        hardware_path: Optional[Path] = None, 
        protocol_path: Optional[Path] = None
    ) -> None:
        self.hardware: Dict[str, Any] = {}
        self.protocol: Dict[str, Any] = {}
        
        if hardware_path:
            self.hardware = load_yaml(hardware_path)
        if protocol_path:
            self.protocol = load_yaml(protocol_path)

    @property
    def board_id(self) -> Optional[str]:
        return self.hardware.get("Board", {}).get("Id")

    @property
    def stream_name(self) -> str:
        return self.hardware.get("Board", {}).get("StreamName", "SynAmpsRT")

    @property
    def serial_port(self) -> Optional[str]:
        return self.hardware.get("VHP", {}).get("Serial")
