"""Detect circular imports dynamically by tracing imports across AST nodes."""

from __future__ import annotations

import os
import ast
import logging

logger = logging.getLogger(__name__)

SCAN_DIR = "/Users/a.ganeshkumarreddy12/TOJI/research_platform"


def get_module_imports(filepath: str) -> list[str]:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.append(name.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def find_cycles() -> list[list[str]]:
    # Build dependency graph
    graph = {}
    
    for root, dirs, files in os.walk(SCAN_DIR):
        if "__pycache__" in root or ".pytest_cache" in root or "tests" in root or "scratch" in root:
            continue

        rel_path = os.path.relpath(root, SCAN_DIR)
        if rel_path == ".":
            pkg = "research_platform"
        else:
            pkg = f"research_platform.{rel_path.replace(os.sep, '.')}"

        for file in files:
            if file.endswith(".py"):
                module_name = f"{pkg}.{file[:-3]}"
                filepath = os.path.join(root, file)
                
                imported_modules = get_module_imports(filepath)
                # Filter to internal research_platform imports only
                internal = []
                for imp in imported_modules:
                    if imp.startswith("research_platform"):
                        # Normalize to module level
                        parts = imp.split(".")
                        # Limit to package-level resolution for cleaner graph
                        if len(parts) >= 2:
                            internal.append(f"research_platform.{parts[1]}")
                
                current_pkg = f"research_platform.{module_name.split('.')[1]}"
                if current_pkg not in graph:
                    graph[current_pkg] = set()
                for target in internal:
                    if target != current_pkg:
                        graph[current_pkg].add(target)

    # DFS path detection
    cycles = []
    visited = {}  # None = unvisited, 1 = visiting, 2 = visited

    def dfs(node, path):
        visited[node] = 1
        path.append(node)

        for neighbor in graph.get(node, []):
            if visited.get(neighbor) == 1:
                idx = path.index(neighbor)
                cycles.append(path[idx:] + [neighbor])
            elif neighbor not in visited:
                dfs(neighbor, path)

        path.pop()
        visited[node] = 2

    for node in graph:
        if node not in visited:
            dfs(node, [])

    return cycles


if __name__ == "__main__":
    cycles = find_cycles()
    if cycles:
        print("WARNING: Circular import cycles detected:")
        for cycle in cycles:
            print(" -> ".join(cycle))
    else:
        print("SUCCESS: Circular import check passed. No cycles detected at package-level.")
