import sys
import os

# Ensure the backend package root is on sys.path so imports resolve correctly
# regardless of where pytest is invoked from.
sys.path.insert(0, os.path.dirname(__file__))
