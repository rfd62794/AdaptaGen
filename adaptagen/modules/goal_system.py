"""
Goal Management Module - Defines goals and manages goal selection for the agent.
"""

import logging
import random
from typing import Dict, List, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)

class Goal:
    """Base class for defining goals."""
    
    description: str = "No description provided"
    priority: int = 5  # Default priority (1-10, 10 being highest)
    
    def __init__(self):
        """Initialize the goal."""
        pass
        
    def get_prompt(self, current_code: str, config) -> str:
        """Generate a prompt for this goal."""
        raise NotImplementedError("Subclasses must implement get_prompt")
        
    def get_enhanced_prompt(self, current_code: str, config, issues: List[str]) -> str:
        """Generate an enhanced prompt addressing specific issues."""
        # Default implementation just adds the issues to the regular prompt
        base_prompt = self.get_prompt(current_code, config)
        
        issues_text = "\n\nThe previous attempt had these issues:\n"
        for issue in issues:
            issues_text += f"- {issue}\n"
            
        issues_text += "\nPlease address these issues in your response."
        
        return base_prompt + issues_text

class SelfEditGoal(Goal):
    """Goal for self-editing and improvement."""
    
    description = "Improve code structure, functionality, and robustness."
    priority = 10  # Highest priority
    
    def get_prompt(self, current_code: str, config) -> str:
        """Generate a prompt for self-editing."""
        return f"""You are AdaptaGen, a self-modifying Python script. Your task is to improve your own code to make it more robust, efficient, and maintainable.

Current code:
```python
{current_code}
```

Please generate an improved version of the code with the following enhancements:
1. Improve error handling and robustness
2. Enhance code organization and structure
3. Add or improve documentation
4. Optimize performance where possible
5. Fix any bugs or edge cases
6. Ensure consistent coding style

Important guidelines:
- Preserve all existing functionality
- Keep the same overall architecture
- Maintain backward compatibility
- Ensure the code is complete and can run as a standalone script
- Include all necessary imports
- Preserve the VERSION constant but update its value
- Keep the main execution block at the end

Return the complete improved code as a single Python script.
"""
        
    def get_enhanced_prompt(self, current_code: str, config, issues: List[str]) -> str:
        """Generate an enhanced prompt addressing specific issues."""
        base_prompt = self.get_prompt(current_code, config)
        
        issues_text = "\n\nThe previous attempt had these issues:\n"
        for issue in issues:
            issues_text += f"- {issue}\n"
            
        issues_text += """
Please address these issues in your response and follow these additional guidelines:
- Ensure all imports from the original code are preserved
- Make sure all class and function definitions from the original code are included
- Verify that the code is syntactically correct
- Check that all docstrings are properly formatted
- Ensure the main execution block is preserved
- Make sure the VERSION constant is properly defined
"""
        
        return base_prompt + issues_text

class PerformanceGoal(Goal):
    """Goal for improving performance and efficiency."""
    
    description = "Improve performance and efficiency of the code."
    priority = 7
    
    def get_prompt(self, current_code: str, config) -> str:
        """Generate a prompt for performance improvement."""
        return f"""You are AdaptaGen, a self-modifying Python script. Your task is to improve your own code to make it more efficient and performant.

Current code:
```python
{current_code}
```

Please generate an improved version of the code with the following performance enhancements:
1. Optimize algorithms and data structures
2. Reduce unnecessary computations
3. Improve memory usage
4. Enhance I/O operations efficiency
5. Implement caching where appropriate
6. Reduce API call overhead
7. Optimize loops and conditionals

Important guidelines:
- Preserve all existing functionality
- Keep the same overall architecture
- Maintain backward compatibility
- Ensure the code is complete and can run as a standalone script
- Include all necessary imports
- Preserve the VERSION constant but update its value
- Keep the main execution block at the end

Return the complete improved code as a single Python script.
"""
        
    def get_enhanced_prompt(self, current_code: str, config, issues: List[str]) -> str:
        """Generate an enhanced prompt addressing specific issues."""
        base_prompt = self.get_prompt(current_code, config)
        
        issues_text = "\n\nThe previous attempt had these issues:\n"
        for issue in issues:
            issues_text += f"- {issue}\n"
            
        issues_text += """
Please address these issues in your response and follow these additional guidelines:
- Ensure all imports from the original code are preserved
- Make sure all class and function definitions from the original code are included
- Verify that the code is syntactically correct
- Focus on performance improvements that don't sacrifice readability
- Consider time complexity of algorithms
- Look for opportunities to reduce API calls through batching or caching
- Ensure the main execution block is preserved
- Make sure the VERSION constant is properly defined
"""
        
        return base_prompt + issues_text

