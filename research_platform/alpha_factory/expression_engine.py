"""DSL AST Parser, Validator, and Compiler.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Union
import pandas as pd

from research_platform.alpha_factory import dsl


def split_arguments(s: str) -> List[str]:
    """Split comma-separated arguments at the top-level parentheses level."""
    args = []
    current = []
    level = 0
    for char in s:
        if char == "(":
            level += 1
            current.append(char)
        elif char == ")":
            level -= 1
            current.append(char)
        elif char == "," and level == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        args.append("".join(current).strip())
    return args


class ExpressionEngine:
    """Parses formula strings, builds Abstract Syntax Trees, and evaluates them on DataFrames."""

    @classmethod
    def parse(cls, formula: str) -> Dict[str, Any]:
        """Parse formula string recursively into AST dictionary."""
        formula = formula.strip()
        
        # Check function call syntax: e.g. ts_mean(close, 20)
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)$", formula)
        if match:
            func_name = match.group(1)
            args_str = match.group(2)
            
            # Split arguments at level 0
            args = split_arguments(args_str)
            parsed_args = [cls.parse(arg) for arg in args if arg]
            
            return {
                "type": "function",
                "name": func_name,
                "args": parsed_args
            }

        # Check if constant number
        try:
            val = float(formula)
            # Check if it should be int
            if val.is_integer():
                val = int(val)
            return {"type": "constant", "value": val}
        except ValueError:
            pass

        # Otherwise, assume it is a variable column reference
        return {"type": "variable", "name": formula}

    @classmethod
    def to_string(cls, ast: Dict[str, Any]) -> str:
        """Convert AST back to formula string representation."""
        node_type = ast.get("type")
        if node_type == "constant":
            return str(ast.get("value"))
        elif node_type == "variable":
            return ast.get("name", "")
        elif node_type == "function":
            name = ast.get("name", "")
            args = [cls.to_string(arg) for arg in ast.get("args", [])]
            return f"{name}({', '.join(args)})"
        return ""

    @classmethod
    def evaluate(cls, ast: Dict[str, Any], df: pd.DataFrame) -> pd.Series:
        """Compile and execute the AST tree on the columns of a pandas DataFrame."""
        node_type = ast.get("type")
        
        if node_type == "constant":
            # Return a scalar or constant Series matching DataFrame index length
            return pd.Series(ast.get("value"), index=df.index)
            
        elif node_type == "variable":
            var_name = ast.get("name", "")
            if var_name not in df.columns:
                raise KeyError(f"Variable '{var_name}' not found in the input DataFrame.")
            return df[var_name]
            
        elif node_type == "function":
            func_name = ast.get("name", "")
            args = ast.get("args", [])
            
            # Resolve arguments recursively
            resolved_args = [cls.evaluate(arg, df) for arg in args]
            
            # Map function name to DSL functions
            if func_name == "rank":
                return dsl.rank(resolved_args[0])
            elif func_name == "ts_mean":
                # second argument is a constant period
                n = int(args[1].get("value", 20))
                return dsl.ts_mean(resolved_args[0], n)
            elif func_name == "delta":
                n = int(args[1].get("value", 5))
                return dsl.delta(resolved_args[0], n)
            elif func_name == "correlation":
                n = int(args[2].get("value", 30))
                return dsl.correlation(resolved_args[0], resolved_args[1], n)
            elif func_name == "ts_rank":
                n = int(args[1].get("value", 10))
                return dsl.ts_rank(resolved_args[0], n)
            elif func_name == "signed_power":
                y = float(args[1].get("value", 1.0))
                return dsl.signed_power(resolved_args[0], y)
            elif func_name == "decay_linear":
                n = int(args[1].get("value", 10))
                return dsl.decay_linear(resolved_args[0], n)
            elif func_name == "adv20":
                return dsl.adv20(resolved_args[0])
            elif func_name == "rolling_zscore":
                n = int(args[1].get("value", 20))
                return dsl.rolling_zscore(resolved_args[0], n)
            elif func_name == "neutralize":
                # second argument is group series
                return dsl.neutralize(resolved_args[0], resolved_args[1])
            else:
                raise ValueError(f"Unsupported DSL function: '{func_name}'")

        raise ValueError(f"Unknown AST node type: '{node_type}'")
