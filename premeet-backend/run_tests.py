"""Run all regressions against temporary databases, never local user data."""
import gc
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server

if __name__=='__main__':
    original=server.DB
    with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{'DEEPSEEK_API_KEY':''}):
        server.DB=Path(folder)/'regressions.sqlite3'
        suite=unittest.defaultTestLoader.discover(str(server.ROOT),pattern='test_*.py')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        server.DB=original
        gc.collect()
    raise SystemExit(not result.wasSuccessful())
