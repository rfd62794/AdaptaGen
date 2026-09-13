# AdaptaGen

A self-modifying AI agent using the Gemini API with version control.

## Overview

AdaptaGen is a Python-based AI agent that can modify and improve its own code. It uses the Gemini API to generate improvements and implements a version control system to track changes.

## Features

- **Self-Modification**: The agent can modify and improve its own code.
- **Version Control**: Tracks changes and maintains a history of versions.
- **Incremental Editing**: Can edit code component by component instead of regenerating the entire codebase.
- **Goal-Based Improvements**: Supports different improvement goals (performance, documentation, features).
- **Learning Database**: Learns from past improvements to make better edits in the future.
- **Error Handling**: Robust error handling and recovery mechanisms.
- **Code Validation**: Validates generated code for common issues.

## Installation

```bash
# Clone the repository
git clone https://github.com/rfd62794/AdaptaGen.git
cd AdaptaGen

# Install the package
pip install -e .
```

## Usage

### Basic Usage

```bash
# Run with default settings (incremental revision)
adaptagen

# Run with incremental editing
adaptagen --incremental

# Run with a specific goal
adaptagen --goal "documentation"

# Run in patient mode with extended backoff times
adaptagen --patient

# Limit the number of components to process
adaptagen --max-components 5
```

### Advanced Usage

```bash
# List all versions
adaptagen --list-versions

# Generate a report on learned information
adaptagen --report

# Run in test mode without making changes
adaptagen --test

# Create a new version based on the latest working version
adaptagen --create-new

# Fix a specific version
adaptagen --fix-with "0.0.2-r1" --fix-target "0.0.2-r2"

# Analyze code for improvements
adaptagen --analyze

# Analyze a specific file
adaptagen --analyze-file "path/to/file.py"
```

## Project Structure

The project is organized into modules:

- `adaptagen/core/`: Core functionality
  - `adaptagen.py`: Main AdaptaGen class
  - `config.py`: Configuration management
- `adaptagen/modules/`: Individual modules
  - `api_client.py`: Gemini API interaction
  - `code_manager.py`: Code reading, writing, and manipulation
  - `code_validator.py`: Code validation and fixing
  - `goal_system.py`: Goal management
  - `incremental_editor.py`: Incremental editing
  - `learning_db.py`: Learning database
  - `token_system.py`: Token management
  - `version_control.py`: Version control

## Requirements

- Python 3.8+
- Google Generative AI Python SDK
- Python-dotenv

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

## License

MIT License 