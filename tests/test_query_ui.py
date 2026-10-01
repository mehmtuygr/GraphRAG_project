"""Offline checks for Gradio query wiring and local command arguments."""
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

result = subprocess.CompletedProcess([], 0, stdout="Yerel yanıt: öğrenme.", stderr="")
with patch("app.run_query_process", return_value=result) as run:
    updates = list(app.graphrag_ask("Soru", "global", "Single Sentence", 0, False))
    assert updates[-1] == result.stdout
    assert len(updates) >= 2
    args = run.call_args.args[0]
    assert args[args.index("--community-level") + 1] == "0"
    assert "--full-reports" not in args
    assert run.call_args.kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
    list(app.graphrag_ask("Soru", "global", "Single Sentence", 1, True))
    assert "--full-reports" in run.call_args.args[0]
    list(app.graphrag_ask("Soru", "drift", "Single Sentence", 0, True))
    assert "--full-reports" not in run.call_args.args[0]

with patch("app.run_query_process", side_effect=subprocess.TimeoutExpired("test", 900)):
    assert "15 dakika" in list(app.graphrag_ask("Soru", "global", "Single Sentence"))[-1]
with patch("app.run_query_process") as run:
    assert len(list(app.graphrag_ask("", "local", "Single Sentence"))) == 1
    run.assert_not_called()
print("PASS: UI construction, global/full-report selection, DRIFT selection, UTF-8, empty input and timeout feedback. No model requests.")
