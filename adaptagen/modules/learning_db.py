"""
Learning Database Module - Manages learning from past improvements and code edits.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)

class LearningDatabase:
    """
    Database for learning from past improvements and code edits.
    Tracks successful and failed edits, analyzes patterns, and adapts prompts.
    """
    
    def __init__(self, db_file: Path = Path(".adaptagen_learning.json")):
        """
        Initialize the learning database.
        
        Args:
            db_file: Path to the database file
        """
        self.db_file = db_file
        self.data = self._load_data()
        
        # Initialize data structure if empty
        if not self.data:
            self.data = {
                "components": {},
                "approaches": {
                    "incremental_edit": {"success": 0, "failure": 0},
                    "full_regeneration": {"success": 0, "failure": 0},
                    "automatic_fix": {"success": 0, "failure": 0}
                },
                "patterns": {
                    "success": [],
                    "failure": []
                },
                "last_updated": time.time()
            }
            self._save_data()
            
    def _load_data(self) -> Dict:
        """Load data from the database file."""
        try:
            if self.db_file.exists():
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.warning(f"Failed to load learning database: {e}")
            return {}
            
    def _save_data(self) -> None:
        """Save data to the database file."""
        try:
            with open(self.db_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save learning database: {e}")
            
    def record_edit_attempt(self, component_name: str, success: bool, 
                           error: str = None, approach: str = "standard") -> None:
        """
        Record an edit attempt in the database.
        
        Args:
            component_name: Name of the component being edited
            success: Whether the edit was successful
            error: Error message if the edit failed
            approach: Approach used for the edit
        """
        # Update component data
        if component_name not in self.data["components"]:
            self.data["components"][component_name] = {
                "attempts": 0,
                "success": 0,
                "failure": 0,
                "last_success": None,
                "last_failure": None,
                "errors": [],
                "complexity": {},
                "approaches": {}
            }
            
        component_data = self.data["components"][component_name]
        component_data["attempts"] += 1
        
        if success:
            component_data["success"] += 1
            component_data["last_success"] = time.time()
        else:
            component_data["failure"] += 1
            component_data["last_failure"] = time.time()
            if error:
                component_data["errors"].append(error)
                
        # Update approach data for the component
        if approach not in component_data["approaches"]:
            component_data["approaches"][approach] = {"success": 0, "failure": 0}
            
        if success:
            component_data["approaches"][approach]["success"] += 1
        else:
            component_data["approaches"][approach]["failure"] += 1
            
        # Update global approach data
        if approach not in self.data["approaches"]:
            self.data["approaches"][approach] = {"success": 0, "failure": 0}
            
        if success:
            self.data["approaches"][approach]["success"] += 1
        else:
            self.data["approaches"][approach]["failure"] += 1
            
        # Update last updated timestamp
        self.data["last_updated"] = time.time()
        
        # Save the data
        self._save_data()
        
    def get_best_approach_for_component(self, component_name: str) -> str:
        """
        Get the best approach for a specific component based on past success.
        
        Args:
            component_name: Name of the component
            
        Returns:
            The name of the best approach
        """
        if component_name not in self.data["components"]:
            # If no data for this component, use the best overall approach
            return self.get_best_approach_overall()
            
        component_data = self.data["components"][component_name]
        
        if not component_data["approaches"]:
            return self.get_best_approach_overall()
            
        # Calculate success rates for each approach
        best_approach = None
        best_rate = -1
        
        for approach, stats in component_data["approaches"].items():
            total = stats["success"] + stats["failure"]
            if total == 0:
                continue
                
            success_rate = stats["success"] / total
            
            if success_rate > best_rate:
                best_rate = success_rate
                best_approach = approach
                
        return best_approach if best_approach else "incremental_edit"
        
    def get_best_approach_overall(self) -> str:
        """
        Get the best approach overall based on past success.
        
        Returns:
            The name of the best approach
        """
        best_approach = None
        best_rate = -1
        
        for approach, stats in self.data["approaches"].items():
            total = stats["success"] + stats["failure"]
            if total < 5:  # Require at least 5 attempts for statistical significance
                continue
                
            success_rate = stats["success"] / total
            
            if success_rate > best_rate:
                best_rate = success_rate
                best_approach = approach
                
        return best_approach if best_approach else "incremental_edit"
        
    def prioritize_components(self, components: Dict[str, str]) -> List[Tuple[str, str]]:
        """
        Prioritize components based on learning data.
        
        Args:
            components: Dictionary mapping component names to code
            
        Returns:
            List of (component_name, code) tuples sorted by priority
        """
        # Calculate priority scores for each component
        component_scores = []
        
        for component_name, code in components.items():
            # Default score for components not in the database
            score = 0.5
            
            if component_name in self.data["components"]:
                component_data = self.data["components"][component_name]
                
                # Calculate success rate
                total_attempts = component_data["success"] + component_data["failure"]
                if total_attempts > 0:
                    success_rate = component_data["success"] / total_attempts
                else:
                    success_rate = 0.5
                    
                # Calculate complexity score
                complexity = self._calculate_complexity(code)
                complexity_score = (
                    0.3 * complexity["cyclomatic"] +
                    0.3 * complexity["nesting"] +
                    0.4 * complexity["length"]
                )
                
                # Calculate recency score (higher for components not recently edited)
                last_edit = component_data.get("last_success", 0)
                if last_edit == 0:
                    recency_score = 1.0  # Never successfully edited
                else:
                    time_since_edit = time.time() - last_edit
                    recency_score = min(1.0, time_since_edit / (7 * 24 * 60 * 60))  # Max score after 1 week
                    
                # Calculate final score
                # Prioritize:
                # 1. Components with low success rate (need more work)
                # 2. Components with high complexity (more room for improvement)
                # 3. Components not edited recently
                score = (
                    0.4 * (1 - success_rate) +  # Lower success rate -> higher priority
                    0.3 * complexity_score +    # Higher complexity -> higher priority
                    0.3 * recency_score         # Not recently edited -> higher priority
                )
                
            component_scores.append((component_name, code, score))
            
        # Sort by score (highest first)
        component_scores.sort(key=lambda x: x[2], reverse=True)
        
        # Return sorted components without scores
        return [(name, code) for name, code, _ in component_scores]
        
    def enhance_prompt_for_component(self, component_name: str, base_prompt: str) -> str:
        """
        Enhance a prompt based on learning data for a specific component.
        
        Args:
            component_name: Name of the component
            base_prompt: Base prompt to enhance
            
        Returns:
            Enhanced prompt
        """
        if component_name not in self.data["components"]:
            return base_prompt
            
        component_data = self.data["components"][component_name]
        
        # Add information about past errors
        if component_data["errors"]:
            # Get the most common errors (up to 3)
            error_counts = {}
            for error in component_data["errors"]:
                error_counts[error] = error_counts.get(error, 0) + 1
                
            common_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            
            error_section = "\nPlease avoid these issues that occurred in previous attempts:\n"
            for error, count in common_errors:
                error_section += f"- {error}\n"
                
            base_prompt += error_section
            
        # Add information about successful patterns
        if "patterns" in self.data and self.data["patterns"]["success"]:
            pattern_section = "\nThese patterns have been successful in previous improvements:\n"
            
            for pattern in self.data["patterns"]["success"][:3]:
                pattern_section += f"- {pattern}\n"
                
            base_prompt += pattern_section
            
        # Add complexity guidance
        complexity_guidance = "\nFocus on these aspects based on component complexity:\n"
        
        if component_data.get("complexity", {}).get("cyclomatic", 0) > 10:
            complexity_guidance += "- Reduce cyclomatic complexity by breaking down complex conditionals\n"
            
        if component_data.get("complexity", {}).get("nesting", 0) > 3:
            complexity_guidance += "- Reduce nesting depth by extracting helper functions\n"
            
        if component_data.get("complexity", {}).get("length", 0) > 100:
            complexity_guidance += "- Improve readability of long functions by adding clear comments\n"
            
        if complexity_guidance != "\nFocus on these aspects based on component complexity:\n":
            base_prompt += complexity_guidance
            
        return base_prompt
        
    def _calculate_complexity(self, code: str) -> Dict[str, float]:
        """
        Calculate complexity metrics for a code component.
        
        Args:
            code: The code to analyze
            
        Returns:
            Dictionary with complexity metrics
        """
        lines = code.split('\n')
        
        # Calculate cyclomatic complexity (approximation based on branches)
        branches = len(re.findall(r'\b(if|elif|else|for|while|try|except|finally)\b', code))
        cyclomatic = 1 + branches
        
        # Calculate maximum nesting depth
        current_depth = 0
        max_depth = 0
        
        for line in lines:
            # Increase depth for lines that start a new block
            if re.search(r':\s*$', line) and not re.search(r'^(?:\s*#|\s*"""|\s*$)', line):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
                
            # Decrease depth for dedents
            elif re.match(r'^\s*(?:return|break|continue|pass)\b', line):
                current_depth = max(0, current_depth - 1)
                
        # Normalize metrics
        normalized_cyclomatic = min(1.0, cyclomatic / 20)  # 20+ is very complex
        normalized_nesting = min(1.0, max_depth / 5)       # 5+ levels is very nested
        normalized_length = min(1.0, len(lines) / 200)     # 200+ lines is very long
        
        return {
            "cyclomatic": normalized_cyclomatic,
            "nesting": normalized_nesting,
            "length": normalized_length
        }
        
    def _extract_patterns(self, code_before: str, code_after: str, success: bool) -> None:
        """
        Extract improvement patterns from code changes.
        
        Args:
            code_before: Code before changes
            code_after: Code after changes
            success: Whether the changes were successful
        """
        # Skip if either code is empty
        if not code_before or not code_after:
            return
            
        # Look for common improvement patterns
        patterns = []
        
        # Check for added docstrings
        if '"""' in code_after and '"""' not in code_before:
            patterns.append("Added docstrings")
            
        # Check for added type hints
        if "->" in code_after and "->" not in code_before:
            patterns.append("Added type hints")
            
        # Check for added error handling
        if "try:" in code_after and "try:" not in code_before:
            patterns.append("Added error handling")
            
        # Check for added logging
        if "logger." in code_after and "logger." not in code_before:
            patterns.append("Added logging")
            
        # Check for function extraction (more functions after)
        funcs_before = len(re.findall(r'\bdef\s+\w+\s*\(', code_before))
        funcs_after = len(re.findall(r'\bdef\s+\w+\s*\(', code_after))
        if funcs_after > funcs_before:
            patterns.append("Extracted helper functions")
            
        # Store the patterns
        if success:
            self.data["patterns"]["success"].extend(patterns)
        else:
            self.data["patterns"]["failure"].extend(patterns)
            
        # Save the data
        self._save_data()
        
    def generate_improvement_report(self) -> str:
        """
        Generate a report on improvements and learning.
        
        Returns:
            Report text
        """
        report = "AdaptaGen Learning Database Report\n"
        report += "===============================\n\n"
        
        # Overall statistics
        total_components = len(self.data["components"])
        total_attempts = sum(comp["attempts"] for comp in self.data["components"].values())
        total_success = sum(comp["success"] for comp in self.data["components"].values())
        
        report += f"Total components tracked: {total_components}\n"
        report += f"Total improvement attempts: {total_attempts}\n"
        report += f"Success rate: {total_success/total_attempts*100:.1f}% ({total_success}/{total_attempts})\n\n"
        
        # Approach effectiveness
        report += "Approach Effectiveness:\n"
        for approach, stats in self.data["approaches"].items():
            total = stats["success"] + stats["failure"]
            if total > 0:
                success_rate = stats["success"] / total * 100
                report += f"- {approach}: {success_rate:.1f}% success ({stats['success']}/{total})\n"
                
        # Most improved components
        report += "\nMost Improved Components:\n"
        improved_components = sorted(
            self.data["components"].items(),
            key=lambda x: x[1]["success"],
            reverse=True
        )[:5]
        
        for name, data in improved_components:
            report += f"- {name}: {data['success']} successful improvements\n"
            
        # Successful patterns
        report += "\nSuccessful Improvement Patterns:\n"
        pattern_counts = {}
        for pattern in self.data["patterns"]["success"]:
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            
        top_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for pattern, count in top_patterns:
            report += f"- {pattern}: {count} occurrences\n"
            
        return report
        
    def _get_component_data(self, component_name: str) -> Dict:
        """
        Get data for a specific component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            Component data or empty dict if not found
        """
        return self.data["components"].get(component_name, {}) 