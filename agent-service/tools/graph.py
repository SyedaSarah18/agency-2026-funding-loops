"""NetworkX helpers for cycle / centrality work on funding-loop subgraphs."""
from __future__ import annotations

import json
from typing import Iterable

import networkx as nx
from strands import tool


@tool
def build_loop_graph(edges_json: str) -> str:
    """Build a directed graph from charity-to-charity gift edges and return
    structural metrics useful for assessing how 'tight' a funding loop is.

    Input: JSON string of a list of edges, each edge is
        [from_bn, to_bn, dollar_amount, fiscal_year]

    Returns JSON with:
        - node_count, edge_count
        - cycles: list of detected cycles (node IDs only, capped at 20)
        - in_degree / out_degree per node
        - betweenness_centrality per node (who's the bottleneck)
        - net_flow per node (in - out dollars)
    """
    try:
        edges = json.loads(edges_json)
    except Exception as e:
        return json.dumps({"error": f"bad edges_json: {e}"})

    G = nx.DiGraph()
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) < 3:
            continue
        u, v, amt = e[0], e[1], float(e[2])
        if G.has_edge(u, v):
            G[u][v]["weight"] += amt
        else:
            G.add_edge(u, v, weight=amt)

    cycles = []
    if G.number_of_nodes() <= 50:
        for c in nx.simple_cycles(G):
            cycles.append(c)
            if len(cycles) >= 20:
                break

    centrality = nx.betweenness_centrality(G, weight="weight") if G.number_of_nodes() <= 100 else {}
    net_flow = {
        n: round(sum(d["weight"] for _, _, d in G.in_edges(n, data=True))
                 - sum(d["weight"] for _, _, d in G.out_edges(n, data=True)), 2)
        for n in G.nodes
    }

    return json.dumps({
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "cycles": cycles,
        "in_degree": {n: G.in_degree(n) for n in G.nodes},
        "out_degree": {n: G.out_degree(n) for n in G.nodes},
        "betweenness_centrality": {n: round(c, 4) for n, c in centrality.items()},
        "net_flow": net_flow,
    }, default=str)
