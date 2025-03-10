"""
Version Control Module - Manages version history and version increments.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Version control constants
VERSION_HISTORY_DIR = Path(".adaptagen_versions")
VERSION_METADATA_FILE = "version_metadata.json"

class VersionControl:
    """Manages version control for the script."""
    
    def __init__(self, directory: Path = VERSION_HISTORY_DIR, metadata_file: str = VERSION_METADATA_FILE):
        """
        Initialize the version control system.
        
        Args:
            directory: Directory to store version history
            metadata_file: File to store version metadata
        """
        self.directory = directory
        self.metadata_file = metadata_file
        
        # Create directory if it doesn't exist
        self.directory.mkdir(exist_ok=True)
        
    def get_metadata_path(self) -> Path:
        """Get the path to the metadata file."""
        return self.directory / self.metadata_file
        
    def _load_metadata(self) -> Dict:
        """Load version metadata from file."""
        metadata_path = self.get_metadata_path()
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load version metadata: {e}")
                
        return {"versions": []}
        
    def _save_metadata(self, metadata: Dict) -> None:
        """Save version metadata to file."""
        metadata_path = self.get_metadata_path()
        try:
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save version metadata: {e}")
            
    def save_version(self, code: str, version: str) -> None:
        """
        Save a version of the code to the version history.
        
        Args:
            code: The code to save
            version: The version identifier
        """
        # Create a filename based on the version and timestamp
        timestamp = time.strftime("%Y%m%d%H%M%S")
        
        # Convert version string to filename-friendly format
        filename_version = version.replace('.', '_').replace('-', '_')
        filename = f"adaptagen_{filename_version}_{timestamp}.py"
        
        # Save the code to a file
        filepath = self.directory / filename
        try:
            with open(filepath, 'w') as f:
                f.write(code)
                
            logger.info(f"Saved version {version} to {filepath}")
            
            # Update metadata
            metadata = self._load_metadata()
            
            # Add version to metadata if not already present
            version_entry = {
                "version": version,
                "timestamp": timestamp,
                "filepath": str(filepath),
                "hash": self._calculate_hash(code)
            }
            
            # Check if this version already exists
            for i, entry in enumerate(metadata["versions"]):
                if entry["version"] == version:
                    # Update existing entry
                    metadata["versions"][i] = version_entry
                    break
            else:
                # Add new entry
                metadata["versions"].append(version_entry)
                
            # Save metadata
            self._save_metadata(metadata)
            
        except Exception as e:
            logger.error(f"Failed to save version {version}: {e}")
            
    def _calculate_hash(self, code: str) -> str:
        """Calculate a hash of the code."""
        import hashlib
        return hashlib.md5(code.encode('utf-8')).hexdigest()
        
    def get_version_history(self) -> List[Dict]:
        """
        Get the version history.
        
        Returns:
            List of version entries
        """
        metadata = self._load_metadata()
        return metadata["versions"]
        
    def get_latest_version(self) -> Optional[Dict]:
        """
        Get the latest version entry.
        
        Returns:
            Latest version entry or None if no versions exist
        """
        versions = self.get_version_history()
        if versions:
            return versions[-1]
        return None

class VersionManager:
    """Manages version increments and updates."""
    
    def __init__(self):
        """Initialize the version manager."""
        pass
        
    @staticmethod
    def increment_version(version: str, increment_type: str = 'revision') -> str:
        """
        Increment a version string.
        
        Args:
            version: The version string to increment
            increment_type: Type of increment ('major', 'minor', 'patch', or 'revision')
            
        Returns:
            The incremented version string
        """
        # Parse the version string
        if '-r' in version:
            # Version with revision (e.g., "0.0.1-r2")
            base_version, revision = version.split('-r')
            major, minor, patch = map(int, base_version.split('.'))
            revision = int(revision)
        else:
            # Version without revision (e.g., "0.0.1")
            major, minor, patch = map(int, version.split('.'))
            revision = 0
            
        # Increment based on type
        if increment_type == 'major':
            major += 1
            minor = 0
            patch = 0
            revision = 0
        elif increment_type == 'minor':
            minor += 1
            patch = 0
            revision = 0
        elif increment_type == 'patch':
            patch += 1
            revision = 0
        elif increment_type == 'revision':
            revision += 1
        else:
            logger.warning(f"Unknown increment type: {increment_type}, using 'revision'")
            revision += 1
            
        # Format the new version string
        if revision > 0:
            return f"{major}.{minor}.{patch}-r{revision}"
        else:
            return f"{major}.{minor}.{patch}"
            
    @staticmethod
    def update_version_in_code(code: str, new_version: str) -> str:
        """
        Update the VERSION constant in the code.
        
        Args:
            code: The code to update
            new_version: The new version string
            
        Returns:
            The updated code
        """
        # Replace the VERSION constant
        pattern = r'VERSION\s*=\s*["\']([^"\']+)["\']'
        return re.sub(pattern, f'VERSION = "{new_version}"', code) 