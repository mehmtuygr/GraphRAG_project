"""Run GraphRAG only with the project's approved local Ollama models."""
from pathlib import Path
import os
import runpy
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate_local_config(root=ROOT):
    cfg = yaml.safe_load((root / "settings.yaml").read_text(encoding="utf-8"))
    for section, allowed in [("completion_models", "udl-qwen-local:latest"),
                             ("embedding_models", "embeddinggemma:latest")]:
        models = cfg.get(section, {})
        if not models:
            raise ValueError("Local model configuration missing; run scripts/setup_graphrag.py")
        for model in models.values():
            if (model.get("api_base") != "http://127.0.0.1:11434/v1"
                    or model.get("model") != allowed
                    or model.get("api_key") != "ollama-local-only"
                    or model.get("model_provider") != "openai"
                    or model.get("type") != "litellm"
                    or set(model.get("call_args", {})) - {"timeout", "temperature", "max_tokens"}):
                raise ValueError("Non-local model configuration blocked; run scripts/setup_graphrag.py")
    return cfg


def main():
    validate_local_config()
    args = sys.argv[1:]
    if not args or args[0] not in {"index", "query"}:
        raise SystemExit("Usage: python scripts/run_local.py index [--dry-run --skip-validation] | query QUESTION --method local")
    if any(a.split('=')[0] in {"--root", "-r", "--config", "-c"} for a in args):
        raise SystemExit("The local runner always uses this project's settings.yaml")
    if args[0] == "query" and not any(a.split('=')[0] == "--community-level" for a in args):
        # Level 0 uses broad communities, avoiding hundreds of report map calls.
        args += ["--community-level", "0"]
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("OPENAI_", "GRAPHRAG_API_KEY", "AZURE_OPENAI_")):
            env.pop(key)
    env["OLLAMA_NO_CLOUD"] = "1"
    env["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    # Run in this process: a wrapper subprocess would leave GraphRAG running
    # with inherited stdout pipes when the UI terminates the wrapper on timeout.
    os.environ.clear()
    os.environ.update(env)
    os.chdir(ROOT)
    method = None
    for i, arg in enumerate(args):
        if arg == "--method" and i + 1 < len(args):
            method = args[i + 1]
        elif arg.startswith("--method="):
            method = arg.split("=", 1)[1]
    full_reports = "--full-reports" in args
    if full_reports:
        args.remove("--full-reports")
    if args[0] == "query" and method == "global" and not full_reports:
        from global_query import main as global_query_main
        global_query_main(args[1:], ROOT)
        return
    sys.argv = ["graphrag", *args, "--root", str(ROOT)]
    runpy.run_module("graphrag", run_name="__main__")


if __name__ == "__main__":
    main()
