import os
import sys
import runpy

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if __name__ == "__main__":
    # Execute Application.main as if it were invoked directly so its argparse logic runs
    runpy.run_module("Application.main", run_name="__main__")
