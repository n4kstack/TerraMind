"""
Auto-generated project architecture snapshot service.

Builds a read-only architecture graph by scanning project source files,
extracting modules, imports, data/control flow hints, API boundaries,
and execution mode pathways.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[3]

LAYER_COLORS = {
    "ui": "#38bdf8",
    "business": "#22c55e",
    "data": "#f59e0b",
    "external": "#94a3b8",
}

SCAN_ROOTS = [
    "frontend/src",
    "backend",
    "ml",
    "models",
    "graph_rag",
    "federated",
    "core",
    "routers",
    "services",
    "schemas",
    "meta_learner",
]

EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    "dist",
    "logs",
    "artifacts",
    "cache",
    "results",
    ".pytest_cache",
    ".mypy_cache",
}

CODE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}

PREFIX_BY_ROUTE_FILE = {
    "backend/app/api/v1/advisor.py": "/api/v1/advisor",
    "backend/app/api/v1/monitor.py": "/api/v1/monitor",
    "backend/app/api/v1/diagnosis.py": "/api/v1/diagnosis",
    "backend/app/api/v1/chatbot.py": "/api/v1/chatbot",
    "backend/app/api/v1/graph_rag.py": "/api/v1/graph-rag",
    "backend/app/api/v1/architecture.py": "/api/v1/architecture",
}

_CACHE: Dict[str, Any] = {
    "fingerprint": None,
    "snapshot": None,
    "built_at": 0,
}


def _to_rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _collect_code_files() -> List[Path]:
    files: List[Path] = []
    for root_rel in SCAN_ROOTS:
        root = PROJECT_ROOT / root_rel
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in CODE_EXTS:
                continue
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def _fingerprint(files: List[Path]) -> float:
    if not files:
        return 0.0
    return max(path.stat().st_mtime for path in files)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _classify(rel_path: str) -> Tuple[str, str]:
    p = rel_path

    if p.startswith("frontend/src/pages/"):
        return "ui", "page"
    if p.startswith("frontend/src/components/forms/"):
        return "ui", "form_component"
    if p.startswith("frontend/src/components/results/"):
        return "ui", "result_component"
    if p.startswith("frontend/src/components/"):
        return "ui", "component"
    if p.startswith("frontend/src/services/"):
        return "business", "frontend_service"
    if p.startswith("frontend/src/"):
        return "ui", "frontend_module"

    if p.startswith("backend/app/api/") or p.startswith("backend/api/"):
        return "business", "api_router"
    if p.startswith("backend/app/services/") or p.startswith("backend/services/"):
        return "business", "service"
    if p.startswith("routers/"):
        return "business", "router"

    if p.startswith("backend/models/"):
        return "data", "ml_model"
    if p.startswith("ml/"):
        return "data", "ml_pipeline"
    if p.startswith("models/"):
        return "data", "model_module"
    if p.startswith("graph_rag/"):
        return "data", "graph_rag_engine"
    if p.startswith("federated/"):
        return "data", "federated_module"
    if p.startswith("backend/app/schemas/") or p.startswith("backend/schemas/") or p.startswith("schemas/"):
        return "data", "schema"

    if p.startswith("backend/app/chatbot/"):
        return "data", "rag_pipeline"

    return "business", "module"


def _label_for(rel_path: str) -> str:
    name = Path(rel_path).stem
    if name == "__init__":
        return f"{Path(rel_path).parent.name}/__init__"
    return name


def _extract_js_imports(content: str) -> List[Tuple[List[str], str]]:
    imports: List[Tuple[List[str], str]] = []

    for match in re.finditer(r"import\s+([^;]+?)\s+from\s+['\"]([^'\"]+)['\"]", content):
        clause = match.group(1).strip()
        spec = match.group(2).strip()
        names: List[str] = []

        if clause.startswith("{") and clause.endswith("}"):
            inner = clause[1:-1]
            names = [n.strip().split(" as ")[0].strip() for n in inner.split(",") if n.strip()]
        elif "," in clause:
            default_part, named_part = clause.split(",", 1)
            names.append(default_part.strip())
            named_match = re.search(r"\{([^}]+)\}", named_part)
            if named_match:
                names.extend(
                    n.strip().split(" as ")[0].strip()
                    for n in named_match.group(1).split(",")
                    if n.strip()
                )
        else:
            names = [clause.strip()]

        imports.append((names, spec))

    for match in re.finditer(r"import\(\s*['\"]([^'\"]+)['\"]\s*\)", content):
        imports.append(([], match.group(1).strip()))

    for match in re.finditer(r"import\s+['\"]([^'\"]+)['\"]", content):
        imports.append(([], match.group(1).strip()))

    return imports


def _extract_py_imports(content: str) -> List[str]:
    modules: List[str] = []
    for match in re.finditer(r"^\s*from\s+([\.\w]+)\s+import\s+", content, flags=re.M):
        modules.append(match.group(1).strip())
    for match in re.finditer(r"^\s*import\s+([\w\.,\s]+)", content, flags=re.M):
        clause = match.group(1)
        for item in clause.split(","):
            name = item.strip().split(" as ")[0].strip()
            if name:
                modules.append(name)
    return modules


def _extract_exports(content: str, suffix: str) -> List[str]:
    exports: List[str] = []

    if suffix in JS_EXTS:
        for match in re.finditer(r"export\s+(?:default\s+)?(?:function|class|const|let|var)\s+([A-Za-z_][\w]*)", content):
            exports.append(match.group(1))
        for match in re.finditer(r"export\s*\{([^}]+)\}", content):
            for part in match.group(1).split(","):
                name = part.strip().split(" as ")[0].strip()
                if name:
                    exports.append(name)
    else:
        for match in re.finditer(r"^\s*(?:async\s+)?def\s+([A-Za-z_][\w]*)\s*\(", content, flags=re.M):
            exports.append(match.group(1))
        for match in re.finditer(r"^\s*class\s+([A-Za-z_][\w]*)\s*[:\(]", content, flags=re.M):
            exports.append(match.group(1))

    # Keep ordering stable while deduplicating.
    seen = set()
    ordered: List[str] = []
    for item in exports:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered[:20]


def _extract_api_calls(content: str) -> List[str]:
    calls: List[str] = []

    for match in re.finditer(r"fetch\(([^\)]*)\)", content):
        calls.append(match.group(1).strip()[:120])

    for match in re.finditer(r"https?://[^\s'\"\)]+", content):
        calls.append(match.group(0).strip())

    for match in re.finditer(r"/api(?:/v\d+)?/[A-Za-z0-9_\-/{}/]+", content):
        calls.append(match.group(0).strip())

    for match in re.finditer(r"\b(?:get|post|put|delete|patch)\(\s*['\"](https?://[^'\"]+)['\"]", content):
        calls.append(match.group(1).strip())

    seen = set()
    ordered: List[str] = []
    for item in calls:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered[:20]


def _extract_react_metadata(content: str) -> Dict[str, Any]:
    props: List[str] = []

    fn_match = re.search(r"function\s+[A-Za-z_][\w]*\s*\(\s*\{([^}]*)\}\s*\)", content, flags=re.S)
    if not fn_match:
        fn_match = re.search(r"const\s+[A-Za-z_][\w]*\s*=\s*\(\s*\{([^}]*)\}\s*\)\s*=>", content, flags=re.S)

    if fn_match:
        for token in fn_match.group(1).split(","):
            candidate = token.strip()
            if not candidate:
                continue
            candidate = candidate.split("=")[0].strip()
            candidate = candidate.split(":")[-1].strip()
            if candidate:
                props.append(candidate)

    state_count = len(re.findall(r"\buseState\s*\(", content))
    event_props = [p for p in props if p.startswith("on")]

    return {
        "props": props[:30],
        "state_count": state_count,
        "event_props": event_props[:20],
    }


def _extract_jsx_usages(content: str, imported_names: List[str]) -> Dict[str, List[str]]:
    usages: Dict[str, List[str]] = {}

    for name in imported_names:
        if not name or name[0].islower():
            continue
        if not re.search(rf"<{re.escape(name)}\b", content):
            continue

        prop_names: set[str] = set()
        for tag_match in re.finditer(rf"<{re.escape(name)}\s+([^>]+?)>", content, flags=re.S):
            attrs = tag_match.group(1)
            for prop_match in re.finditer(r"([A-Za-z_][\w]*)\s*=", attrs):
                prop_names.add(prop_match.group(1))

        usages[name] = sorted(prop_names)[:20]

    return usages


def _resolve_js_relative_import(base_rel: str, spec: str, file_index: Dict[str, Dict[str, Any]]) -> Optional[str]:
    if not spec.startswith("."):
        return None

    base_abs = PROJECT_ROOT / base_rel
    target_base = (base_abs.parent / spec).resolve()

    candidates: List[Path] = []
    if target_base.suffix:
        candidates.append(target_base)
    else:
        for ext in JS_EXTS:
            candidates.append(Path(str(target_base) + ext))
        for ext in JS_EXTS:
            candidates.append(target_base / f"index{ext}")

    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            rel = _to_rel(candidate)
        except ValueError:
            continue
        if rel in file_index:
            return rel

    return None


def _resolve_py_import(module: str, file_index: Dict[str, Dict[str, Any]]) -> Optional[str]:
    candidate_modules: List[str] = []

    if module.startswith("backend."):
        candidate_modules.append(module)
    elif module.startswith("app."):
        candidate_modules.append("backend." + module)
    elif module.startswith("graph_rag") or module.startswith("ml") or module.startswith("models"):
        candidate_modules.append(module)
    else:
        return None

    for mod in candidate_modules:
        path_base = mod.replace(".", "/")
        py_rel = f"{path_base}.py"
        init_rel = f"{path_base}/__init__.py"
        if py_rel in file_index:
            return py_rel
        if init_rel in file_index:
            return init_rel

    return None


def _extract_fastapi_endpoints(content: str) -> List[Tuple[str, str]]:
    endpoints: List[Tuple[str, str]] = []
    pattern = r"@(?:router|app)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]"
    for match in re.finditer(pattern, content):
        method = match.group(1).upper()
        route = match.group(2)
        endpoints.append((method, route))
    return endpoints


def _build_external_nodes(nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
    external_defs = {
        "external::llm": {
            "label": "Gemini / LLM Runtime",
            "role": "external_service",
        },
        "external::vector_store": {
            "label": "Vector Store / FAISS",
            "role": "external_service",
        },
        "external::ml_runtime": {
            "label": "ML Runtime (scikit-learn / torch)",
            "role": "external_service",
        },
        "external::cloud_sources": {
            "label": "External Knowledge Sources",
            "role": "external_service",
        },
    }

    for ext_id, ext_meta in external_defs.items():
        if ext_id not in nodes:
            nodes[ext_id] = {
                "id": ext_id,
                "label": ext_meta["label"],
                "path": ext_id,
                "role": ext_meta["role"],
                "layer": "external",
                "color": LAYER_COLORS["external"],
                "exports": [],
                "dependencies": [],
                "metadata": {},
            }

    for node in list(nodes.values()):
        if not node["id"].startswith("file::"):
            continue

        text_blob = " ".join(node.get("dependencies", []) + node.get("metadata", {}).get("api_calls", []))
        lower_blob = text_blob.lower()

        if "ollama" in lower_blob or "gemini" in lower_blob or "api/generate" in lower_blob:
            edges.append({
                "source": node["id"],
                "target": "external::llm",
                "type": "integration",
                "label": "llm",
            })

        if "faiss" in lower_blob or "vector" in lower_blob or "document_registry" in lower_blob:
            edges.append({
                "source": node["id"],
                "target": "external::vector_store",
                "type": "integration",
                "label": "retrieval",
            })

        if any(k in lower_blob for k in ["sklearn", "torch", "pandas", "numpy", "joblib"]):
            edges.append({
                "source": node["id"],
                "target": "external::ml_runtime",
                "type": "integration",
                "label": "ml",
            })

        if any(k in lower_blob for k in ["agris", "agricola", "http://", "https://"]):
            edges.append({
                "source": node["id"],
                "target": "external::cloud_sources",
                "type": "integration",
                "label": "source",
            })


def _add_mode_nodes(nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]], file_nodes: List[Dict[str, Any]]) -> None:
    modes = {
        "mode::edge": "Edge Execution Path",
        "mode::central": "Central Execution Path",
        "mode::local": "Local Execution Path",
    }

    for mode_id, label in modes.items():
        nodes[mode_id] = {
            "id": mode_id,
            "label": label,
            "path": mode_id,
            "role": "execution_mode",
            "layer": "business",
            "color": LAYER_COLORS["business"],
            "exports": [],
            "dependencies": [],
            "metadata": {},
        }

    edge_hits: List[str] = []
    central_hits: List[str] = []
    local_hits: List[str] = []

    for node in file_nodes:
        rel = node["path"]
        content = node.get("_content", "").lower()

        if "edge" in content:
            edge_hits.append(rel)
        if "central" in content:
            central_hits.append(rel)
        if "local_only" in content or "local only" in content or "local-only" in content:
            local_hits.append(rel)

    for rel in edge_hits[:30]:
        edges.append({"source": "mode::edge", "target": f"file::{rel}", "type": "execution", "label": "edge"})
    for rel in central_hits[:30]:
        edges.append({"source": "mode::central", "target": f"file::{rel}", "type": "execution", "label": "central"})
    for rel in local_hits[:30]:
        edges.append({"source": "mode::local", "target": f"file::{rel}", "type": "execution", "label": "local"})


def _dedupe_edges(edges: List[Dict[str, Any]], nodes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    edge_index = 1

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        etype = edge.get("type", "flow")
        label = edge.get("label", "")

        if source not in nodes or target not in nodes:
            continue

        key = (source, target, etype, label)
        if key in seen:
            continue
        seen.add(key)

        edge_payload = {
            "id": f"edge-{edge_index}",
            "source": source,
            "target": target,
            "type": etype,
            "label": label,
        }
        edge_index += 1
        out.append(edge_payload)

    return out


def generate_architecture_snapshot(force_refresh: bool = False) -> Dict[str, Any]:
    files = _collect_code_files()
    fingerprint = _fingerprint(files)

    if (
        not force_refresh
        and _CACHE.get("snapshot") is not None
        and _CACHE.get("fingerprint") == fingerprint
    ):
        return _CACHE["snapshot"]

    file_nodes: List[Dict[str, Any]] = []
    file_index: Dict[str, Dict[str, Any]] = {}

    for path in files:
        rel = _to_rel(path)
        content = _read_text(path)
        layer, role = _classify(rel)
        exports = _extract_exports(content, path.suffix.lower())
        api_calls = _extract_api_calls(content)

        metadata: Dict[str, Any] = {
            "api_calls": api_calls,
        }

        if path.suffix.lower() in JS_EXTS and "frontend/src" in rel:
            metadata.update(_extract_react_metadata(content))

        node = {
            "id": f"file::{rel}",
            "label": _label_for(rel),
            "path": rel,
            "role": role,
            "layer": layer,
            "color": LAYER_COLORS[layer],
            "exports": exports,
            "dependencies": [],
            "metadata": metadata,
            "_content": content,
        }

        file_nodes.append(node)
        file_index[rel] = node

    edges: List[Dict[str, Any]] = []
    endpoint_nodes: Dict[str, Dict[str, Any]] = {}
    boundary_sources: set[str] = set()

    # Extract import and flow relationships.
    for node in file_nodes:
        rel = node["path"]
        content = node["_content"]
        suffix = Path(rel).suffix.lower()

        dep_names: set[str] = set()

        if suffix in JS_EXTS:
            js_imports = _extract_js_imports(content)
            imported_name_to_rel: Dict[str, str] = {}

            for names, spec in js_imports:
                dep_names.add(spec)
                resolved = _resolve_js_relative_import(rel, spec, file_index)
                if resolved:
                    edges.append({"source": node["id"], "target": f"file::{resolved}", "type": "import", "label": "import"})
                    for name in names:
                        imported_name_to_rel[name] = resolved

            jsx_usage = _extract_jsx_usages(content, list(imported_name_to_rel.keys()))
            for comp_name, props in jsx_usage.items():
                target_rel = imported_name_to_rel.get(comp_name)
                if not target_rel:
                    continue
                edges.append({
                    "source": node["id"],
                    "target": f"file::{target_rel}",
                    "type": "props",
                    "label": "props" if not props else ", ".join(props[:4]),
                })

            # Frontend-backend boundary detection via fetch/API usage.
            if rel.startswith("frontend/src/services/") and node["metadata"].get("api_calls"):
                boundary_sources.add(node["id"])

        elif suffix == ".py":
            for module in _extract_py_imports(content):
                dep_names.add(module)
                resolved = _resolve_py_import(module, file_index)
                if resolved:
                    edges.append({"source": node["id"], "target": f"file::{resolved}", "type": "import", "label": "import"})

            # API endpoint extraction.
            if rel.startswith("backend/app/api/") or rel.startswith("backend/api/"):
                for method, route in _extract_fastapi_endpoints(content):
                    prefix = PREFIX_BY_ROUTE_FILE.get(rel, "")
                    full_path = f"{prefix}{route}" if route.startswith("/") else f"{prefix}/{route}"
                    full_path = re.sub(r"//+", "/", full_path)
                    endpoint_id = f"endpoint::{method}:{full_path}"

                    if endpoint_id not in endpoint_nodes:
                        endpoint_nodes[endpoint_id] = {
                            "id": endpoint_id,
                            "label": f"{method} {full_path}",
                            "path": rel,
                            "role": "api_endpoint",
                            "layer": "business",
                            "color": LAYER_COLORS["business"],
                            "exports": [],
                            "dependencies": [],
                            "metadata": {
                                "method": method,
                                "route": full_path,
                            },
                        }

                    edges.append({
                        "source": node["id"],
                        "target": endpoint_id,
                        "type": "exposes",
                        "label": method,
                    })

        node["dependencies"] = sorted(dep_names)[:30]

    # Build frontend-backend boundary node and connect service files.
    boundary_id = "boundary::frontend_backend"
    boundary_node = {
        "id": boundary_id,
        "label": "Frontend ↔ Backend Boundary",
        "path": boundary_id,
        "role": "boundary",
        "layer": "business",
        "color": LAYER_COLORS["business"],
        "exports": [],
        "dependencies": [],
        "metadata": {
            "description": "HTTP/API contract boundary",
        },
    }

    nodes_map: Dict[str, Dict[str, Any]] = {node["id"]: node for node in file_nodes}
    nodes_map.update(endpoint_nodes)
    nodes_map[boundary_id] = boundary_node

    if boundary_sources:
        for source_id in sorted(boundary_sources):
            edges.append({"source": source_id, "target": boundary_id, "type": "api_call", "label": "fetch"})

        # Heuristic binding of frontend services to backend endpoint groups.
        for source_id in sorted(boundary_sources):
            source_node = nodes_map[source_id]
            joined_calls = " ".join(source_node.get("metadata", {}).get("api_calls", [])).lower()
            for endpoint_id, endpoint_node in endpoint_nodes.items():
                route = endpoint_node.get("metadata", {}).get("route", "").lower()
                if not route:
                    continue
                tokens = [t for t in route.split("/") if t and t != "api" and not t.startswith("v")]
                if not tokens:
                    continue
                if any(tok in joined_calls for tok in tokens[:2]):
                    edges.append({"source": boundary_id, "target": endpoint_id, "type": "boundary_flow", "label": "http"})

    _build_external_nodes(nodes_map, edges)
    _add_mode_nodes(nodes_map, edges, file_nodes)

    # Remove non-serializable helper field.
    for node in nodes_map.values():
        if "_content" in node:
            del node["_content"]

    deduped_edges = _dedupe_edges(edges, nodes_map)

    layers = [
        {"id": "ui", "label": "UI Layer", "color": LAYER_COLORS["ui"]},
        {"id": "business", "label": "Business Logic Layer", "color": LAYER_COLORS["business"]},
        {"id": "data", "label": "Data / Model Layer", "color": LAYER_COLORS["data"]},
        {"id": "external", "label": "External Services", "color": LAYER_COLORS["external"]},
    ]

    nodes_out = sorted(
        nodes_map.values(),
        key=lambda n: (
            {"ui": 0, "business": 1, "data": 2, "external": 3}.get(n["layer"], 9),
            n["path"],
        ),
    )

    snapshot = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "project_root": str(PROJECT_ROOT),
        "fingerprint": fingerprint,
        "summary": {
            "files_scanned": len(file_nodes),
            "nodes": len(nodes_out),
            "edges": len(deduped_edges),
            "layers": len(layers),
        },
        "layers": layers,
        "nodes": nodes_out,
        "edges": deduped_edges,
        "execution_paths": {
            "edge": "mode::edge",
            "central": "mode::central",
            "local": "mode::local",
        },
    }

    _CACHE["fingerprint"] = fingerprint
    _CACHE["snapshot"] = snapshot
    _CACHE["built_at"] = time.time()

    return snapshot
