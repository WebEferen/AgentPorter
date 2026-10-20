from __future__ import annotations

from collections import defaultdict
from typing import Hashable, Iterable, Mapping


def tarjan_scc(nodes: Iterable[Hashable], edges: Mapping[Hashable, Iterable[Hashable]]) -> list[list[Hashable]]:
    """Strongly connected components, iterative (no recursion limit), deterministic order."""
    index: dict = {}
    low: dict = {}
    on_stack: set = set()
    stack: list = []
    result: list[list] = []
    counter = 0
    node_list = list(nodes)
    known = set(node_list)
    for start in node_list:
        if start in index:
            continue
        work = [(start, iter(sorted((n for n in edges.get(start, ()) if n in known), key=str)))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted((n for n in edges.get(nxt, ()) if n in known), key=str))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    item = stack.pop()
                    on_stack.discard(item)
                    comp.append(item)
                    if item == node:
                        break
                result.append(sorted(comp, key=str))
    return result


def cycles(nodes: Iterable[Hashable], edges: Mapping[Hashable, Iterable[Hashable]]) -> list[list[Hashable]]:
    out = []
    for comp in tarjan_scc(nodes, edges):
        if len(comp) > 1 or (comp and comp[0] in set(edges.get(comp[0], ()))):
            out.append(comp)
    return out


def waves(nodes: Iterable[Hashable], deps: Mapping[Hashable, Iterable[Hashable]]) -> dict:
    """Longest-path depth from a leaf over an acyclic dependency map (node -> things it depends on)."""
    nodes = list(nodes)
    known = set(nodes)
    depth: dict = {}
    indeg = {n: 0 for n in nodes}
    users = defaultdict(list)
    for n in nodes:
        for d in set(deps.get(n, ())):
            if d in known and d != n:
                indeg[n] += 1
                users[d].append(n)
    ready = sorted((n for n in nodes if indeg[n] == 0), key=str)
    for n in ready:
        depth[n] = 0
    queue = list(ready)
    while queue:
        n = queue.pop(0)
        for u in sorted(users[n], key=str):
            depth[u] = max(depth.get(u, 0), depth[n] + 1)
            indeg[u] -= 1
            if indeg[u] == 0:
                queue.append(u)
    if len(depth) != len(nodes):
        missing = sorted((n for n in nodes if n not in depth), key=str)
        raise ValueError(f"dependency cycle among: {missing}")
    return depth


def reachable(start: Hashable, edges: Mapping[Hashable, Iterable[Hashable]]) -> set:
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for nxt in edges.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen
