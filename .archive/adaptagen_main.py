#!/usr/bin/env python3
"""
AdaptaGen Main Script - Entry point for the self-modifying AI agent.
"""

import argparse
import logging
import sys
import importlib.util
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='AdaptaGen: Self-Modifying AI Agent')
    parser.add_argument('--incremental', action='store_true', 
                        help='Use incremental editing instead of full regeneration')
    parser.add_argument('--version-type', choices=['major', 'minor', 'patch', 'revision'], 
                        default='revision', help='Type of version increment')
    parser.add_argument('--test', action='store_true', 
                        help='Run in test mode without making changes')
    parser.add_argument('--goal', type=str, 
                        help='Specify a goal to use (e.g., "performance", "documentation", "features")')
    parser.add_argument('--report', action='store_true', 
                        help='Generate a report on learned information')
    parser.add_argument('--list-versions', action='store_true', 
                        help='List all versions in the version history')
    parser.add_argument('--max-components', type=int, default=10, 
                        help='Maximum number of components to process in a single run')
    parser.add_argument('--patient', action='store_true', 
                        help='Use extended backoff times for more patient operation (up to 1 hour)')
    parser.add_argument('--specific-version', type=str,
                        help='Load a specific version instead of the latest')
    parser.add_argument('--fix-next', action='store_true',
                        help='Use the latest working version to fix the next version')
    parser.add_argument('--fix-with', type=str,
                        help='Specify which version to use for fixing (e.g., "0.0.2-r1")')
    parser.add_argument('--fix-target', type=str,
                        help='Specify which version to fix (e.g., "0.0.2-r2")')
    parser.add_argument('--create-new', action='store_true',
                        help='Create a new version based on the latest working version')
    parser.add_argument('--analyze', action='store_true',
                        help='Analyze the code and suggest improvements')
    parser.add_argument('--analyze-file', type=str,
                        help='Specify a file to analyze for improvements')
    parser.add_argument('--analyze-category', type=str, choices=['documentation', 'complexity', 'structure', 'error_handling', 'performance', 'code_style'],
                        help='Filter improvement suggestions by category')
    parser.add_argument('--analyze-component', type=str,
                        help='Filter improvement suggestions by component (e.g., "class:ClassName", "function:function_name")')
    parser.add_argument('--analyze-limit', type=int, default=10,
                        help='Limit the number of improvement suggestions to display')
    
    return parser.parse_args()

