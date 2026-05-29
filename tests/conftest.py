"""
tests/conftest.py
Pytest configuration — runs before any test file.
Sets environment variables needed for testing.
"""
import os
# Disable rate limiting during tests so all tests can run freely
os.environ["RATE_LIMIT_REQUESTS"] = "1000"
os.environ["RATE_LIMIT_WINDOW"]   = "1"
