import sys
import os

# Replace 'yourusername' with your actual PythonAnywhere username
path = '/home/yourusername/expense-tracker'
if path not in sys.path:
    sys.path.insert(0, path)

from app import app as application
