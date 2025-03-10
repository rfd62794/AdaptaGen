"""
Test script for the LearningDatabase functionality.
"""

import json
import datetime
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

class SimpleLearningDatabase:
    """Simplified version of the LearningDatabase class for testing."""
    
    def __init__(self, db_file: Path = Path(".adaptagen_learning_test.json")):
        """Initialize the learning database."""
        self.db_file = db_file
        self.data = self._load_data()
        
        # Initialize database structure if it doesn't exist
        if "component_history" not in self.data:
            self.data["component_history"] = {}
        if "approach_success_rates" not in self.data:
            self.data["approach_success_rates"] = {}
        if "prompt_patterns" not in self.data:
            self.data["prompt_patterns"] = {"successful": [], "failed": []}
        if "complexity_metrics" not in self.data:
            self.data["complexity_metrics"] = {}
        if "improvement_metrics" not in self.data:
            self.data["improvement_metrics"] = {"overall": []}
        
        # Save initialized structure
        self._save_data()
    
    def _load_data(self) -> Dict:
        """Load data from the database file."""
        if self.db_file.exists():
            try:
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading learning database: {e}")
                return {}
        return {}
    
    def _save_data(self) -> None:
        """Save data to the database file."""
        try:
            with open(self.db_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving learning database: {e}")
    
    def record_edit_attempt(self, component_name: str, approach: str, 
                           success: bool, code_before: str, code_after: str = None,
                           error_message: str = None) -> None:
        """
        Record an edit attempt in the database.
        
        Args:
            component_name: Name of the component that was edited
            approach: The editing approach used
            success: Whether the edit was successful
            code_before: The code before the edit
            code_after: The code after the edit (if successful)
            error_message: Error message (if failed)
        """
        # Initialize component history if it doesn't exist
        if component_name not in self.data["component_history"]:
            self.data["component_history"][component_name] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "last_success": None,
                "last_failure": None,
                "approaches": {}
            }
        
        # Update component history
        component_data = self.data["component_history"][component_name]
        component_data["attempts"] += 1
        
        # Initialize approach data if it doesn't exist
        if approach not in component_data["approaches"]:
            component_data["approaches"][approach] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0
            }
        
        # Update approach data for this component
        approach_data = component_data["approaches"][approach]
        approach_data["attempts"] += 1
        
        # Initialize global approach data if it doesn't exist
        if approach not in self.data["approach_success_rates"]:
            self.data["approach_success_rates"][approach] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0
            }
        
        # Update global approach data
        global_approach_data = self.data["approach_success_rates"][approach]
        global_approach_data["attempts"] += 1
        
        # Record timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Record success or failure
        if success:
            component_data["successes"] += 1
            component_data["last_success"] = timestamp
            approach_data["successes"] += 1
            global_approach_data["successes"] += 1
            
            # Calculate complexity metrics
            complexity_before = self._calculate_complexity(code_before)
            complexity_after = self._calculate_complexity(code_after)
            
            # Record complexity change
            if component_name not in self.data["complexity_metrics"]:
                self.data["complexity_metrics"][component_name] = []
            
            self.data["complexity_metrics"][component_name].append({
                "timestamp": timestamp,
                "before": complexity_before,
                "after": complexity_after,
                "change": {k: complexity_after[k] - complexity_before[k] for k in complexity_before}
            })
            
            # Extract successful patterns from the edit
            self._extract_patterns(code_before, code_after, success=True)
        else:
            component_data["failures"] += 1
            component_data["last_failure"] = timestamp
            approach_data["failures"] += 1
            global_approach_data["failures"] += 1
            
            # Record error message
            if error_message:
                if "error_patterns" not in component_data:
                    component_data["error_patterns"] = []
                
                component_data["error_patterns"].append({
                    "timestamp": timestamp,
                    "approach": approach,
                    "error": error_message
                })
        
        # Save updated data
        self._save_data()
    
    def _calculate_complexity(self, code: str) -> Dict[str, float]:
        """
        Calculate complexity metrics for a piece of code.
        
        Args:
            code: The code to analyze
            
        Returns:
            Dictionary of complexity metrics
        """
        if not code:
            return {"lines": 0, "cyclomatic": 0, "nesting": 0}
        
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # Simple cyclomatic complexity estimation
        decision_points = 0
        for line in non_empty_lines:
            if re.search(r'\bif\b|\bfor\b|\bwhile\b|\belif\b|\bexcept\b|\bwith\b', line):
                decision_points += 1
        
        # Simple nesting level estimation
        max_indent = 0
        for line in non_empty_lines:
            indent = len(line) - len(line.lstrip())
            max_indent = max(max_indent, indent)
        
        # Normalize nesting level (assuming 4 spaces per level)
        nesting_level = max_indent / 4 if max_indent > 0 else 0
        
        return {
            "lines": len(non_empty_lines),
            "cyclomatic": decision_points,
            "nesting": nesting_level
        }
    
    def _extract_patterns(self, code_before: str, code_after: str, success: bool) -> None:
        """
        Extract patterns from successful or failed edits.
        
        Args:
            code_before: Code before the edit
            code_after: Code after the edit
            success: Whether the edit was successful
        """
        if not code_before or not code_after:
            return
        
        # This is a simplified implementation
        # A more sophisticated approach would use AST parsing to identify
        # specific transformation patterns
        
        # For now, just look for simple patterns like added error handling
        if success:
            # Check for added try/except blocks
            if "try:" in code_after and "try:" not in code_before:
                self.data["prompt_patterns"]["successful"].append(
                    "Adding proper error handling with try/except blocks"
                )
            
            # Check for added logging
            if "print" in code_after and "print" not in code_before:
                self.data["prompt_patterns"]["successful"].append(
                    "Adding print statements for better observability"
                )
            
            # Check for added docstrings
            if '"""' in code_after and '"""' not in code_before:
                self.data["prompt_patterns"]["successful"].append(
                    "Adding or improving docstrings"
                )
            
            # Deduplicate patterns
            self.data["prompt_patterns"]["successful"] = list(set(self.data["prompt_patterns"]["successful"]))
    
    def generate_improvement_report(self) -> str:
        """
        Generate a report on improvement progress.
        
        Returns:
            Report text
        """
        report = "AdaptaGen Improvement Report\n"
        report += "=========================\n\n"
        
        # Overall statistics
        total_attempts = sum(comp["attempts"] for comp in self.data["component_history"].values())
        total_successes = sum(comp["successes"] for comp in self.data["component_history"].values())
        success_rate = total_successes / total_attempts if total_attempts > 0 else 0
        
        report += f"Overall Statistics:\n"
        report += f"- Total edit attempts: {total_attempts}\n"
        report += f"- Successful edits: {total_successes}\n"
        report += f"- Success rate: {success_rate:.2%}\n\n"
        
        # Approach effectiveness
        report += f"Approach Effectiveness:\n"
        for approach, data in self.data["approach_success_rates"].items():
            if data["attempts"] > 0:
                approach_success_rate = data["successes"] / data["attempts"]
                report += f"- {approach}: {approach_success_rate:.2%} ({data['successes']}/{data['attempts']})\n"
        
        report += "\n"
        
        # Most improved components
        if self.data["complexity_metrics"]:
            report += f"Most Improved Components:\n"
            component_improvements = []
            
            for component, metrics in self.data["complexity_metrics"].items():
                if metrics:
                    # Calculate total improvement
                    total_improvement = sum(m["change"].get("cyclomatic", 0) for m in metrics)
                    component_improvements.append((component, total_improvement))
            
            # Sort by improvement (most improved first)
            sorted_improvements = sorted(component_improvements, key=lambda x: x[1], reverse=True)
            
            for component, improvement in sorted_improvements[:5]:
                report += f"- {component}: {improvement} complexity reduction\n"
        
        return report

def main():
    """Test the SimpleLearningDatabase functionality."""
    print("Testing SimpleLearningDatabase...")
    
    # Create a learning database
    db_file = Path(".adaptagen_learning_test.json")
    db = SimpleLearningDatabase(db_file)
    
    # Record some test edit attempts
    print("Recording test edit attempts...")
    
    # Successful edit
    db.record_edit_attempt(
        component_name="TestComponent",
        approach="standard",
        success=True,
        code_before="def test():\n    pass",
        code_after="def test():\n    print('Hello, world!')"
    )
    
    # Failed edit
    db.record_edit_attempt(
        component_name="TestComponent",
        approach="simplified",
        success=False,
        code_before="def test():\n    pass",
        error_message="Verification failed"
    )
    
    # Generate a report
    print("\n" + "="*50)
    print("IMPROVEMENT REPORT")
    print("="*50)
    report = db.generate_improvement_report()
    print(report)
    
    # Print the raw data
    print("\n" + "="*50)
    print("RAW DATABASE CONTENT")
    print("="*50)
    with open(db_file, 'r') as f:
        data = json.load(f)
        print(json.dumps(data, indent=2))
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main() 