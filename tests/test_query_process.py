"""Regression: timeout must kill a virtualenv process and its inherited child."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.query_process import run_query_process

env = dict(os.environ, PYTHONIOENCODING="utf-8")
result = run_query_process([sys.executable, "-c", "print(chr(351))"], timeout=20, env=env)
assert result.returncode == 0 and result.stdout.strip() == chr(351)
with tempfile.TemporaryDirectory(prefix="udl-timeout-test-") as tmp:
    marker = str(Path(tmp) / "child-finished.txt")
    child = "import time,pathlib; time.sleep(5); pathlib.Path(" + repr(marker) + ").write_text('bad')"
    parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); print('started',flush=True); time.sleep(60)"
    start = time.monotonic()
    try:
        run_query_process([sys.executable, "-c", parent], timeout=2, env=env)
        raise AssertionError("Expected timeout")
    except subprocess.TimeoutExpired:
        assert time.monotonic() - start < 10
    time.sleep(6)
    assert not Path(marker).exists(), "Child outlived timeout"
print("PASS: UTF-8 output and timeout terminates the virtualenv launcher/child tree. No model calls.")
