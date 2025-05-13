import json
import os

# The path to the workflow configuration file
workflow_path = ".replit/.workflows/Start application.workflow"

try:
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(workflow_path), exist_ok=True)
    
    # Define the new workflow configuration
    workflow_config = {
        "name": "Start application",
        "author": "agent",
        "tasks": [
            {
                "task": "shell.exec",
                "args": "hypercorn --bind 0.0.0.0:5000 --reload main:app",
                "waitForPort": 5000
            }
        ]
    }
    
    # Write the configuration to the file
    with open(workflow_path, 'w') as f:
        json.dump(workflow_config, f, indent=2)
    
    print(f"Updated workflow configuration at {workflow_path}")
    print("Please restart the workflow to apply the changes.")
except Exception as e:
    print(f"Error updating workflow configuration: {e}")