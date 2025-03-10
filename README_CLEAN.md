# AdaptaGen - Modular Self-Modifying AI Agent

This is a refactored version of AdaptaGen that follows better software design principles (PEP8, SOLID, DRY, KISS) and has a more modular structure.

## Structure

The system is divided into four main components:

1. **Main Script (`adaptagen_main.py`)**: Entry point for the application that handles command-line arguments and delegates to the appropriate modules.

2. **Version Loader (`version_loader.py`)**: Handles loading different versions of the agent, with fallback mechanisms to ensure a working version is always loaded.

3. **Agent Template (`adaptagen_template.py`)**: Base template for the agent that will be used as a starting point for new versions.

4. **Improvement Analyzer (`improvement_analyzer.py`)**: Analyzes code to identify areas for improvement and provides targeted recommendations.

## Features

- **Progressive Version Loading**: The system attempts to load the latest version first, but falls back to earlier versions if the latest doesn't work.
- **Version Status Tracking**: The system keeps track of which versions work and which don't, to avoid repeatedly trying to load broken versions.
- **Modular Design**: Each component has a single responsibility, making the code easier to maintain and extend.
- **Clean Code**: Follows PEP8 style guidelines and SOLID principles.
- **Minimal Documentation**: Focuses on essential documentation without fluff.
- **NAME Token Filtering**: Filters out 'NAME' tokens from validation to prevent unnecessary warnings.
- **Version Fixing**: Allows a working version to fix the next version that needs improvement.
- **Code Analysis**: Provides detailed analysis of code quality and targeted improvement suggestions.

## Usage

```bash
# Run the latest working version
python adaptagen_main.py

# Run a specific version
python adaptagen_main.py --specific-version 0.0.2-r1

# Run in test mode
python adaptagen_main.py --test

# Generate a report
python adaptagen_main.py --report

# List all versions
python adaptagen_main.py --list-versions

# Run with incremental editing
python adaptagen_main.py --incremental

# Run with patient mode (extended backoff times)
python adaptagen_main.py --patient

# Limit the number of components processed
python adaptagen_main.py --max-components 5

# Create a new version based on the latest working version
python adaptagen_main.py --create-new --version-type revision

# Use the latest working version to fix the next version
python adaptagen_main.py --fix-next

# Analyze the latest version for improvement suggestions
python adaptagen_main.py --analyze

# Analyze a specific file
python adaptagen_main.py --analyze-file path/to/file.py

# Filter analysis by category
python adaptagen_main.py --analyze --analyze-category documentation

# Filter analysis by component
python adaptagen_main.py --analyze --analyze-component "class:ClassName"

# Limit the number of suggestions
python adaptagen_main.py --analyze --analyze-limit 5
```

## How It Works

1. The main script parses command-line arguments and initializes the version loader.
2. The version loader finds and loads the appropriate version of the agent.
3. The agent is initialized with the configuration and runs according to the specified parameters.
4. The improvement analyzer can be used to identify areas for improvement in the code.

## Improvement Analyzer

The Improvement Analyzer module helps the agent identify areas for improvement in its codebase. It analyzes the code and provides targeted recommendations for enhancing code quality.

The analyzer checks for issues in the following categories:

- **Documentation**: Missing or inadequate docstrings and comments
- **Complexity**: High cyclomatic complexity and long functions/classes
- **Structure**: Large classes with too many responsibilities and unused imports
- **Error Handling**: Missing try-except blocks and bare except clauses
- **Performance**: Inefficient code patterns
- **Code Style**: TODO comments and long lines

Each suggestion includes:
- The component it applies to (overall, class, or function)
- A priority level (1-10, with 10 being highest)
- A description of the issue
- A rationale explaining why it's an issue

## Extending the System

To add new functionality:

1. Create a new version of the agent based on the template or an existing version.
2. Implement the new functionality.
3. The version loader will automatically detect and use the new version.

## Requirements

- Python 3.7+
- Google Generative AI Python SDK
- python-dotenv

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file with the following variables:

```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-pro
TEMPERATURE=0.7
MAX_OUTPUT_TOKENS=8192
TOP_P=0.95
TOP_K=40
``` 