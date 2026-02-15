# Test configuration
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Pytest markers
pytest_plugins = ["pytest_asyncio"]
