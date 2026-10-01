"""Small local integration test; never indexes the full book."""
from pathlib import Path
from datetime import datetime
import os
import subprocess
import sys
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_local import ROOT, validate_local_config


def main():
    cfg = validate_local_config()
    target = ROOT / "output" / ("local-smoke-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    target.mkdir(parents=True)
    (target / "input").mkdir()
    (target / "input" / "sample.txt").write_text(
        "Gradient descent minimizes a loss function by updating neural network weights "
        "in the direction opposite to the gradient. Backpropagation computes these "
        "gradients efficiently using the chain rule. The learning rate controls the "
        "size of each gradient descent update. Stochastic gradient descent estimates "
        "the gradient using minibatches of training examples. Adam combines momentum "
        "with adaptive learning rates to optimize neural network weights. Residual "
        "connections add a layer's input to its output and help gradients propagate "
        "through deep neural networks. Regularization reduces overfitting. Weight "
        "decay penalizes large weights, while dropout randomly masks activations "
        "during training. Validation data helps select the regularization strength.",
        encoding="utf-8",
    )
    cfg["input_storage"] = {"type": "file", "base_dir": "input"}
    cfg["output_storage"] = {"type": "file", "base_dir": "output"}
    cfg["cache"]["storage"]["base_dir"] = "cache"
    cfg["vector_store"]["db_uri"] = "output/lancedb"
    for section in cfg.values():
        if isinstance(section, dict):
            for key, value in list(section.items()):
                if "prompt" in key and isinstance(value, str) and value.startswith("prompts/"):
                    section[key] = str(ROOT / value)
    (target / "settings.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("OPENAI_", "GRAPHRAG_API_KEY", "AZURE_OPENAI_")):
            env.pop(key)
    env.update(LITELLM_LOCAL_MODEL_COST_MAP="True", NO_PROXY="127.0.0.1,localhost")
    for args in [["index", "--skip-validation"],
                 ["query", "How does backpropagation help gradient descent?", "--method", "local"]]:
        subprocess.run([sys.executable, "-m", "graphrag", *args, "--root", str(target)],
                       cwd=target, env=env, check=True, timeout=1200)
    import pandas as pd
    for name in ["entities", "relationships", "community_reports"]:
        table = pd.read_parquet(target / "output" / (name + ".parquet"))
        assert len(table) > 0, f"No {name} generated"
        print(f"{name}: {len(table)} rows")
    print("PASS: small local index and local query. Artifacts:", target)


if __name__ == "__main__":
    main()
