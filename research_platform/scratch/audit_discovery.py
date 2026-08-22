"""Automated AST-based static codebase analysis and metadata discovery for TOJI platform."""

from __future__ import annotations

import os
import ast
import json
import logging

logger = logging.getLogger(__name__)

SCAN_DIR = "/Users/a.ganeshkumarreddy12/TOJI/research_platform"


def analyze_file(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {}

    file_meta = {
        "classes": [],
        "interfaces": [],
        "plugins": [],
        "repositories": [],
        "models": [],
        "events": [],
        "db_tables": [],
        "exports": [],
        "threads": False
    }

    # Find exports in __init__.py files
    if filepath.endswith("__init__.py"):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            file_meta["exports"] = [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)]

    # Thread check
    if "threading.Thread" in content or "Thread(" in content:
        file_meta["threads"] = True

    # Scan classes
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)

            # Class metadata
            class_info = {
                "name": class_name,
                "bases": bases,
                "methods": [sub.name for sub in node.body if isinstance(sub, ast.FunctionDef)]
            }
            file_meta["classes"].append(class_info)

            # Interfaces (e.g. starts with I, or inherits from ABC/abc.ABC, or has abstractmethods)
            is_abc = any("ABC" in b for b in bases)
            has_abstract = any(
                isinstance(decorator, ast.Name) and decorator.id == "abstractmethod"
                for sub in node.body if isinstance(sub, ast.FunctionDef)
                for decorator in getattr(sub, "decorator_list", [])
            )
            if class_name.startswith("I") or is_abc or has_abstract:
                file_meta["interfaces"].append(class_name)

            # Plugins (ends with Plugin)
            if class_name.endswith("Plugin"):
                file_meta["plugins"].append(class_name)

            # Repositories (ends with Repository)
            if class_name.endswith("Repository"):
                file_meta["repositories"].append(class_name)

            # Models (inherits from BaseModel or Base or ends with Model)
            is_model = any(b in ("BaseModel", "Base") or class_name.endswith("Model") for b in bases)
            if is_model:
                file_meta["models"].append(class_name)

            # Database Table Names in SQLAlchemy Models
            if "Base" in bases or class_name.endswith("Model"):
                for sub in node.body:
                    if isinstance(sub, ast.Assign):
                        for target in sub.targets:
                            if isinstance(target, ast.Name) and target.id == "__tablename__":
                                if isinstance(sub.value, ast.Constant):
                                    file_meta["db_tables"].append(sub.value.value)

            # Event identification (inside events.py files or inheriting from Event/BaseModel)
            is_event_file = "events.py" in filepath
            if is_event_file and (any(b in ("BaseModel", "Event", "ValidationEvent", "MetricsEvent", "AlertEvent") for b in bases)):
                file_meta["events"].append(class_name)

    return file_meta


def scan_platform() -> dict:
    inventory = {
        "subsystems": [],
        "packages": [],
        "modules": [],
        "plugins": [],
        "repositories": [],
        "interfaces": [],
        "models": [],
        "events": [],
        "db_tables": [],
        "exports": [],
        "threads_detected": []
    }

    for root, dirs, files in os.walk(SCAN_DIR):
        if "__pycache__" in root or ".pytest_cache" in root or "tests" in root:
            continue

        rel_path = os.path.relpath(root, SCAN_DIR)
        if rel_path == ".":
            rel_path = "research_platform"
        else:
            rel_path = f"research_platform.{rel_path.replace(os.sep, '.')}"

        # Subsystems are top-level directories under research_platform
        if os.path.dirname(root) == SCAN_DIR:
            inventory["subsystems"].append(os.path.basename(root))

        if any(f.endswith(".py") for f in files):
            inventory["packages"].append(rel_path)

        for file in files:
            if file.endswith(".py"):
                mod_path = f"{rel_path}.{file[:-3]}"
                inventory["modules"].append(mod_path)
                filepath = os.path.join(root, file)

                file_meta = analyze_file(filepath)
                if not file_meta:
                    continue

                inventory["plugins"].extend(file_meta["plugins"])
                inventory["interfaces"].extend(file_meta["interfaces"])
                inventory["repositories"].extend(file_meta["repositories"])
                inventory["models"].extend(file_meta["models"])
                inventory["events"].extend(file_meta["events"])
                inventory["db_tables"].extend(file_meta["db_tables"])
                inventory["exports"].extend(file_meta["exports"])
                if file_meta["threads"]:
                    inventory["threads_detected"].append(mod_path)

    # De-duplicate lists
    for k in ["subsystems", "packages", "modules", "plugins", "interfaces", "repositories", "models", "events", "db_tables", "exports"]:
        inventory[k] = sorted(list(set(inventory[k])))

    return inventory


if __name__ == "__main__":
    result = scan_platform()
    output_path = "/Users/a.ganeshkumarreddy12/TOJI/research_platform/scratch/platform_inventory.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
    print(f"Platform Discovery completed. Inventory saved to {output_path}")
    print(f"Total Subsystems: {len(result['subsystems'])}")
    print(f"Total Plugins: {len(result['plugins'])}")
    print(f"Total Interfaces: {len(result['interfaces'])}")
    print(f"Total Repositories: {len(result['repositories'])}")
    print(f"Total Models: {len(result['models'])}")
    print(f"Total Database Tables: {len(result['db_tables'])}")