class DocumentationGoal(Goal):
    """Goal for improving documentation and code clarity."""
    
    description = "Improve documentation and code clarity."
    priority = 8
    
    def get_prompt(self, current_code: str, config) -> str:
        """Generate a prompt for documentation improvement."""
        return f"""You are AdaptaGen, a self-modifying Python script. Your task is to improve your own code's documentation and clarity.

Current code:
```python
{current_code}
```

Please generate an improved version of the code with the following documentation enhancements:
1. Add or improve docstrings for all classes and functions
2. Add type hints where missing
3. Improve variable and function naming for clarity
4. Add explanatory comments for complex sections
5. Ensure consistent documentation style
6. Improve code organization for readability
7. Add examples where helpful

Important guidelines:
- Preserve all existing functionality
- Keep the same overall architecture
- Maintain backward compatibility
- Ensure the code is complete and can run as a standalone script
- Include all necessary imports
- Preserve the VERSION constant but update its value
- Keep the main execution block at the end

Return the complete improved code as a single Python script.
"""
        
    def get_enhanced_prompt(self, current_code: str, config, issues: List[str]) -> str:
        """Generate an enhanced prompt addressing specific issues."""
        base_prompt = self.get_prompt(current_code, config)
        
        issues_text = "\n\nThe previous attempt had these issues:\n"
        for issue in issues:
            issues_text += f"- {issue}\n"
            
        issues_text += """
Please address these issues in your response and follow these additional guidelines:
- Ensure all imports from the original code are preserved
- Make sure all class and function definitions from the original code are included
- Verify that the code is syntactically correct
- Follow Google-style docstring format
- Add type hints that are accurate and helpful
- Ensure comments explain "why" not just "what"
- Ensure the main execution block is preserved
- Make sure the VERSION constant is properly defined
"""
        
        return base_prompt + issues_text

class FeatureGoal(Goal):
    """Goal for adding new features."""
    
    description = "Add new features to enhance functionality."
    priority = 6
    
    def __init__(self, feature_description: str = None):
        """
        Initialize the feature goal.
        
        Args:
            feature_description: Description of the feature to add
        """
        super().__init__()
        self.feature_description = feature_description or "Add self-improvement capabilities"
        self.description = f"Add new feature: {self.feature_description}"
        
    def get_prompt(self, current_code: str, config) -> str:
        """Generate a prompt for adding a new feature."""
        return f"""You are AdaptaGen, a self-modifying Python script. Your task is to improve your own code by adding a new feature.

Current code:
```python
{current_code}
```

Please generate an improved version of the code that adds the following feature:
{self.feature_description}

The implementation should:
1. Integrate seamlessly with the existing codebase
2. Follow the same coding style and patterns
3. Include proper error handling
4. Be well-documented with docstrings and comments
5. Include any necessary new classes, functions, or methods
6. Update existing code to support the new feature

Important guidelines:
- Preserve all existing functionality
- Keep the same overall architecture
- Maintain backward compatibility
- Ensure the code is complete and can run as a standalone script
- Include all necessary imports
- Preserve the VERSION constant but update its value
- Keep the main execution block at the end

Return the complete improved code as a single Python script.
"""
        
    def get_enhanced_prompt(self, current_code: str, config, issues: List[str]) -> str:
        """Generate an enhanced prompt addressing specific issues."""
        base_prompt = self.get_prompt(current_code, config)
        
        issues_text = "\n\nThe previous attempt had these issues:\n"
        for issue in issues:
            issues_text += f"- {issue}\n"
            
        issues_text += f"""
Please address these issues in your response and follow these additional guidelines:
- Ensure all imports from the original code are preserved
- Make sure all class and function definitions from the original code are included
- Verify that the code is syntactically correct
- Focus on implementing the feature: {self.feature_description} correctly
- Make sure the new feature is properly integrated with existing code
- Add appropriate tests or validation for the new feature
- Ensure the main execution block is preserved
- Make sure the VERSION constant is properly defined
"""
        
        return base_prompt + issues_text

class GoalManager:
    """Manages goals and goal selection for the agent."""
    
    def __init__(self):
        """Initialize the goal manager with default goals."""
        self.goals = [
            SelfEditGoal(),
            DocumentationGoal(),
            PerformanceGoal(),
            FeatureGoal("Implement learning from past improvements"),
            FeatureGoal("Add progressive complexity management"),
            FeatureGoal("Add self-evaluation capabilities")
        ]
        
        # Sort goals by priority (highest first)
        self.goals.sort(key=lambda g: g.priority, reverse=True)
        
        # Track the current goal index
        self.current_goal_index = 0
        
    def add_goal(self, goal: Goal) -> None:
        """
        Add a new goal to the manager.
        
        Args:
            goal: The goal to add
        """
        self.goals.append(goal)
        
        # Re-sort goals by priority
        self.goals.sort(key=lambda g: g.priority, reverse=True)
        
        # Reset current goal index to the highest priority goal
        self.current_goal_index = 0
        
    def get_current_goal(self) -> Goal:
        """
        Get the current goal.
        
        Returns:
            The current goal
        """
        if not self.goals:
            # If no goals defined, create a default goal
            return SelfEditGoal()
            
        return self.goals[self.current_goal_index]
        
    def rotate_goal(self) -> Goal:
        """
        Rotate to the next goal in the priority list.
        
        Returns:
            The next goal
        """
        if not self.goals:
            return SelfEditGoal()
            
        # Move to the next goal
        self.current_goal_index = (self.current_goal_index + 1) % len(self.goals)
        
        # Occasionally (10% chance) pick a random goal to ensure all goals get attention
        if random.random() < 0.1:
            old_index = self.current_goal_index
            while self.current_goal_index == old_index:
                self.current_goal_index = random.randint(0, len(self.goals) - 1)
                
        return self.goals[self.current_goal_index]
        
    def get_goal_by_name(self, name: str) -> Optional[Goal]:
        """
        Get a goal by its description.
        
        Args:
            name: The goal description or a substring of it
            
        Returns:
            The matching goal or None if not found
        """
        name = name.lower()
        
        for goal in self.goals:
            if name in goal.description.lower():
                return goal
                
        return None 