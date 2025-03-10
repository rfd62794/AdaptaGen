#!/usr/bin/env python3
"""
Improvement Analyzer Module - Helps the agent identify areas for improvement in its codebase.
"""

import ast
import logging
import re
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
import importlib.util

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class CodeMetrics:
    """Metrics for a code component."""
    lines: int = 0
    complexity: int = 0
    comments: int = 0
    docstring_lines: int = 0
    function_count: int = 0
    class_count: int = 0
    import_count: int = 0
    todo_count: int = 0
    
@dataclass
class ImprovementSuggestion:
    """Suggestion for improving code."""
    component: str
    priority: int  # 1-10, 10 being highest
    category: str  # 'documentation', 'performance', 'structure', 'functionality', etc.
    description: str
    rationale: str

class ImprovementAnalyzer:
    """
    Analyzes code to identify areas for improvement.
    Provides targeted recommendations for enhancing code quality.
    """
    
    def __init__(self, code_path: Path = None):
        """
        Initialize the improvement analyzer.
        
        Args:
            code_path: Path to the code file to analyze
        """
        self.code_path = code_path
        self.code = ""
        self.ast_tree = None
        self.metrics = {}
        self.suggestions = []
        
    def load_code(self, code_path: Path = None) -> bool:
        """
        Load code from a file.
        
        Args:
            code_path: Path to the code file (overrides the path set in __init__)
            
        Returns:
            True if loading succeeded, False otherwise
        """
        if code_path:
            self.code_path = code_path
            
        if not self.code_path or not self.code_path.exists():
            logger.error(f"Invalid code path: {self.code_path}")
            return False
            
        try:
            with open(self.code_path, 'r', encoding='utf-8') as f:
                self.code = f.read()
                
            # Parse the AST
            self.ast_tree = ast.parse(self.code)
            return True
        except Exception as e:
            logger.error(f"Failed to load code: {e}")
            return False
            
    def analyze(self) -> List[ImprovementSuggestion]:
        """
        Analyze the code and generate improvement suggestions.
        
        Returns:
            List of improvement suggestions
        """
        if not self.code:
            logger.error("No code loaded")
            return []
            
        # Clear previous analysis
        self.metrics = {}
        self.suggestions = []
        
        # Collect metrics
        self._collect_metrics()
        
        # Generate suggestions
        self._check_documentation()
        self._check_complexity()
        self._check_structure()
        self._check_error_handling()
        self._check_performance()
        self._check_code_style()
        
        # Sort suggestions by priority (highest first)
        self.suggestions.sort(key=lambda s: s.priority, reverse=True)
        
        return self.suggestions
        
    def _collect_metrics(self) -> None:
        """Collect metrics for the code."""
        # Overall metrics
        self.metrics['overall'] = CodeMetrics(
            lines=len(self.code.splitlines()),
            import_count=len([n for n in ast.walk(self.ast_tree) if isinstance(n, (ast.Import, ast.ImportFrom))]),
            todo_count=len(re.findall(r'#\s*TODO', self.code, re.IGNORECASE))
        )
        
        # Collect metrics for each class and function
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.ClassDef):
                class_code = ast.get_source_segment(self.code, node)
                if class_code:
                    self.metrics[f"class:{node.name}"] = self._get_component_metrics(node, class_code)
                    self.metrics['overall'].class_count += 1
            elif isinstance(node, ast.FunctionDef):
                # Skip methods (they're part of classes)
                if not any(isinstance(parent, ast.ClassDef) for parent in ast.iter_fields(node)):
                    func_code = ast.get_source_segment(self.code, node)
                    if func_code:
                        self.metrics[f"function:{node.name}"] = self._get_component_metrics(node, func_code)
                        self.metrics['overall'].function_count += 1
                        
    def _get_component_metrics(self, node: ast.AST, code: str) -> CodeMetrics:
        """
        Get metrics for a code component.
        
        Args:
            node: AST node for the component
            code: Source code for the component
            
        Returns:
            CodeMetrics for the component
        """
        lines = len(code.splitlines())
        
        # Count docstring lines
        docstring = ast.get_docstring(node)
        docstring_lines = len(docstring.splitlines()) if docstring else 0
        
        # Count comments
        comment_count = 0
        for line in code.splitlines():
            if '#' in line:
                comment_count += 1
                
        # Calculate cyclomatic complexity (simplified)
        complexity = 1  # Base complexity
        for subnode in ast.walk(node):
            if isinstance(subnode, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(subnode, ast.BoolOp) and isinstance(subnode.op, (ast.And, ast.Or)):
                complexity += len(subnode.values) - 1
                
        return CodeMetrics(
            lines=lines,
            complexity=complexity,
            comments=comment_count,
            docstring_lines=docstring_lines
        )
        
    def _check_documentation(self) -> None:
        """Check for documentation issues."""
        # Check overall documentation
        if self.metrics['overall'].docstring_lines < 5:
            self.suggestions.append(ImprovementSuggestion(
                component="overall",
                priority=8,
                category="documentation",
                description="Improve module-level documentation",
                rationale="The module has minimal or no top-level documentation"
            ))
            
        # Check class and function documentation
        for name, metrics in self.metrics.items():
            if name.startswith(("class:", "function:")) and metrics.docstring_lines == 0:
                component_type, component_name = name.split(":", 1)
                self.suggestions.append(ImprovementSuggestion(
                    component=name,
                    priority=7,
                    category="documentation",
                    description=f"Add docstring to {component_type} {component_name}",
                    rationale=f"The {component_type} {component_name} has no docstring"
                ))
                
    def _check_complexity(self) -> None:
        """Check for complexity issues."""
        for name, metrics in self.metrics.items():
            if name.startswith(("class:", "function:")) and metrics.complexity > 10:
                component_type, component_name = name.split(":", 1)
                self.suggestions.append(ImprovementSuggestion(
                    component=name,
                    priority=9,
                    category="complexity",
                    description=f"Reduce complexity of {component_type} {component_name}",
                    rationale=f"The {component_type} {component_name} has high cyclomatic complexity ({metrics.complexity})"
                ))
                
            if name.startswith(("class:", "function:")) and metrics.lines > 100:
                component_type, component_name = name.split(":", 1)
                self.suggestions.append(ImprovementSuggestion(
                    component=name,
                    priority=8,
                    category="complexity",
                    description=f"Break down {component_type} {component_name} into smaller components",
                    rationale=f"The {component_type} {component_name} is very long ({metrics.lines} lines)"
                ))
                
    def _check_structure(self) -> None:
        """Check for structural issues."""
        # Check for large classes with many methods
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                if len(methods) > 10:
                    self.suggestions.append(ImprovementSuggestion(
                        component=f"class:{node.name}",
                        priority=7,
                        category="structure",
                        description=f"Consider breaking down class {node.name}",
                        rationale=f"The class {node.name} has {len(methods)} methods, which may indicate it has too many responsibilities"
                    ))
                    
        # Check for unused imports
        import_nodes = [n for n in ast.walk(self.ast_tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        imported_names = set()
        
        for node in import_nodes:
            if isinstance(node, ast.Import):
                for name in node.names:
                    imported_names.add(name.name)
            elif isinstance(node, ast.ImportFrom):
                for name in node.names:
                    if name.name == '*':
                        # Can't track * imports
                        continue
                    if node.module:
                        imported_names.add(f"{node.module}.{name.name}")
                    else:
                        imported_names.add(name.name)
                        
        # Simple check for unused imports (not perfect)
        used_names = set()
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
                
        potentially_unused = imported_names - used_names
        if potentially_unused:
            self.suggestions.append(ImprovementSuggestion(
                component="overall",
                priority=5,
                category="structure",
                description="Check for unused imports",
                rationale=f"There may be unused imports: {', '.join(sorted(potentially_unused))}"
            ))
            
    def _check_error_handling(self) -> None:
        """Check for error handling issues."""
        # Find functions with no error handling
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.FunctionDef):
                has_try = any(isinstance(n, ast.Try) for n in ast.walk(node))
                has_io = any(isinstance(n, ast.Call) and hasattr(n.func, 'id') and 
                            n.func.id in ('open', 'read', 'write', 'load', 'loads', 'request') 
                            for n in ast.walk(node))
                            
                if has_io and not has_try:
                    self.suggestions.append(ImprovementSuggestion(
                        component=f"function:{node.name}",
                        priority=8,
                        category="error_handling",
                        description=f"Add error handling to function {node.name}",
                        rationale=f"The function {node.name} performs I/O operations but has no try-except blocks"
                    ))
                    
        # Check for bare except clauses
        bare_excepts = [n for n in ast.walk(self.ast_tree) if isinstance(n, ast.ExceptHandler) and n.type is None]
        if bare_excepts:
            self.suggestions.append(ImprovementSuggestion(
                component="overall",
                priority=7,
                category="error_handling",
                description="Replace bare except clauses with specific exception types",
                rationale=f"Found {len(bare_excepts)} bare except clauses, which can hide bugs"
            ))
            
    def _check_performance(self) -> None:
        """Check for performance issues."""
        # Check for inefficient list operations
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.For):
                if isinstance(node.iter, ast.Call) and hasattr(node.iter.func, 'id') and node.iter.func.id == 'range':
                    # Check for range(len(x)) pattern
                    if (len(node.iter.args) == 1 and isinstance(node.iter.args[0], ast.Call) and 
                        hasattr(node.iter.args[0].func, 'id') and node.iter.args[0].func.id == 'len'):
                        self.suggestions.append(ImprovementSuggestion(
                            component="overall",
                            priority=6,
                            category="performance",
                            description="Use enumerate() instead of range(len())",
                            rationale="Using range(len(x)) is less efficient and less readable than enumerate(x)"
                        ))
                        
    def _check_code_style(self) -> None:
        """Check for code style issues."""
        # Check for TODO comments
        if self.metrics['overall'].todo_count > 0:
            self.suggestions.append(ImprovementSuggestion(
                component="overall",
                priority=5,
                category="code_style",
                description="Address TODO comments",
                rationale=f"Found {self.metrics['overall'].todo_count} TODO comments that should be addressed"
            ))
            
        # Check for long lines
        long_lines = 0
        for i, line in enumerate(self.code.splitlines()):
            if len(line) > 100:
                long_lines += 1
                
        if long_lines > 0:
            self.suggestions.append(ImprovementSuggestion(
                component="overall",
                priority=4,
                category="code_style",
                description="Fix long lines",
                rationale=f"Found {long_lines} lines longer than 100 characters"
            ))
            
    def generate_report(self) -> str:
        """
        Generate a human-readable report of the analysis.
        
        Returns:
            Report as a string
        """
        if not self.suggestions:
            return "No improvement suggestions found."
            
        report = "Improvement Analysis Report\n"
        report += "==========================\n\n"
        
        # Overall metrics
        report += "Overall Metrics:\n"
        report += f"  - Lines of code: {self.metrics['overall'].lines}\n"
        report += f"  - Classes: {self.metrics['overall'].class_count}\n"
        report += f"  - Functions: {self.metrics['overall'].function_count}\n"
        report += f"  - Imports: {self.metrics['overall'].import_count}\n"
        report += f"  - TODO comments: {self.metrics['overall'].todo_count}\n\n"
        
        # Suggestions by priority
        report += "Improvement Suggestions (by priority):\n"
        for i, suggestion in enumerate(self.suggestions, 1):
            report += f"{i}. [{suggestion.priority}/10] {suggestion.category.upper()}: {suggestion.description}\n"
            report += f"   Rationale: {suggestion.rationale}\n"
            report += f"   Component: {suggestion.component}\n\n"
            
        return report
        
    def get_top_suggestions(self, limit: int = 5) -> List[ImprovementSuggestion]:
        """
        Get the top N suggestions by priority.
        
        Args:
            limit: Maximum number of suggestions to return
            
        Returns:
            List of top suggestions
        """
        return self.suggestions[:limit]
        
    def get_suggestions_by_category(self, category: str) -> List[ImprovementSuggestion]:
        """
        Get suggestions filtered by category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of suggestions in the specified category
        """
        return [s for s in self.suggestions if s.category.lower() == category.lower()]
        
    def get_suggestions_for_component(self, component: str) -> List[ImprovementSuggestion]:
        """
        Get suggestions for a specific component.
        
        Args:
            component: Component to filter by
            
        Returns:
            List of suggestions for the specified component
        """
        return [s for s in self.suggestions if s.component == component]

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python improvement_analyzer.py <path_to_code_file>")
        sys.exit(1)
        
    analyzer = ImprovementAnalyzer(Path(sys.argv[1]))
    if analyzer.load_code():
        analyzer.analyze()
        print(analyzer.generate_report()) 