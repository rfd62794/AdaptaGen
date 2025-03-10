"""
AdaptaGen Core Module - Main orchestrator for the self-modifying AI agent.
"""

import inspect
import logging
import shutil
from pathlib import Path
from typing import Optional

# Import modules
from adaptagen.core.config import Config
from adaptagen.modules.token_system import TokenRegistry
from adaptagen.modules.code_manager import CodeManager
from adaptagen.modules.version_control import VersionControl, VersionManager
from adaptagen.modules.api_client import GeminiAPI
from adaptagen.modules.goal_system import GoalManager
from adaptagen.modules.learning_db import LearningDatabase
from adaptagen.modules.code_validator import CodeValidator
from adaptagen.modules.incremental_editor import IncrementalEditor

# Configure logging
logger = logging.getLogger(__name__)

# Version
VERSION = "0.0.2-r2"

class AdaptaGen:
    """Orchestrates the self-modification process."""
    
    def __init__(self, config: Config):
        """Initialize the AdaptaGen system."""
        self.config = config
        self.gemini_api = GeminiAPI(config)
        self.code_manager = CodeManager()
        self.version_control = VersionControl()
        self.version_manager = VersionManager()
        self.goal_manager = GoalManager()
        self.learning_db = LearningDatabase()
        
        # Register with token registry
        TokenRegistry.register("ADAPTAGEN", self.__class__.__name__)
    
    def run(self, increment_type: str = 'revision', use_incremental: bool = False, 
            goal_name: str = None, max_components: int = 10, patient_mode: bool = False) -> None:
        """
        Execute the self-modification process.
        
        Args:
            increment_type: Type of version increment ('major', 'minor', 'patch', or 'revision')
            use_incremental: Whether to use incremental editing instead of full regeneration
            goal_name: Name of the goal to use (if None, use current goal)
            max_components: Maximum number of components to process in a single run
            patient_mode: Whether to use extended backoff times for more patient operation
        """
        # Set the current goal if specified
        if goal_name:
            goal = self.goal_manager.get_goal_by_name(goal_name)
            if not goal:
                logger.warning(f"Goal {goal_name} not found. Using current goal.")
                goal = self.goal_manager.get_current_goal()
        else:
            # Get the current goal or rotate to the next one
            if self.version_control.get_version_history():
                # If we have previous versions, rotate to the next goal
                goal = self.goal_manager.rotate_goal()
            else:
                # For the first run, use the current goal (highest priority)
                goal = self.goal_manager.get_current_goal()
        
        logger.info(f"Starting AdaptaGen {VERSION} with goal: {goal.description}")
        
        # Read the current source code
        current_filepath = Path(inspect.getfile(inspect.currentframe()))
        current_code = self.code_manager.read_code(current_filepath)
        if not current_code:
            logger.error("Failed to read source code.")
            return
        
        # Save current version to version history
        self.version_control.save_version(current_code, VERSION)
        
        # Increment version
        new_version = self.version_manager.increment_version(VERSION, increment_type)
        
        if use_incremental:
            # Use incremental editing approach
            logger.info("Using incremental editing approach")
            
            # Determine the target file path
            target_filepath = current_filepath
            
            # Create a backup of the current file
            backup_filepath = Path(f"{current_filepath}.bak")
            try:
                shutil.copy2(current_filepath, backup_filepath)
                logger.info(f"Created backup at {backup_filepath}")
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")
                return
            
            # Initialize the incremental editor with the target file and learning database
            incremental_editor = IncrementalEditor(
                current_code, 
                self.code_manager, 
                self.version_control,
                self.gemini_api,
                target_filepath,
                self.learning_db
            )
            
            # Configure the incremental editor based on parameters
            if max_components:
                incremental_editor.max_components_per_run = max_components
                logger.info(f"Set maximum components per run to {max_components}")
                
            if patient_mode:
                # Use extended backoff times for more patient operation
                # Up to 1 hour: 1s, 5s, 15s, 30s, 1m, 2m, 5m, 10m, 15m, 30m, 60m
                incremental_editor.backoff_times = [1, 5, 15, 30, 60, 120, 300, 600, 900, 1800, 3600]
                logger.info("Using patient mode with extended backoff times (up to 1 hour)")
            
            try:
                # Run incremental editing
                improved_code = incremental_editor.run_incremental_edit(new_version)
                
                # Only proceed if we have successful edits
                if incremental_editor.successful_edits > 0:
                    # Update version in code
                    improved_code = self.version_manager.update_version_in_code(improved_code, new_version)
                    
                    # Write the final version back to the same file
                    if self.code_manager.write_code(target_filepath, improved_code):
                        logger.info(f"Successfully updated {target_filepath} with version {new_version}")
                        
                        # Save to version history
                        self.version_control.save_version(improved_code, new_version)
                        
                        # Log statistics
                        logger.info(f"Incremental editing statistics: {incremental_editor.successful_edits} successful edits, {incremental_editor.failed_edits} failed edits")
                    else:
                        logger.error(f"Failed to write to {target_filepath}")
                        self._restore_backup(backup_filepath, target_filepath)
                else:
                    logger.warning("No successful edits were made during incremental editing")
                    self._restore_backup(backup_filepath, target_filepath)
            except Exception as e:
                logger.error(f"Error during incremental editing: {e}")
                self._restore_backup(backup_filepath, target_filepath)
            finally:
                # Clean up backup if everything went well
                if backup_filepath.exists() and incremental_editor.successful_edits > 0:
                    try:
                        backup_filepath.unlink()
                        logger.info(f"Removed backup file {backup_filepath}")
                    except Exception as e:
                        logger.warning(f"Failed to remove backup file: {e}")
            
            return
        
        # Traditional approach (full regeneration)
        # Generate a prompt based on the current goal
        prompt = goal.get_prompt(current_code, self.config)
        
        # Get AI-generated improvements
        logger.info("Generating improved version using AI...")
        improved_code = self.gemini_api.generate_response(prompt)
        
        # Error handling for API response
        if not improved_code:
            logger.error("Failed to generate improved code.")
            return
        
        # Maximum number of retry attempts
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Attempt to compile the generated code to catch syntax errors early
                compile(improved_code, '<string>', 'exec')
                
                # Validate the generated code for common issues
                code_validator = CodeValidator()
                is_valid, issues = code_validator.validate_code(improved_code, current_code)
                
                if not is_valid:
                    logger.warning(f"Generated code has issues: {', '.join(issues)}")
                    
                    # If we have retries left, try to regenerate with an enhanced prompt
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Attempting to regenerate code (retry {retry_count}/{max_retries})...")
                        
                        # Generate an enhanced prompt that addresses the specific issues
                        enhanced_prompt = goal.get_enhanced_prompt(current_code, self.config, issues)
                        
                        # Save the problematic code for reference
                        self.version_control.save_version(
                            improved_code, 
                            f"{new_version}-retry{retry_count}_issues"
                        )
                        
                        # Generate new code with the enhanced prompt
                        improved_code = self.gemini_api.generate_response(enhanced_prompt)
                        
                        if not improved_code:
                            logger.error(f"Failed to regenerate code on retry {retry_count}.")
                            break
                            
                        # Continue to the next iteration to validate the new code
                        continue
                    
                    # If we're out of retries, attempt to fix common issues
                    logger.info("Attempting to fix common issues in generated code")
                    improved_code = code_validator.fix_common_issues(improved_code, current_code)
                    
                    # Validate again after fixes
                    is_valid, remaining_issues = code_validator.validate_code(improved_code, current_code)
                    if not is_valid:
                        logger.warning(f"Issues remain after fixes: {', '.join(remaining_issues)}")
                
                # Update version in the code
                improved_code = self.version_manager.update_version_in_code(improved_code, new_version)
                
                # Write the improved code to a new file
                new_filepath = Path(f"adaptagen_{new_version.replace('.', '_').replace('-', '_')}.py")
                if self.code_manager.write_code(new_filepath, improved_code):
                    logger.info(f"Successfully generated improved version: {new_version}")
                    logger.info(f"Saved to: {new_filepath}")
                    
                    # Save to version history
                    self.version_control.save_version(improved_code, new_version)
                else:
                    logger.error(f"Failed to write improved code to {new_filepath}")
                
                # Break out of the retry loop if we got here
                break
                
            except SyntaxError as e:
                logger.error(f"Generated code has syntax errors: {e}")
                
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Attempting to regenerate code (retry {retry_count}/{max_retries})...")
                    
                    # Save the problematic code for reference
                    self.version_control.save_version(
                        improved_code, 
                        f"{new_version}-retry{retry_count}_syntax_error"
                    )
                    
                    # Generate an enhanced prompt that addresses syntax errors
                    enhanced_prompt = goal.get_enhanced_prompt(
                        current_code, 
                        self.config, 
                        [f"Syntax error: {e}"]
                    )
                    
                    # Generate new code with the enhanced prompt
                    improved_code = self.gemini_api.generate_response(enhanced_prompt)
                    
                    if not improved_code:
                        logger.error(f"Failed to regenerate code on retry {retry_count}.")
                        break
                else:
                    logger.error("Maximum retry attempts reached. Giving up.")
                    break
    
    def _restore_backup(self, backup_filepath: Path, target_filepath: Path) -> None:
        """
        Restore a file from backup.
        
        Args:
            backup_filepath: Path to the backup file
            target_filepath: Path to the target file to restore
        """
        try:
            if backup_filepath.exists():
                shutil.copy2(backup_filepath, target_filepath)
                logger.info(f"Restored from backup {backup_filepath}")
                
                # Remove the backup file
                backup_filepath.unlink()
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            
    def fix_version(self, next_version: str, use_incremental: bool = False, 
                   max_components: int = 10, patient_mode: bool = False) -> None:
        """
        Fix a specific version using the current version.
        
        Args:
            next_version: The version to fix
            use_incremental: Whether to use incremental editing
            max_components: Maximum number of components to process
            patient_mode: Whether to use extended backoff times
        """
        # Implementation would be similar to the run method but focused on fixing
        # a specific version rather than creating a new one
        logger.info(f"Fixing version {next_version} using current version {VERSION}")
        
        # The rest of the implementation would be similar to the run method
        # but adapted for fixing a specific version
            
    def list_versions(self) -> None:
        """List all versions in the version history."""
        versions = self.version_control.get_version_history()
        if versions:
            print("Version History:")
            for version in versions:
                print(f"  {version['version']} - {version['timestamp']}")
        else:
            print("No version history found.")
            
    def generate_improvement_report(self) -> str:
        """
        Generate a report on improvements and learning.
        
        Returns:
            Report text
        """
        if self.learning_db:
            return self.learning_db.generate_improvement_report()
        else:
            return "No learning database available." 