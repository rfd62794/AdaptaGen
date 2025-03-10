"""
Incremental Editor Module - Handles incremental editing of code components.
"""

import re
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logger = logging.getLogger(__name__)

class IncrementalEditor:
    """
    Handles incremental editing of code components.
    """
    def __init__(self, code: str, code_manager, 
                 version_control, gemini_api,
                 target_filepath: Path, learning_db = None):
        """
        Initialize the incremental editor.
        
        Args:
            code: The code to edit
            code_manager: CodeManager instance
            version_control: VersionControl instance
            gemini_api: GeminiAPI instance
            target_filepath: Path to the target file
            learning_db: LearningDatabase instance (optional)
        """
        self.code = code
        self.code_manager = code_manager
        self.version_control = version_control
        self.gemini_api = gemini_api
        self.target_filepath = target_filepath
        self.learning_db = learning_db
        self.successful_edits = 0
        self.failed_edits = 0
        self.rate_limit_hits = 0
        self.max_components_per_run = 10
        
        # Default backoff times in seconds (up to 5 minutes)
        # 1s, 5s, 15s, 30s, 60s, 120s, 300s
        self.backoff_times = [1, 5, 15, 30, 60, 120, 300]
        
        # Track components that have been processed
        self.processed_components = set()
        
    def run_incremental_edit(self, new_version: str) -> str:
        """
        Run the incremental editing process on the code.
        
        Args:
            new_version: The new version identifier
            
        Returns:
            The updated code
        """
        # Extract components from the code
        components = self.code_manager.extract_components(self.code)
        logger.info(f"Extracted {len(components)} components from code")
        
        # Sort components by priority (classes first, then functions)
        try:
            sorted_components = sorted(
                components.items(),
                key=lambda x: (
                    0 if x[0].startswith("class ") else 1,  # Classes first
                    len(x[1])  # Then by size (smaller first)
                )
            )
            
            # Process components
            processed_count = 0
            for component_name, component_code in sorted_components:
                # Skip if we've reached the maximum number of components for this run
                if processed_count >= self.max_components_per_run:
                    logger.info(f"Reached maximum of {self.max_components_per_run} components for this run")
                    break
                    
                # Skip if this component has already been processed
                if component_name in self.processed_components:
                    logger.info(f"Skipping already processed component: {component_name}")
                    continue
                    
                logger.info(f"Processing component: {component_name}")
                
                # Try to improve the component
                improved_component = self._improve_component(component_name, component_code, new_version)
                
                if improved_component and improved_component != component_code:
                    # Replace the component in the code
                    self.code = self.code_manager.replace_component(self.code, component_name, improved_component)
                    self.successful_edits += 1
                    logger.info(f"Successfully improved component: {component_name}")
                    
                    # Record the successful edit in the learning database
                    if self.learning_db:
                        self.learning_db.record_edit_attempt(
                            component_name=component_name,
                            success=True,
                            error=None,
                            approach="incremental_edit"
                        )
                    
                    # Write the updated code to the file after each successful edit
                    if self.code_manager.write_code(self.target_filepath, self.code):
                        logger.info(f"Updated {self.target_filepath} with improved component")
                    else:
                        logger.error(f"Failed to write to {self.target_filepath}")
                else:
                    self.failed_edits += 1
                    logger.warning(f"Failed to improve component: {component_name}")
                    
                    # Record the failed edit in the learning database
                    if self.learning_db:
                        self.learning_db.record_edit_attempt(
                            component_name=component_name,
                            success=False,
                            error="No improvement generated",
                            approach="incremental_edit"
                        )
                
                # Mark this component as processed
                self.processed_components.add(component_name)
                processed_count += 1
        except Exception as e:
            logger.error(f"Error processing components: {str(e)}")
            # Return the original code if there was an error
            return self.code
            
        logger.info(f"Incremental editing complete. Successful edits: {self.successful_edits}, Failed edits: {self.failed_edits}, Rate limit hits: {self.rate_limit_hits}")
        return self.code
        
    def _improve_component(self, component_name: str, component_code: str, new_version: str) -> Optional[str]:
        """
        Attempt to improve a single component.
        
        Args:
            component_name: The name of the component
            component_code: The code of the component
            new_version: The new version identifier
            
        Returns:
            The improved component code, or None if improvement failed
        """
        # Prepare the prompt
        base_prompt = f"""
        You are an expert Python developer tasked with improving the following code component from AdaptaGen version {new_version}.
        
        Component: {component_name}
        
        ```python
        {component_code}
        ```
        
        Please improve this component by:
        1. Enhancing functionality
        2. Fixing any bugs or edge cases
        3. Improving error handling
        4. Adding or improving docstrings and comments
        5. Optimizing performance where possible
        
        Return ONLY the improved code for this component, nothing else.
        """
        
        # Enhance the prompt with learning from past attempts if available
        if self.learning_db:
            enhanced_prompt = self.learning_db.enhance_prompt_for_component(component_name, base_prompt)
        else:
            enhanced_prompt = base_prompt
        
        # Try to get a response with backoff for rate limits
        retry_count = 0
        max_retries = len(self.backoff_times)
        
        while retry_count < max_retries:
            try:
                response = self.gemini_api.generate_text(enhanced_prompt)
                
                if response:
                    # Extract the code from the response
                    code_pattern = r"```(?:python)?\s*(.*?)```"
                    matches = re.findall(code_pattern, response, re.DOTALL)
                    
                    if matches:
                        improved_code = matches[0].strip()
                        return improved_code
                    else:
                        # If no code block found, check if the entire response is valid Python
                        if self._is_valid_python(response):
                            return response.strip()
                        else:
                            logger.warning(f"No valid Python code found in response for {component_name}")
                            return None
                else:
                    logger.warning(f"Empty response from API for {component_name}")
                    return None
                    
            except Exception as e:
                retry_count += 1
                self.rate_limit_hits += 1
                
                if retry_count < max_retries:
                    backoff_time = self.backoff_times[retry_count - 1]
                    logger.warning(f"API error: {str(e)}. Retrying in {backoff_time} seconds... (Attempt {retry_count}/{max_retries})")
                    time.sleep(backoff_time)
                else:
                    logger.error(f"Failed to improve component {component_name} after {max_retries} attempts: {str(e)}")
                    
                    # Record the failed edit in the learning database
                    if self.learning_db:
                        self.learning_db.record_edit_attempt(
                            component_name=component_name,
                            success=False,
                            error=str(e),
                            approach="incremental_edit"
                        )
                    
                    return None
        
        return None
        
    def _is_valid_python(self, code: str) -> bool:
        """
        Check if a string is valid Python code.
        
        Args:
            code: The code to check
            
        Returns:
            True if the code is valid Python, False otherwise
        """
        try:
            compile(code, '<string>', 'exec')
            return True
        except SyntaxError:
            return False 