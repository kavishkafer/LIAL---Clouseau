"""Deterministic knowledge-graph assembly + layout for the Clouseau Live demo.

Turns captured evidence into a rendered attack-reconstruction graph:

  * Nodes = artifacts the Chief actually committed in its final structured
    report (same addresses/domains/files/malicious_processes/tainted_processes
    schema chief_inspector.py's _emit_artifacts_from_eval already reads).
    Never fabricated here.
  * Edges = derived ONLY between two already-committed node ids, from
    sql_result rows whose columns match a recognized relationship shape
    (pid+ppid -> spawned, pid+object/ip -> connected to, domain+response ->
    resolves to) or from a parsed lateral-movement pivot. A row referencing a
    pid/ip that isn't already a committed node contributes nothing — this is
    the grounding rule: evidence can corroborate a relationship between
    established findings, it can never introduce a new one.
  * Layout = plain layered-DAG placement (topological layer, host-grouped
    track within each layer), converted to collision-free pixel positions
    using the same node-size table the frontend renders with, then expressed
    as 0-100 percentages — the exact graphOp/nodeXY contract the frontend
    already consumes, so no frontend changes are needed.

Entirely deterministic — no LLM call, no network I/O. Gated behind
CLOUSEAU_OBSERVABILITY, same as the rest of the demo instrumentation, and
called synchronously from within ClouseauRun (chief_inspector.py) before
observability.end_run() — so its output reaches the delivery queue before the
run_complete sentinel does, with no backend changes required either.
"""
import json
import re
from typing import Dict, List, Optional

import observability

# Mirrors demo/frontend/index.html's NODE_W/NODE_H/viewBox exactly — keep in
# sync by hand if either changes.
NODE_W = {'host': 108, 'domain': 128, 'ip': 100, 'file': 132, 'process': 110}
NODE_H = 42
VIEW_W = 1500
VIEW_H = 620
ROW_PAD = 20  # vertical gap between tracks within a layer column

_IP_RE = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')


def _safe_id(prefix: str, value) -> str:
    return prefix + '_' + re.sub(r'[^A-Za-z0-9]+', '_', str(value)).strip('_')


def _extract_nodes(eval_json_text) -> Dict[str, dict]:
    """Parses the same structured report chief_inspector.py's
    _emit_artifacts_from_eval reads, returning {node_id: node_dict} instead of
    emitting events. These are the only nodes that can ever appear — edges
    can only connect ids present in this dict."""
    if not isinstance(eval_json_text, str):
        return {}
    text = eval_json_text.strip()
    if text.startswith('```'):
        text = text.strip('`')
        if text.lower().startswith('json'):
            text = text[4:]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    items = data[0] if isinstance(data, list) and data else data
    if not isinstance(items, dict):
        return {}

    nodes: Dict[str, dict] = {}
    for addr in items.get('addresses') or []:
        nid = _safe_id('ip', addr)
        nodes[nid] = {'id': nid, 'kind': 'ip', 'label': str(addr), 'status': 'critical'}
    for dom in items.get('domains') or []:
        nid = _safe_id('domain', dom)
        nodes[nid] = {'id': nid, 'kind': 'domain', 'label': str(dom), 'status': None}
    for f in items.get('files') or []:
        nid = _safe_id('file', f)
        nodes[nid] = {'id': nid, 'kind': 'file', 'label': str(f), 'status': 'critical'}
    for proc in items.get('malicious_processes') or []:
        pid, name = proc.get('pid'), proc.get('name', 'unknown')
        nid = _safe_id('proc', pid if pid is not None else name)
        label = f"{name}\nPID {pid}" if pid is not None else name
        nodes[nid] = {'id': nid, 'kind': 'process', 'label': label, 'status': 'critical'}
    for proc in items.get('tainted_processes') or []:
        pid, name = proc.get('pid'), proc.get('name', 'unknown')
        nid = _safe_id('proc', pid if pid is not None else name)
        label = f"{name}\nPID {pid}" if pid is not None else name
        nodes[nid] = {'id': nid, 'kind': 'process', 'label': label, 'status': 'serious'}
    return nodes


def _derive_edges(nodes: Dict[str, dict], sql_result_events: List[dict]) -> List[dict]:
    edges: List[dict] = []
    seen = set()

    def add_edge(src, dst, label):
        key = (src, dst, label)
        if src in nodes and dst in nodes and src != dst and key not in seen:
            seen.add(key)
            edges.append({'id': f'e{len(edges)}', 'from': src, 'to': dst, 'label': label})

    for ev in sql_result_events:
        detail = ev.get('detail') or {}
        col_names, rows = detail.get('col_names'), detail.get('rows')
        if not col_names or not rows:
            continue
        cols_lower = [str(c).lower() for c in col_names]
        col_idx = {c: i for i, c in enumerate(cols_lower)}

        has_pid, has_ppid = 'pid' in col_idx, 'ppid' in col_idx
        has_domain = 'domain' in col_idx or 'query' in col_idx
        has_response = 'response' in col_idx or 'answers' in col_idx
        obj_col = next((c for c in ('object', 'ip', 'address') if c in col_idx), None)

        for row in rows:
            if has_pid and has_ppid:
                pid_val, ppid_val = row[col_idx['pid']], row[col_idx['ppid']]
                if ppid_val and str(ppid_val).lower() != 'none':
                    add_edge(_safe_id('proc', ppid_val), _safe_id('proc', pid_val), 'spawned')
            if has_pid and obj_col:
                m = _IP_RE.search(str(row[col_idx[obj_col]]))
                if m:
                    add_edge(_safe_id('proc', row[col_idx['pid']]), _safe_id('ip', m.group(1)), 'connected to')
            if has_domain and has_response:
                dcol = 'domain' if 'domain' in col_idx else 'query'
                rcol = 'response' if 'response' in col_idx else 'answers'
                dom_nid = _safe_id('domain', row[col_idx[dcol]])
                for ip in _IP_RE.findall(str(row[col_idx[rcol]])):
                    add_edge(dom_nid, _safe_id('ip', ip), 'resolves to')
    return edges


