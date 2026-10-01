"""Offline configuration validation, or a small local-only Ollama smoke test."""
import argparse
import json
import socket
import os
from urllib.request import build_opener, ProxyHandler, Request
from run_local import validate_local_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    cfg = validate_local_config()
    if not args.smoke:
        def blocked(*a, **kw):
            raise RuntimeError("Network disabled during offline validation")
        socket.socket.connect = blocked
        socket.socket.connect_ex = blocked
        socket.create_connection = blocked
        from graphrag.config.models.graph_rag_config import GraphRagConfig
        from string import Template
        import yaml
        parsed = yaml.safe_load(Template(yaml.safe_dump(cfg)).substitute({}))
        GraphRagConfig(**parsed)
        print("PASS: local endpoints, YAML interpolation and GraphRAG schema. No API requests.")
        return
    # Ignore system HTTP proxies; contact only the loopback Ollama endpoint.
    opener = build_opener(ProxyHandler({}))
    def post(path, data):
        request = Request("http://127.0.0.1:11434" + path,
                          data=json.dumps(data).encode(),
                          headers={"Content-Type": "application/json"})
        with opener.open(request, timeout=600) as response:
            return json.load(response)
    response = post("/v1/chat/completions", {
        "model": "udl-qwen-local:latest", "temperature": 0,
        "max_tokens": 100, "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": 'Return JSON with key status and value ok.'}]})
    assert json.loads(response["choices"][0]["message"]["content"])["status"] == "ok"
    response = post("/v1/embeddings", {"model": "embeddinggemma:latest", "input": ["gradient descent"]})
    assert len(response["data"][0]["embedding"]) == 768
    print("PASS: local JSON completion and 768-dimensional embedding.")
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    from graphrag_llm.config.model_config import ModelConfig
    from graphrag_llm.completion import create_completion
    from graphrag_llm.embedding import create_embedding
    from pydantic import BaseModel
    import asyncio

    class Status(BaseModel):
        status: str

    async def check_adapters():
        completion = create_completion(ModelConfig(**cfg["completion_models"]["index_model"]))
        result = await completion.completion_async(
            messages='Return JSON with status set to ok.', response_format=Status)
        assert result.formatted_response.status == "ok"
        embedding = create_embedding(ModelConfig(**cfg["embedding_models"]["default_embedding_model"]))
        result = await embedding.embedding_async(input=["gradient descent"])
        assert len(result.first_embedding) == 768
    asyncio.run(check_adapters())
    print("PASS: GraphRAG adapters support structured JSON and local embeddings.")


if __name__ == "__main__":
    main()
