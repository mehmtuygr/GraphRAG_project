"""Global GraphRAG over community summaries, without changing the saved index."""
import argparse
import asyncio
from pathlib import Path
import os
import sys


def main(args, root):
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--method", choices=["global"], default="global")
    parser.add_argument("--community-level", type=int, default=0)
    parser.add_argument("--response-type", default="Multiple Paragraphs")
    options = parser.parse_args(args)
    import pandas as pd
    from graphrag.config.load_config import load_config
    from graphrag.callbacks.query_callbacks import QueryCallbacks
    from graphrag.api import global_search

    class Progress(QueryCallbacks):
        def report(self, text):
            print(text, file=sys.stderr, flush=True)
            path = os.environ.get("UDL_QUERY_PROGRESS_FILE")
            if path:
                Path(path).write_text(text, encoding="utf-8")

        def on_map_response_start(self, contexts):
            self.report(f"Global: topluluk özetleri {len(contexts)} grup halinde taranıyor.")

        def on_map_response_end(self, outputs):
            self.report(f"Global: {len(outputs)} grup tamamlandı; bulgular birleştiriliyor.")

        def on_reduce_response_start(self, context):
            self.report("Global: son yanıt oluşturuluyor.")

    config = load_config(root_dir=root)
    output = Path(config.output_storage.base_dir)
    if not output.is_absolute():
        output = root / output
    reports = pd.read_parquet(output / "community_reports.parquet")
    # Preserve all report IDs, hierarchy and citations. Replace only the in-memory
    # text supplied to GlobalSearch; no parquet or embedding files are modified.
    summaries = reports["summary"].fillna("").astype(str)
    reports["full_content"] = summaries.where(summaries.str.strip().ne(""), reports["full_content"])
    response, _ = asyncio.run(global_search(
        config=config, entities=pd.read_parquet(output / "entities.parquet"),
        communities=pd.read_parquet(output / "communities.parquet"), community_reports=reports,
        community_level=options.community_level, dynamic_community_selection=False,
        response_type=options.response_type, query=options.query, callbacks=[Progress()],
    ))
    print(response)
