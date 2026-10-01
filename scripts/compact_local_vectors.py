"""Merge small LanceDB fragments; retain old versions and verify every row."""
from datetime import timedelta
import json
from pathlib import Path
import lancedb

ROOT = Path(__file__).resolve().parents[1]


def fragment_count(stats):
    fragments = stats["fragment_stats"] if isinstance(stats, dict) else stats.fragment_stats
    return fragments["num_fragments"] if isinstance(fragments, dict) else fragments.num_fragments


def main():
    db_path = (ROOT / "output/local/lancedb").resolve()
    if not db_path.is_relative_to(ROOT.resolve()) or not db_path.is_dir():
        raise SystemExit("Expected the existing local LanceDB inside the project")
    db = lancedb.connect(str(db_path))
    results = []
    for name in ["text_unit_text", "entity_description", "community_full_content"]:
        table = db.open_table(name)
        before_version = table.version
        before_stats = table.stats()
        before = table.to_arrow().sort_by([("id", "ascending")]).combine_chunks()
        old_versions = {v["version"] for v in table.list_versions()}
        print(f"{name}: {fragment_count(before_stats)} fragments, {before.num_rows} rows", flush=True)
        # Retain a century of history: these project tables were created in 2026.
        # Do not delete unverified files or retrain/create a vector index.
        table.optimize(cleanup_older_than=timedelta(days=36500), delete_unverified=False, retrain=False)
        after = table.to_arrow().sort_by([("id", "ascending")]).combine_chunks()
        if not before.equals(after):
            table.restore(before_version)
            raise RuntimeError(f"Row comparison failed for {name}; restored version {before_version}")
        assert old_versions.issubset({v["version"] for v in table.list_versions()}), "Old versions must be retained"
        result = {"table": name, "rows": after.num_rows, "previous_version": before_version,
                  "version": table.version, "fragments_before": fragment_count(before_stats),
                  "fragments_after": fragment_count(table.stats()), "data_equal": True}
        results.append(result)
        print(json.dumps(result), flush=True)
        (ROOT / "logs/vector-compaction.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
