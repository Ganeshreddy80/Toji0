"""Custom AST-based static code quality analyzer for TOJI V1."""

from __future__ import annotations

import os
import ast
import sys
import json


class TojiCodeQualityAnalyzer(ast.NodeVisitor):
    """AST visitor to audit imports, security risks, dead functions, and duplicates."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.imported_names: dict[str, int] = {}  # name -> line
        self.used_names: set[str] = set()
        self.defined_privates: dict[str, int] = {}  # name -> line
        self.referenced_privates: set[str] = set()
        self.definitions: dict[str, list[int]] = {}  # name -> list of lines
        self.security_issues: list[dict[str, str | int]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            # Keep base module name if it contains dots
            self.imported_names[name.split(".")[0]] = node.lineno
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self.imported_names[name] = node.lineno
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
            if node.id.startswith("_") and not node.id.startswith("__"):
                self.referenced_privates.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_") and not node.attr.startswith("__"):
            self.referenced_privates.add(node.attr)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        name = node.name
        self.definitions.setdefault(name, []).append(node.lineno)
        if name.startswith("_") and not name.startswith("__"):
            self.defined_privates[name] = node.lineno
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        name = node.name
        self.definitions.setdefault(name, []).append(node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check security issues
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ("eval", "exec", "input"):
                self.security_issues.append({
                    "type": "Dangerous Builtin",
                    "msg": f"Use of dangerous builtin '{func_name}' is a security risk.",
                    "line": node.lineno
                })
        
        # Check subprocess shell=True
        if self._is_subprocess_call(node):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self.security_issues.append({
                        "type": "Subprocess Shell True",
                        "msg": "Subprocess execution with shell=True is vulnerable to injection.",
                        "line": node.lineno
                    })

        # Check raw query execution with potential SQL injection
        if self._is_query_execution(node):
            # Check if any argument uses string formatting or addition
            for arg in node.args:
                if self._has_string_formatting(arg):
                    self.security_issues.append({
                        "type": "SQL Injection Risk",
                        "msg": "Database query formatting via string concatenation or format(). Use query parameters.",
                        "line": node.lineno
                    })

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Check hardcoded secrets/passwords
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_lower = target.id.lower()
                if any(x in name_lower for x in ("password", "secret", "api_key", "token")):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        # Ignore obviously mock values or empty
                        val = node.value.value
                        if val and not any(m in val.lower() for m in ("mock", "test", "dummy", "admin@toji.local", "toji")):
                            self.security_issues.append({
                                "type": "Hardcoded Secret",
                                "msg": f"Possible hardcoded credential variable '{target.id}' assigned raw string literal.",
                                "line": node.lineno
                            })
        self.generic_visit(node)

    def _is_subprocess_call(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                return True
        return False

    def _is_query_execution(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("execute", "execute_query", "run_query"):
                return True
        return False

    def _has_string_formatting(self, node: ast.AST) -> bool:
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            return True
        if isinstance(node, ast.JoinedStr):  # f-strings
            return True
        return False


def run_static_quality_audit(scan_dir: str):
    print(f"Scanning directory: {scan_dir}...")
    
    all_unused_imports = []
    all_security_issues = []
    all_dead_privates = []
    all_duplicates = []

    total_files = 0
    for root, _, files in os.walk(scan_dir):
        for f in files:
            if f.endswith(".py"):
                filepath = os.path.join(root, f)
                total_files += 1
                try:
                    with open(filepath, "r", encoding="utf-8") as file_obj:
                        code = file_obj.read()
                    
                    tree = ast.parse(code, filename=filepath)
                    analyzer = TojiCodeQualityAnalyzer(filepath)
                    analyzer.visit(tree)

                    # Compute unused imports
                    for imp, line in analyzer.imported_names.items():
                        if imp not in analyzer.used_names:
                            # Filter out standard fallback imports or init imports
                            if not f.endswith("__init__.py"):
                                all_unused_imports.append({
                                    "file": filepath,
                                    "line": line,
                                    "name": imp
                                })

                    # Compute security issues
                    for issue in analyzer.security_issues:
                        all_security_issues.append({
                            "file": filepath,
                            "line": issue["line"],
                            "type": issue["type"],
                            "msg": issue["msg"]
                        })

                    # Compute unused private definitions
                    for priv, line in analyzer.defined_privates.items():
                        if priv not in analyzer.referenced_privates:
                            all_dead_privates.append({
                                "file": filepath,
                                "line": line,
                                "name": priv
                            })

                    # Compute duplicates
                    for name, lines in analyzer.definitions.items():
                        if len(lines) > 1:
                            all_duplicates.append({
                                "file": filepath,
                                "lines": lines,
                                "name": name
                            })

                except Exception as e:
                    print(f"Error parsing {filepath}: {e}", file=sys.stderr)

    # Format report
    unused_imports_rows = []
    for ui in all_unused_imports[:15]:  # Limit rows
        rel_path = os.path.relpath(ui["file"], scan_dir)
        unused_imports_rows.append(f"| `{rel_path}` | {ui['line']} | `{ui['name']}` |")

    security_rows = []
    for sec in all_security_issues[:15]:
        rel_path = os.path.relpath(sec["file"], scan_dir)
        security_rows.append(f"| `{rel_path}` | {sec['line']} | **{sec['type']}** | {sec['msg']} |")

    dead_privates_rows = []
    for dp in all_dead_privates[:15]:
        rel_path = os.path.relpath(dp["file"], scan_dir)
        dead_privates_rows.append(f"| `{rel_path}` | {dp['line']} | `{dp['name']}` |")

    duplicates_rows = []
    for dup in all_duplicates[:15]:
        rel_path = os.path.relpath(dup["file"], scan_dir)
        lines_str = ", ".join(map(str, dup["lines"]))
        duplicates_rows.append(f"| `{rel_path}` | {lines_str} | `{dup['name']}` |")

    report_content = f"""# CODE_QUALITY_REPORT.md — Static Code Quality Audit

