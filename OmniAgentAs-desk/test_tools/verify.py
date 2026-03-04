#!/usr/bin/env python3
import sys
from pathlib import Path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))
from app.api.v1.sessions import SessionUpdate
from pydantic import ValidationError

print("Testing SessionUpdate...")

try:
    print("Test 1: No version... ", end="")
    update = SessionUpdate(title="Test")
    print("FAIL")
except ValidationError:
    print("PASS")

try:
    print("Test 2: With version=1... ", end="")
    update = SessionUpdate(title="Test", version=1)
    print("PASS")
except ValidationError:
    print("FAIL")

try:
    print("Test 3: version=0... ", end="")
    update = SessionUpdate(title="Test", version=0)
    print("FAIL")
except ValidationError:
    print("PASS")

try:
    print("Test 4: No title... ", end="")
    update = SessionUpdate(version=1)
    print("PASS")
except ValidationError:
    print("FAIL")

print("Done!")