"""Toji Platform — The OS Kernel for quantitative research.

This package provides the foundational kernel that all Toji modules
plug into: event bus, registries, plugin management, configuration,
logging, lifecycle, and dependency injection.
"""

import sys

# ── Standard Library Platform Shadowing Workaround ───────────────────────────
# Because this package is named 'platform', it shadows Python's standard library
# 'platform' module. We dynamically resolve and merge the standard library
# module's attributes here so that third-party packages (like pytest, zstandard,
# etc.) can still import platform and access standard functions like
# platform.python_implementation() or platform.system().
# ─────────────────────────────────────────────────────────────────────────────
def _bootstrap_stdlib_platform() -> None:
    original_path = sys.path.copy()
    # Filter out path entries pointing to the workspace root or local platform directory
    sys.path = [
        p for p in sys.path 
        if p != "" and "TOJI" not in p and not p.endswith("toji")
    ]
    
    current_platform = sys.modules.get("platform")
    if "platform" in sys.modules:
        del sys.modules["platform"]
        
    try:
        import platform as stdlib_platform
        for attr in dir(stdlib_platform):
            if not attr.startswith("__"):
                globals()[attr] = getattr(stdlib_platform, attr)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to bootstrap stdlib platform module: {e}\n")
    finally:
        sys.path = original_path
        if current_platform is not None:
            sys.modules["platform"] = current_platform

_bootstrap_stdlib_platform()
del _bootstrap_stdlib_platform


__version__ = "0.1.0"
__package_name__ = "toji-platform"