## 1. Static Scan Overview
- **Total Files Scanned**: `{total_files}`
- **Quality Standard**: Zero warnings, unused imports pruned, safe dependency hierarchies.

---

## 2. Unused Imports ({len(all_unused_imports)} occurrences)
Unused imports block namespaces and increase footprint.

| File Path | Line | Unused Import Name |
| :--- | :--- | :--- |
{chr(10).join(unused_imports_rows) if unused_imports_rows else "| None | - | - |"}

---

## 3. Potential Security Vulnerabilities ({len(all_security_issues)} occurrences)
Bandit-level security analysis checking execution inputs, shell processes, and query concatenations.

| File Path | Line | Vulnerability Type | Description |
| :--- | :--- | :--- | :--- |
{chr(10).join(security_rows) if security_rows else "| None | - | - | - |"}

---

## 4. Dead Code / Unused Private Members ({len(all_dead_privates)} occurrences)
Private functions or members prefixed with an underscore defined but not called or referenced in the module scope.

| File Path | Line | Private Member Name |
| :--- | :--- | :--- |
{chr(10).join(dead_privates_rows) if dead_privates_rows else "| None | - | - |"}

---

## 5. Duplicate Function / Class Definitions ({len(all_duplicates)} occurrences)
Identified overlapping namespaces within the same module scope.

| File Path | Lines | Definition Name |
| :--- | :--- | :--- |
{chr(10).join(duplicates_rows) if duplicates_rows else "| None | - | - |"}
"""

    report_dir = "/Users/a.ganeshkumarreddy12/TOJI/research_platform/scratch/reports"
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "CODE_QUALITY_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"CODE_QUALITY_REPORT.md generated successfully at {report_path}")


if __name__ == "__main__":
    run_static_quality_audit("/Users/a.ganeshkumarreddy12/TOJI/research_platform")
