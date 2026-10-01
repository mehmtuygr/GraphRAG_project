from __future__ import annotations
import sys
import subprocess
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
# Local model names deliberately do not inherit the old OpenAI .env settings.
INDEX_MODEL = QUERY_MODEL = "udl-qwen-local:latest"
EMBED_MODEL = "embeddinggemma:latest"


def deep_set(d: dict, path: list[str], value):
    cur = d
    for key in path[:-1]:
        cur = cur.setdefault(key, {})
    cur[path[-1]] = value


def main():
    path = ROOT / "settings.yaml"
    if not path.exists():
        # Init in a temporary directory so the user's .env is never overwritten.
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, "-m", "graphrag", "init", "--root", tmp], check=True)
            shutil.copyfile(Path(tmp) / "settings.yaml", path)
            shutil.copytree(Path(tmp) / "prompts", ROOT / "prompts", dirs_exist_ok=True)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def model(name, embedding=False):
        return {
            "type": "litellm", "model_provider": "openai",
            "model": name, "api_base": "http://127.0.0.1:11434/v1",
            "auth_method": "api_key", "api_key": "ollama-local-only",
            "call_args": {"timeout": 600} if embedding else {
                "timeout": 600, "temperature": 0, "max_tokens": 1000},
            "retry": {"type": "exponential_backoff", "max_retries": 2, "base_delay": 2.0},
        }
    # 'openai' selects the compatible protocol, not OpenAI's hosted service.
    cfg["completion_models"] = {"index_model": model(INDEX_MODEL), "query_model": model(QUERY_MODEL)}
    # Extraction and JSON reports need more output space than a short answer.
    cfg["completion_models"]["index_model"]["call_args"]["max_tokens"] = 1600
    cfg["embedding_models"] = {"default_embedding_model": model(EMBED_MODEL, True)}
    cfg["concurrent_requests"] = 1
    # New storage avoids mixing local vectors with any previous OpenAI index.
    cfg["output_storage"] = {"type": "file", "base_dir": "output/local"}
    cfg["cache"] = {"type": "json", "storage": {"type": "file", "base_dir": "cache/local"}}
    cfg["vector_store"] = {"type": "lancedb", "db_uri": "output/local/lancedb", "vector_size": 768}

    # Page-aware files + moderate chunking: enough context for textbook concepts without
    # making each extraction call huge.
    deep_set(cfg, ["input", "type"], "text")
    # GraphRAG expands environment variables with string.Template before YAML parsing.
    # Escape the regex end anchor so it becomes a literal '$' after expansion.
    deep_set(cfg, ["input", "file_pattern"], r".*\.txt$$")
    deep_set(cfg, ["chunking", "type"], "tokens")
    deep_set(cfg, ["chunking", "size"], 600)
    deep_set(cfg, ["chunking", "overlap"], 80)
    deep_set(cfg, ["chunking", "encoding_model"], "o200k_base")

    # Local extraction with short chunks for the laptop GPU.
    deep_set(cfg, ["extract_graph", "completion_model_id"], "index_model")
    deep_set(cfg, ["extract_graph", "entity_types"], [
        "concept", "model", "method", "task", "metric", "person"
    ])
    # Gleanings are extra extraction passes; 0 is the main cost-saving choice.
    deep_set(cfg, ["extract_graph", "max_gleanings"], 0)
    deep_set(cfg, ["summarize_descriptions", "completion_model_id"], "index_model")
    deep_set(cfg, ["summarize_descriptions", "max_length"], 350)
    deep_set(cfg, ["community_reports", "completion_model_id"], "index_model")
    deep_set(cfg, ["community_reports", "max_length"], 500)
    deep_set(cfg, ["extract_claims", "enabled"], False)
    deep_set(cfg, ["embed_text", "embedding_model_id"], "default_embedding_model")
    deep_set(cfg, ["embed_text", "names"], ["text_unit_text", "entity_description", "community_full_content"])

    # Use the same local model for every search method.
    for section in ["local_search", "global_search", "drift_search", "basic_search"]:
        deep_set(cfg, [section, "completion_model_id"], "query_model")
    for section in ["local_search", "drift_search", "basic_search"]:
        deep_set(cfg, [section, "embedding_model_id"], "default_embedding_model")

    deep_set(cfg, ["local_search", "max_context_tokens"], 1800)
    deep_set(cfg, ["local_search", "top_k_entities"], 12)
    deep_set(cfg, ["local_search", "top_k_relationships"], 15)
    deep_set(cfg, ["basic_search", "k"], 8)
    deep_set(cfg, ["basic_search", "max_context_tokens"], 1800)
    deep_set(cfg, ["drift_search", "data_max_tokens"], 1800)
    deep_set(cfg, ["global_search", "data_max_tokens"], 1800)

    deep_set(cfg, ["extract_claims", "completion_model_id"], "index_model")
    deep_set(cfg, ["summarize_descriptions", "max_input_tokens"], 1600)
    deep_set(cfg, ["community_reports", "max_input_length"], 1600)
    deep_set(cfg, ["embed_text", "batch_size"], 1)
    deep_set(cfg, ["embed_text", "batch_max_tokens"], 1200)
    deep_set(cfg, ["global_search", "max_context_tokens"], 1800)
    deep_set(cfg, ["global_search", "map_max_length"], 300)
    deep_set(cfg, ["global_search", "reduce_max_length"], 500)
    deep_set(cfg, ["drift_search", "concurrency"], 1)
    deep_set(cfg, ["drift_search", "drift_k_followups"], 2)
    deep_set(cfg, ["drift_search", "primer_folds"], 1)
    deep_set(cfg, ["drift_search", "n_depth"], 2)
    deep_set(cfg, ["drift_search", "prompt"], "prompts/drift_local_compact.txt")
    deep_set(cfg, ["drift_search", "reduce_prompt"], "prompts/drift_reduce_compact.txt")
    deep_set(cfg, ["drift_search", "local_search_max_data_tokens"], 3200)
    deep_set(cfg, ["drift_search", "local_search_text_unit_prop"], 0.5)
    deep_set(cfg, ["drift_search", "local_search_community_prop"], 0.0)
    deep_set(cfg, ["drift_search", "local_search_top_k_mapped_entities"], 6)
    deep_set(cfg, ["drift_search", "local_search_top_k_relationships"], 8)
    deep_set(cfg, ["drift_search", "primer_llm_max_tokens"], 1000)
    deep_set(cfg, ["drift_search", "local_search_llm_max_gen_tokens"], 1000)
    deep_set(cfg, ["drift_search", "reduce_max_tokens"], 1000)

    # GraphML export is not used by the application.
    deep_set(cfg, ["snapshots", "graphml"], False)
    deep_set(cfg, ["snapshots", "raw_graph"], False)

    path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"OK: wrote local-only {path}")
    print(f"Index model={INDEX_MODEL} | Query model={QUERY_MODEL} | Embedding={EMBED_MODEL}")


if __name__ == "__main__":
    main()
