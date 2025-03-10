# AdaptaGen

A self-modifying Python script that uses the Gemini API to read and improve its own code.

## Overview

AdaptaGen is a Python script that can:
1. Read its own source code
2. Use the Gemini API to generate improved versions of itself
3. Write the new version to a file
4. Follow SOLID, DRY, PEP 8, and KISS principles
5. Track its own evolution with built-in version control

The initial goal of AdaptaGen is to make controlled edits to itself, but this can be extended to other goals by implementing new Goal classes.

## Requirements

- Python 3.7+
- Google Gemini API key

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/AdaptaGen.git
   cd AdaptaGen
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project directory with your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage

### Basic Usage

Run the script to generate an improved version:
```
python adaptagen_0_0_1_r1.py
```

The script will:
1. Read its own source code
2. Generate an improved version using the Gemini API
3. Write the new version to a file with an incremented version number
4. Save the version history in the `.adaptagen_versions` directory

### Version Control Commands

List all versions in the version history:
```
python adaptagen_0_0_1_r1.py list-versions
```

Run with a specific version increment type:
```
python adaptagen_0_0_1_r1.py run [increment_type]
```

Where `increment_type` can be:
- `major` - Increment the major version (X.0.0-r0)
- `minor` - Increment the minor version (0.X.0-r0)
- `patch` - Increment the patch version (0.0.X-r0)
- `revision` - Increment the revision number (0.0.0-rX) [default]

## Version Control System

AdaptaGen includes a basic version control system that:

1. Tracks all versions of the script
2. Stores version history in the `.adaptagen_versions` directory
3. Maintains metadata about each version (timestamp, hash, etc.)
4. Automatically increments version numbers
5. Allows listing and retrieving previous versions

## Configuration

You can configure the following parameters in the `.env` file:

```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-pro
TEMPERATURE=0.7
MAX_OUTPUT_TOKENS=8192
TOP_P=0.95
TOP_K=40
```

## Extending AdaptaGen

### Adding New Goals

To add new goals for self-modification:

1. Create a new class that inherits from the `Goal` abstract base class
2. Implement the `get_description()` and `get_prompt()` methods
3. Update the `AdaptaGen` class to use your new goal

### Enhancing Version Control

The version control system can be extended by:

1. Adding methods to the `CodeManager` class for more advanced version management
2. Implementing version comparison and diff functionality
3. Adding rollback capabilities to revert to previous versions

## License

MIT 