def main():
    """Main entry point for AdaptaGen."""
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Import the version loader module
        from version_loader import VersionLoader
        
        # Initialize the version loader
        loader = VersionLoader()
        
        # Analyze code if requested
        if args.analyze or args.analyze_file:
            from improvement_analyzer import ImprovementAnalyzer
            
            # Determine which file to analyze
            file_to_analyze = None
            
            if args.analyze_file:
                file_to_analyze = Path(args.analyze_file)
            else:
                # If no specific file is provided, analyze the latest version
                _, version = loader.load_latest_working_version()
                if not version:
                    logger.error("No working version found to analyze")
                    sys.exit(1)
                    
                # Find the file for this version
                version_files = loader._find_version_files()
                for v, file_path in version_files:
                    if v == version:
                        file_to_analyze = file_path
                        break
                        
            if not file_to_analyze or not file_to_analyze.exists():
                logger.error(f"File to analyze not found: {file_to_analyze}")
                sys.exit(1)
                
            # Create and run the analyzer
            analyzer = ImprovementAnalyzer(file_to_analyze)
            if not analyzer.load_code():
                logger.error(f"Failed to load code from {file_to_analyze}")
                sys.exit(1)
                
            suggestions = analyzer.analyze()
            
            # Filter suggestions if requested
            if args.analyze_category:
                suggestions = analyzer.get_suggestions_by_category(args.analyze_category)
                
            if args.analyze_component:
                suggestions = analyzer.get_suggestions_for_component(args.analyze_component)
                
            # Limit the number of suggestions
            if args.analyze_limit > 0 and len(suggestions) > args.analyze_limit:
                suggestions = suggestions[:args.analyze_limit]
                
            # Generate and print the report
            if suggestions:
                print(analyzer.generate_report())
            else:
                print("No improvement suggestions found with the specified filters.")
                
            return
        
        # List versions if requested
        if args.list_versions:
            versions = loader.list_all_versions()
            if versions:
                print("Version History:")
                for v, status in versions:
                    status_marker = "✓" if status == "working" else "✗" if status == "failed" else "?"
                    print(f"  {status_marker} {v}")
            else:
                print("No version history found.")
            return
            
        # Create a new version if requested
        if args.create_new:
            # Load the latest working version first
            _, working_version = loader.load_latest_working_version()
            if not working_version:
                logger.error("No working version found to base new version on")
                sys.exit(1)
                
            # Create a new version
            new_version, new_file_path = loader.create_new_version(working_version, args.version_type)
            if not new_version:
                logger.error("Failed to create new version")
                sys.exit(1)
                
            print(f"Created new version {new_version} at {new_file_path}")
            return
            
        # Fix the next version if requested
        if args.fix_next or (args.fix_with and args.fix_target):
            # Determine which version to use for fixing
            working_module = None
            working_version = ""
            next_version = ""
            
            if args.fix_with and args.fix_target:
                # Use specified versions
                working_module, working_version = loader.load_specific_version(args.fix_with)
                if not working_module:
                    logger.error(f"Failed to load specified fixing version: {args.fix_with}")
                    sys.exit(1)
                next_version = args.fix_target
            else:
                # Use the working version and get the next version to fix
                working_module, working_version, next_version = loader.load_next_version_to_fix()
                
            if not working_module:
                logger.error("No working version found")
                sys.exit(1)
                
            if not next_version:
                logger.error("No next version to fix found")
                sys.exit(1)
                
            # Get the AdaptaGen and Config classes from the loaded module
            AdaptaGen = getattr(working_module, 'AdaptaGen')
            Config = getattr(working_module, 'Config')
            
            logger.info(f"Using {working_version} to fix {next_version}")
            
            # Initialize configuration from environment variables
            config = Config.from_env()
            
            # Initialize the agent
            agent = AdaptaGen(config)
            
            # Run the agent in fix mode
            if hasattr(agent, 'fix_version') and callable(getattr(agent, 'fix_version')):
                agent.fix_version(next_version, args.incremental, args.max_components, args.patient)
            else:
                logger.error(f"Version {working_version} does not support fixing other versions")
                sys.exit(1)
                
            return
        
        # Load the agent module (either specific version or latest working version)
        if args.specific_version:
            agent_module, version = loader.load_specific_version(args.specific_version)
            if not agent_module:
                logger.error(f"Failed to load specified version: {args.specific_version}")
                sys.exit(1)
        else:
            agent_module, version = loader.load_latest_working_version()
            if not agent_module:
                logger.error("Failed to load any working version")
                sys.exit(1)
        
        # Get the AdaptaGen and Config classes from the loaded module
        AdaptaGen = getattr(agent_module, 'AdaptaGen')
        Config = getattr(agent_module, 'Config')
        
        logger.info(f"Successfully loaded AdaptaGen version {version}")
        
        # Initialize configuration from environment variables
        config = Config.from_env()
        
        # Initialize the agent
        agent = AdaptaGen(config)
        
        # Generate report if requested
        if args.report:
            if hasattr(agent, 'learning_db') and agent.learning_db:
                report = agent.generate_improvement_report()
                print("\nImprovement Report:")
                print(report)
                
                # Print raw database content for debugging
                import json
                print("\nRaw Database Content:")
                print(json.dumps(agent.learning_db.data, indent=2))
            else:
                print("No learning database available.")
            return
        
        # Run in test mode if requested
        if args.test:
            print(f"Running AdaptaGen version {version} in test mode")
            print(f"Current file: {__file__}")
            print(f"Version type: {args.version_type}")
            print(f"Incremental: {args.incremental}")
            if args.goal:
                print(f"Goal: {args.goal}")
            if args.patient:
                print("Patient mode: Enabled (using extended backoff times up to 1 hour)")
            if args.max_components:
                print(f"Max components: {args.max_components}")
            return
        
        # Run the agent
        agent.run(
            increment_type=args.version_type,
            use_incremental=args.incremental,
            goal_name=args.goal,
            max_components=args.max_components,
            patient_mode=args.patient
        )
    except ImportError as e:
        logger.error(f"Failed to import required module: {e}")
        print(f"Error: Make sure all required modules are available.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 