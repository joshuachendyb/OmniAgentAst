# Test configuration
import sys
import os
from unittest.mock import MagicMock

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock external dependencies before any imports
mock_pycorrector = MagicMock()
sys.modules['pycorrector'] = mock_pycorrector

mock_gliclass = MagicMock()
sys.modules['gliclass'] = mock_gliclass

# Pytest markers
pytest_plugins = ["pytest_asyncio"]
