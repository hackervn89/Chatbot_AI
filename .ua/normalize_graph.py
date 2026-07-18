# -*- coding: utf-8 -*-
"""Chuẩn hóa knowledge-graph.json của UnderstandAnything."""
import json
import os
import datetime

UA_DIR = os.path.dirname(os.path.abspath(__file__))
ABS_PREFIX = "g:/My Drive/Chuyên viên ảo/"

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def dump(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def norm_id(s):
    return s.replace(ABS_PREFIX, "") if isinstance(s, str) else s

def derive_name(node):
    if node.get("name"):
        return node["name"]
    if node.get("label"):
        return node["label"]
    nid = node.get("id", "")
    return nid.split(":")[-1] if nid else nid

def derive_path(node_id, file_paths):
    for p in file_paths:
        if p in node_id:
            return p
    return None

def main():
    # Load scan result
    scan = load(os.path.join(UA_DIR, "intermediate", "scan-result.json"))
    file_paths = [f["path"] for f in scan.get("files", [])]
    file_paths.sort(key=len, reverse=True)
    import_map = scan.get("importMap", {})
    
    # Load main graph
    graph_path = os.path.join(UA_DIR, "knowledge-graph.json")
    d = load(graph_path)
    nodes = d.get("nodes", [])
    edges = d.get("edges", [])
    
    # Normalize nodes
    for n in nodes:
        n["id"] = norm_id(n["id"])
        if not n.get("path"):
            n["path"] = derive_path(n["id"], file_paths)
        n["name"] = derive_name(n)
        if not n.get("label"):
            n["label"] = n["name"]
    
    # Normalize edges
    seen = set()
    new_edges = []
    for e in edges:
        e["source"] = norm_id(e["source"])
        e["target"] = norm_id(e["target"])
        key = (e["source"], e["target"], e.get("type"))
        if key not in seen:
            seen.add(key)
            new_edges.append(e)
    
    # Add import edges
    node_by_path = {}
    for n in nodes:
        p = n.get("path")
        if p and n["id"].endswith(p):
            node_by_path.setdefault(p, n["id"])
    
    for src_path, deps in import_map.items():
        src_node = node_by_path.get(src_path)
        if not src_node:
            continue
        for dep_path in deps:
            tgt_node = node_by_path.get(dep_path)
            if not tgt_node:
                continue
            key = (src_node, tgt_node, "imports")
            if key not in seen:
                seen.add(key)
                new_edges.append({
                    "source": src_node,
                    "target": tgt_node,
                    "type": "imports",
                    "direction": "forward"
                })
    
    # Normalize layers/tour
    if "layers" in d:
        for layer in d["layers"]:
            layer["nodeIds"] = [norm_id(x) for x in layer.get("nodeIds", [])]
    if "tour" in d:
        for step in d["tour"]:
            step["nodeIds"] = [norm_id(x) for x in step.get("nodeIds", [])]
    
    # Đồng bộ ID ở các artifact trung gian để lần chạy sau không tái sinh
    # tham chiếu đường dẫn tuyệt đối Windows.
    for artifact in ("layers.json", "tour.json"):
        artifact_path = os.path.join(UA_DIR, "intermediate", artifact)
        artifact_data = load(artifact_path)
        for item in artifact_data:
            item["nodeIds"] = [norm_id(x) for x in item.get("nodeIds", [])]
        dump(artifact_path, artifact_data)

    # Update metadata
    proj = d.setdefault("project", {})
    proj["normalizedAt"] = datetime.datetime.now(datetime.UTC).isoformat()
    proj["nodeCount"] = len(nodes)
    proj["edgeCount"] = len(new_edges)
    
    d["nodes"] = nodes
    d["edges"] = new_edges
    dump(graph_path, d)
    
    # Validate
    node_ids = {n["id"] for n in nodes}
    issues = []
    for i, n in enumerate(nodes):
        if not n.get("name"):
            issues.append(f"Node[{i}] '{n.get('id')}' missing name")
        if ABS_PREFIX in n["id"]:
            issues.append(f"Absolute path in node[{i}]: {n['id']}")
    for e in new_edges:
        if e["source"] not in node_ids or e["target"] not in node_ids:
            issues.append(f"Dangling edge {e['source']} -> {e['target']}")
    
    connected = set()
    for e in new_edges:
        connected.add(e["source"])
        connected.add(e["target"])
    orphans = [n["id"] for n in nodes if n["id"] not in connected]
    
    review = {
        "issues": issues,
        "warnings": [],
        "stats": {
            "totalNodes": len(nodes),
            "totalEdges": len(new_edges),
            "totalLayers": len(d.get("layers", [])),
            "tourSteps": len(d.get("tour", [])),
            "danglingEdges": sum(1 for e in new_edges if e["source"] not in node_ids or e["target"] not in node_ids),
            "orphanNodes": len(orphans),
            "nodesMissingName": sum(1 for n in nodes if not n.get("name")),
            "nodesMissingPath": sum(1 for n in nodes if not n.get("path") and n.get("type") != "project")
        }
    }
    dump(os.path.join(UA_DIR, "intermediate", "review.json"), review)
    
    # Update meta
    meta = {
        "lastAnalyzedAt": scan.get("analyzedAt", ""),
        "normalizedAt": proj["normalizedAt"],
        "gitCommitHash": proj.get("gitCommitHash", ""),
        "version": "1.0.0",
        "nodeCount": len(nodes),
        "edgeCount": len(new_edges)
    }
    dump(os.path.join(UA_DIR, "meta.json"), meta)
    
    print(json.dumps(review["stats"], ensure_ascii=False, indent=2))
    if issues:
        print(f"\nISSUES ({len(issues)}):")
        for x in issues[:10]:
            print("  -", x)
    else:
        print("\nNo blocking issues.")

if __name__ == "__main__":
    main()
