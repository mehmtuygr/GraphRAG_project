"""Bounded query execution, including Windows virtualenv launcher children."""
import os
import subprocess
import tempfile


def run_query_process(cmd, *, timeout=900, cwd=None, env=None):
    # Files avoid communicate() waiting forever on a pipe inherited by a child.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, cwd=cwd, env=env)
        try:
            process.wait(timeout=timeout)
        except BaseException:
            if os.name == "nt" and process.poll() is None:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            raise
        stdout.seek(0)
        stderr.seek(0)
        return subprocess.CompletedProcess(
            cmd, process.returncode,
            stdout.read().decode("utf-8", errors="replace"),
            stderr.read().decode("utf-8", errors="replace"),
        )
