#!/usr/bin/env python3
import unittest
import sys
import os

# Add Project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../Project')))

if __name__ == "__main__":
    # Discover and run all tests in the 'tests/' directory
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with a non-zero status code if any tests failed
    if not result.wasSuccessful():
        sys.exit(1)