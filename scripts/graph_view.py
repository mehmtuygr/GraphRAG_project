"""Read-only, offline exploration of the saved GraphRAG graph."""
import html
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load_graph():
    base = ROOT / "output/local"
    return tuple(pd.read_parquet(base / f"{name}.parquet") for name in
                 ("entities", "relationships", "communities"))


def find_entities(term):
    entities, _, _ = load_graph()
    names = entities["title"].fillna("").astype(str)
    matches = entities[names.str.contains((term or "").strip(), case=False, regex=False)]
    matches = matches.sort_values("degree", ascending=False).head(60)
    return matches["title"].tolist()


def build_graph(title, hops=1, limit=35):
    entities, relationships, communities = load_graph()
    by_name = {str(row["title"]): row for row in entities.to_dict("records")}
    if title not in by_name:
        raise ValueError("Önce bir kavram arayıp listeden seç.")
    limit = max(5, min(80, int(limit)))
    selected, frontier = {title}, {title}
    ranked = relationships.sort_values("weight", ascending=False).to_dict("records")
    for _ in range(max(1, min(2, int(hops)))):
        additions = []
        for edge in ranked:
            a, b = str(edge["source"]), str(edge["target"])
            if a in frontier or b in frontier:
                for name in (a, b):
                    if name in by_name and name not in selected and name not in additions:
                        additions.append(name)
        frontier = set(additions[:max(0, limit - len(selected))])
        selected.update(frontier)
    groups = {}
    for row in communities[communities["level"] == 0].to_dict("records"):
        for entity_id in row["entity_ids"]:
            groups[str(entity_id)] = str(row["community"])
    nodes = []
    for name in [title] + sorted(selected - {title}):
        row = by_name[name]
        nodes.append({"name": name, "description": str(row.get("description", "")),
                      "type": str(row.get("type", "")), "group": groups.get(str(row["id"]), "?"),
                      "id": str(row["human_readable_id"])})
    edges = [{"source": str(e["source"]), "target": str(e["target"]),
              "description": str(e.get("description", "")), "weight": float(e["weight"]),
              "id": str(e["human_readable_id"])} for e in ranked
             if str(e["source"]) in selected and str(e["target"]) in selected]
    return {"nodes": nodes, "edges": edges}


def render_graph(title, hops, limit):
    try:
        data = build_graph(title, hops, limit)
    except (OSError, ValueError, KeyError) as exc:
        return f"<p>{html.escape(str(exc))}</p>"
    template = (ROOT / "scripts/graph_view.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    document = template.replace("/*GRAPH_DATA*/", payload)
    return '<iframe title="Kavram ilişkileri" sandbox="allow-scripts" style="width:100%;height:660px;border:0;border-radius:14px" srcdoc="' + html.escape(document, quote=True) + '"></iframe>'
