"""R51 Secrets manager.
"""

from __future__ import annotations

import base64
from typing import Dict, Any


class SecretsManager:
    """Masks credentials and manages base64/file secrets resolution."""

    @staticmethod
    def resolve_secrets(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Resolves configuration dictionaries, decoding password or key entries if encoded."""
        # Check database password
        db = config_dict.get("database", {})
        if isinstance(db, dict) and "password" in db:
            pwd = db["password"]
            if pwd.startswith("base64:"):
                try:
                    decoded = base64.b64decode(pwd[7:]).decode("utf-8")
                    db["password"] = decoded
                except Exception:
                    pass

        # Check exchange api key/secret
        exch = config_dict.get("exchange", {})
        if isinstance(exch, dict):
            for sec_key in ["api_key", "api_secret"]:
                if sec_key in exch:
                    val = exch[sec_key]
                    if val.startswith("base64:"):
                        try:
                            decoded = base64.b64decode(val[7:]).decode("utf-8")
                            exch[sec_key] = decoded
                        except Exception:
                            pass
        return config_dict