def _derive_pivot_edges(nodes: Dict[str, dict], pivot_events: List[dict]) -> List[dict]:
    edges = []
    for i, ev in enumerate(pivot_events):
        d = ev.get('detail') or {}
        pid, dst_host = d.get('pid'), d.get('dst_host')
        if pid is None or not dst_host:
            continue
        src_nid, dst_nid = _safe_id('proc', pid), _safe_id('host', dst_host)
        if src_nid in nodes and dst_nid in nodes:
            edges.append({'id': f'epivot{i}', 'from': src_nid, 'to': dst_nid,
                           'label': 'lateral movement', 'pivot': True})
    return edges


def _layer_nodes(nodes: Dict[str, dict], edges: List[dict]) -> Dict[str, int]:
    """Longest-path layering: layer(child) >= layer(parent) + 1 for every
    edge. Nodes with no incoming edge sit at layer 0. Iterative relaxation
    (bounded by node count) rather than a strict topological sort — safer if
    the edge set ever contains a cycle (shouldn't happen with this edge
    vocabulary, but this degrades gracefully instead of raising)."""
    layer = {nid: 0 for nid in nodes}
    for _ in range(len(nodes) + 1):
        changed = False
        for e in edges:
            if e['from'] in layer and e['to'] in layer and layer[e['to']] < layer[e['from']] + 1:
                layer[e['to']] = layer[e['from']] + 1
                changed = True
        if not changed:
            break
    return layer


def _assign_positions(nodes: Dict[str, dict], layer: Dict[str, int]) -> None:
    """Groups nodes by layer into tracks (ordered by host so same-host nodes
    cluster together), then converts to collision-free pixel positions —
    compressing row spacing if a layer has more nodes than the viewBox height
    comfortably fits, the same technique used for the Agents topology view
    client-side. Mutates each node dict in place with 'x'/'y' (0-100)."""
    by_layer: Dict[int, List[str]] = {}
    for nid in nodes:
        by_layer.setdefault(layer.get(nid, 0), []).append(nid)

    max_layer = max(by_layer) if by_layer else 0
    col_w = VIEW_W / (max_layer + 1)

    for lyr, nids in by_layer.items():
        nids.sort(key=lambda n: (nodes[n].get('host') or '', n))
        row_h = NODE_H + ROW_PAD
        total_h = row_h * len(nids)
        if total_h > VIEW_H:
            row_h = VIEW_H / len(nids)
        start_y = (VIEW_H - row_h * len(nids)) / 2
        cx = col_w * lyr + col_w / 2
        for i, nid in enumerate(nids):
            cy = start_y + row_h * (i + 0.5)
            nodes[nid]['x'] = round(max(0.0, min(100.0, cx / VIEW_W * 100)), 2)
            nodes[nid]['y'] = round(max(0.0, min(100.0, cy / VIEW_H * 100)), 2)


def assemble(host_labels: Optional[List[str]], eval_json_by_host: Dict[str, str],
             captured_events: List[dict]) -> Optional[List[dict]]:
    """Pure function (no observability side effects) — returns a list of
    graphOp dicts ready to emit, or None if there's nothing to draw. Kept
    separate from assemble_and_emit() so it's directly unit-testable."""
    nodes: Dict[str, dict] = {}
    for host, eval_text in (eval_json_by_host or {}).items():
        for nid, n in _extract_nodes(eval_text).items():
            n['host'] = host
            nodes[nid] = n
    if not nodes:
        return None

    for host in host_labels or []:
        nid = _safe_id('host', host)
        nodes.setdefault(nid, {'id': nid, 'kind': 'host', 'label': host, 'host': host, 'status': None})

    sql_result_events = [e for e in captured_events if e.get('type') == 'sql_result']
    pivot_events = [e for e in captured_events if e.get('type') == 'pivot_found']

    edges = _derive_edges(nodes, sql_result_events)
    edges += _derive_pivot_edges(nodes, pivot_events)

    layer = _layer_nodes(nodes, edges)
    _assign_positions(nodes, layer)

    ops: List[dict] = []
    for n in nodes.values():
        node_op = {'id': n['id'], 'label': n['label'], 'kind': n['kind'], 'x': n['x'], 'y': n['y']}
        if n.get('status'):
            node_op['status'] = n['status']
        ops.append({'op': 'addNode', 'node': node_op})
    for e in edges:
        edge_op = {'id': e['id'], 'from': e['from'], 'to': e['to'], 'label': e['label']}
        if e.get('pivot'):
            edge_op['pivot'] = True
        ops.append({'op': 'addEdge', 'edge': edge_op})
    return ops


def assemble_and_emit(run_id: str, host_labels: Optional[List[str]], eval_json_by_host: Dict[str, str]) -> None:
    if not observability.is_enabled() or not run_id:
        return
    ops = assemble(host_labels, eval_json_by_host, observability.get_log(run_id))
    if not ops:
        return
    n_nodes = sum(1 for o in ops if o['op'] == 'addNode')
    n_edges = sum(1 for o in ops if o['op'] == 'addEdge')
    observability.emit(
        run_id, 'graph_assembled', role='system', agent_id='system',
        narration=f"Attack graph assembled: {n_nodes} artifacts, {n_edges} relationships.",
        detail={'node_count': n_nodes, 'edge_count': n_edges}, graph_op=ops,
    )
