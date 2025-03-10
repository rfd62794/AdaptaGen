#!/usr/bin/env python3
"""
Version Loader Module - Handles loading different versions of the AdaptaGen agent.
"""

import importlib.util
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
logger = logging.getLogger(__name__)

class VersionLoader:
    """
    Handles loading different versions of the AdaptaGen agent.
    Provides fallback mechanisms to load the latest working version.
    """
    
    def __init__(self, versions_dir: Path = None, status_file: Path = None):
        """
        Initialize the version loader.
        
        Args:
            versions_dir: Directory containing version files (default: current directory)
            status_file: File to store version status (default: .adaptagen_versions/version_status.json)
        """
        self.versions_dir = versions_dir or Path('.')
        self.status_file = status_file or Path('.adaptagen_versions/version_status.json')
        self.version_status = self._load_version_status()
        
    def _load_version_status(self) -> Dict[str, str]:
        """
        Load version status from file.
        
        Returns:
            Dictionary mapping version names to status ("working", "failed", or "unknown")
        """
        try:
            if self.status_file.exists():
                import json
                with open(self.status_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.warning(f"Failed to load version status: {e}")
            return {}
            
    def _save_version_status(self) -> None:
        """Save version status to file."""
        try:
            # Create directory if it doesn't exist
            self.status_file.parent.mkdir(exist_ok=True)
            
            import json
            with open(self.status_file, 'w') as f:
                json.dump(self.version_status, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save version status: {e}")
            
    def _find_version_files(self) -> List[Tuple[str, Path]]:
        """
        Find all version files in the versions directory.
        
        Returns:
            List of tuples (version, path) sorted by version (newest first)
        """
        version_files = []
        
        # Pattern to match version files and extract version number
        pattern = re.compile(r'adaptagen_(\d+)_(\d+)_(\d+)(?:_r(\d+))?\.py')
        
        for file in self.versions_dir.glob('adaptagen_*.py'):
            match = pattern.match(file.name)
            if match:
                # Extract version components
                major = int(match.group(1))
                minor = int(match.group(2))
                patch = int(match.group(3))
                revision = int(match.group(4)) if match.group(4) else 0
                
                # Create version tuple for sorting
                version_tuple = (major, minor, patch, revision)
                version_str = f"{major}.{minor}.{patch}" + (f"-r{revision}" if revision else "")
                
                version_files.append((version_str, version_tuple, file))
        
        # Sort by version (newest first)
        version_files.sort(key=lambda x: x[1], reverse=True)
        
        # Return version string and path
        return [(v[0], v[2]) for v in version_files]
        
    def _load_module_from_file(self, file_path: Path) -> Optional[Any]:
        """
        Load a Python module from a file.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            Loaded module or None if loading failed
        """
        try:
            # Generate a unique module name
            module_name = f"adaptagen_version_{file_path.stem}"
            
            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                logger.error(f"Failed to create spec for {file_path}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Verify that the module has the required classes
            if not hasattr(module, 'AdaptaGen') or not hasattr(module, 'Config'):
                logger.error(f"Module {file_path} does not have required classes")
                return None
                
            return module
        except Exception as e:
            logger.error(f"Failed to load module {file_path}: {e}")
            return None
            
    def load_specific_version(self, version: str) -> Tuple[Optional[Any], str]:
        """
        Load a specific version of the AdaptaGen agent.
        
        Args:
            version: Version string (e.g., "0.0.2-r1")
            
        Returns:
            Tuple of (module, version) or (None, version) if loading failed
        """
        # Convert version string to file name
        version_parts = version.split('.')
        if len(version_parts) != 3:
            logger.error(f"Invalid version format: {version}")
            return None, version
            
        major = version_parts[0]
        minor = version_parts[1]
        
        # Handle revision if present
        if '-r' in version_parts[2]:
            patch_parts = version_parts[2].split('-r')
            patch = patch_parts[0]
            revision = patch_parts[1]
            file_name = f"adaptagen_{major}_{minor}_{patch}_r{revision}.py"
        else:
            patch = version_parts[2]
            file_name = f"adaptagen_{major}_{minor}_{patch}.py"
            
        file_path = self.versions_dir / file_name
        
        # Check if file exists
        if not file_path.exists():
            logger.error(f"Version file not found: {file_path}")
            return None, version
            
        # Load the module
        module = self._load_module_from_file(file_path)
        
        # Update version status
        if module:
            self.version_status[version] = "working"
        else:
            self.version_status[version] = "failed"
            
        self._save_version_status()
        
        return module, version
        
    def load_latest_working_version(self) -> Tuple[Optional[Any], str]:
        """
        Load the latest working version of the AdaptaGen agent.
        Falls back to earlier versions if the latest doesn't work.
        
        Returns:
            Tuple of (module, version) or (None, "") if no working version found
        """
        # Find all version files
        version_files = self._find_version_files()
        
        if not version_files:
            logger.error("No version files found")
            return None, ""
            
        # Try loading versions in order (newest first)
        for version, file_path in version_files:
            # Check if we already know this version doesn't work
            if self.version_status.get(version) == "failed":
                logger.info(f"Skipping known failed version: {version}")
                continue
                
            logger.info(f"Attempting to load version: {version}")
            
            # Load the module
            module = self._load_module_from_file(file_path)
            
            # Update version status
            if module:
                logger.info(f"Successfully loaded version: {version}")
                self.version_status[version] = "working"
                self._save_version_status()
                return module, version
            else:
                logger.warning(f"Failed to load version: {version}")
                self.version_status[version] = "failed"
                self._save_version_status()
                
        logger.error("No working version found")
        return None, ""
        
    def list_all_versions(self) -> List[Tuple[str, str]]:
        """
        List all available versions with their status.
        
        Returns:
            List of tuples (version, status) sorted by version (newest first)
        """
        # Find all version files
        version_files = self._find_version_files()
        
        # Create list of versions with status
        versions = []
        for version, _ in version_files:
            status = self.version_status.get(version, "unknown")
            versions.append((version, status))
            
        return versions
        
    def load_next_version_to_fix(self) -> Tuple[Optional[Any], str, str]:
        """
        Load the next version that needs fixing, along with the latest working version.
        This allows the working version to attempt to fix the next version.
        
        Returns:
            Tuple of (working_module, working_version, next_version_to_fix)
            If no working version is found, returns (None, "", "")
            If no next version to fix is found, returns (working_module, working_version, "")
        """
        # Find all version files
        version_files = self._find_version_files()
        
        if not version_files:
            logger.error("No version files found")
            return None, "", ""
            
        # Find the latest working version
        working_module = None
        working_version = ""
        
        for version, file_path in version_files:
            if self.version_status.get(version) == "working":
                logger.info(f"Found working version: {version}")
                working_module = self._load_module_from_file(file_path)
                working_version = version
                break
                
        if not working_module:
            # Try to load versions in order to find a working one
            for version, file_path in version_files:
                if self.version_status.get(version) == "failed":
                    continue
                    
                logger.info(f"Attempting to load version: {version}")
                module = self._load_module_from_file(file_path)
                
                if module:
                    logger.info(f"Successfully loaded version: {version}")
                    self.version_status[version] = "working"
                    self._save_version_status()
                    working_module = module
                    working_version = version
                    break
                else:
                    logger.warning(f"Failed to load version: {version}")
                    self.version_status[version] = "failed"
                    self._save_version_status()
        
        if not working_module:
            logger.error("No working version found")
            return None, "", ""
            
        # Find the next version to fix
        next_version_to_fix = ""
        
        # Get version tuples for comparison
        version_tuples = []
        for version, _ in version_files:
            parts = version.split('.')
            if '-r' in parts[2]:
                patch_parts = parts[2].split('-r')
                version_tuple = (int(parts[0]), int(parts[1]), int(patch_parts[0]), int(patch_parts[1]))
            else:
                version_tuple = (int(parts[0]), int(parts[1]), int(parts[2]), 0)
            version_tuples.append((version, version_tuple))
            
        # Sort by version
        version_tuples.sort(key=lambda x: x[1])
        
        # Find the working version in the sorted list
        working_index = -1
        for i, (version, _) in enumerate(version_tuples):
            if version == working_version:
                working_index = i
                break
                
        # Find the next version to fix
        if working_index >= 0 and working_index < len(version_tuples) - 1:
            next_version_to_fix = version_tuples[working_index + 1][0]
            logger.info(f"Next version to fix: {next_version_to_fix}")
        else:
            logger.info("No next version to fix found")
            
        return working_module, working_version, next_version_to_fix
        
    def create_new_version(self, base_version: str, increment_type: str = 'revision') -> Tuple[str, Path]:
        """
        Create a new version file based on an existing version.
        
        Args:
            base_version: Version to base the new version on
            increment_type: Type of version increment ('major', 'minor', 'patch', or 'revision')
            
        Returns:
            Tuple of (new_version, new_file_path)
        """
        # Find the base version file
        version_files = self._find_version_files()
        base_file_path = None
        
        for version, file_path in version_files:
            if version == base_version:
                base_file_path = file_path
                break
                
        if not base_file_path:
            logger.error(f"Base version not found: {base_version}")
            return "", Path()
            
        # Parse the base version
        version_parts = base_version.split('.')
        if len(version_parts) != 3:
            logger.error(f"Invalid version format: {base_version}")
            return "", Path()
            
        major = int(version_parts[0])
        minor = int(version_parts[1])
        
        # Handle revision if present
        if '-r' in version_parts[2]:
            patch_parts = version_parts[2].split('-r')
            patch = int(patch_parts[0])
            revision = int(patch_parts[1])
        else:
            patch = int(version_parts[2])
            revision = 0
            
        # Increment version
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
        else:  # revision
            revision += 1
            
        # Create new version string
        new_version = f"{major}.{minor}.{patch}" + (f"-r{revision}" if revision else "")
        
        # Create new file path
        new_file_name = f"adaptagen_{major}_{minor}_{patch}" + (f"_r{revision}" if revision else "") + ".py"
        new_file_path = self.versions_dir / new_file_name
        
        # Copy the base file to the new file
        try:
            import shutil
            shutil.copy2(base_file_path, new_file_path)
            
            # Update the version in the new file
            with open(new_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Replace version string
            version_pattern = r'VERSION\s*=\s*["\']([^"\']+)["\']'
            content = re.sub(version_pattern, f'VERSION = "{new_version}"', content)
            
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            logger.info(f"Created new version: {new_version} at {new_file_path}")
            return new_version, new_file_path
        except Exception as e:
            logger.error(f"Failed to create new version: {e}")
            return "", Path() 