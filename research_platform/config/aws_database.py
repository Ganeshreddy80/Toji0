"""Secure database configuration retrieval from AWS Secrets Manager.

The provider deliberately uses boto3's default credential chain so an EC2 IAM
role is used in production. Local and development callers may inject a client
for tests or omit the provider entirely.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Mapping, Optional
from urllib.parse import parse_qs, unquote, urlparse

logger = logging.getLogger(__name__)


_DATABASE_ALIASES = {
    "host": "host",
    "port": "port",
    "database": "database",
    "dbname": "database",
    "username": "username",
    "user": "username",
    "password": "password",
    "raw_url": "raw_url",
    "url": "raw_url",
    "database_url": "raw_url",
    "connection_string": "raw_url",
    "DATABASE_URL": "raw_url",
    "sslmode": "sslmode",
    "sslrootcert": "sslrootcert",
    "channel_binding": "channel_binding",
}


def database_config_from_url(raw_url: str) -> dict[str, Any]:
    """Convert a PostgreSQL URL into the application's database config shape."""
    normalized = raw_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
        raise ValueError("database URL must be a PostgreSQL URL with a host")

    config: dict[str, Any] = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/"),
        "raw_url": normalized,
    }
    if parsed.username is not None:
        config["username"] = unquote(parsed.username)
    if parsed.password is not None:
        config["password"] = unquote(parsed.password)
    query = parse_qs(parsed.query)
    for key in ("sslmode", "sslrootcert", "channel_binding"):
        if key in query:
            config[key] = query[key][0]
    return config


class AWSDatabaseSecretProvider:
    """Load database configuration from AWS Secrets Manager.

    With no injected client, boto3 uses its normal credential provider chain,
    including the EC2 instance profile. The provider never logs secret values.
    """

    def __init__(
        self,
        secret_name: Optional[str] = None,
        region_name: Optional[str] = None,
        client: Any = None,
    ) -> None:
        self.secret_name = secret_name or os.getenv("TOJI_DATABASE_SECRET_NAME") or os.getenv(
            "AWS_DATABASE_SECRET_NAME"
        )
        self.region_name = region_name or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.secret_name)

    def load_database_config(self) -> Optional[dict[str, Any]]:
        """Return normalized database settings, or ``None`` if not configured."""
        if not self.secret_name:
            return None

        client = self._client or self._build_client()
        try:
            response = client.get_secret_value(SecretId=self.secret_name)
        except Exception as exc:
            # Do not include the exception text: botocore errors can contain
            # request details, URLs, or provider-specific sensitive context.
            logger.error(
                "AWS database secret retrieval failed (error_type=%s).",
                type(exc).__name__,
            )
            raise RuntimeError("Unable to retrieve database configuration from AWS Secrets Manager") from None

        payload = self._decode_response(response)
        return self._normalize_payload(payload)

    def _build_client(self) -> Any:
        try:
            import boto3
        except ImportError:
            raise RuntimeError("boto3 is required for AWS database secret retrieval") from None
        session = boto3.Session()
        if self.region_name:
            return session.client("secretsmanager", region_name=self.region_name)
        return session.client("secretsmanager")

    @staticmethod
    def _decode_response(response: Mapping[str, Any]) -> Mapping[str, Any]:
        secret_string = response.get("SecretString")
        if secret_string is not None:
            try:
                payload = json.loads(secret_string)
            except (TypeError, json.JSONDecodeError):
                raise RuntimeError("AWS database secret must contain valid JSON") from None
        else:
            binary = response.get("SecretBinary")
            if binary is None:
                raise RuntimeError("AWS database secret did not contain a value")
            try:
                if isinstance(binary, str):
                    binary = base64.b64decode(binary)
                payload = json.loads(bytes(binary).decode("utf-8"))
            except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
                raise RuntimeError("AWS database secret must contain valid JSON") from None

        if not isinstance(payload, Mapping):
            raise RuntimeError("AWS database secret must contain a JSON object")
        return payload

    @staticmethod
    def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        nested = payload.get("database")
        source: Mapping[str, Any] = nested if isinstance(nested, Mapping) else payload

        normalized: dict[str, Any] = {}
        for key, value in source.items():
            target = _DATABASE_ALIASES.get(str(key))
            if target is not None:
                normalized[target] = value

        raw_url = normalized.get("raw_url")
        if raw_url:
            try:
                url_config = database_config_from_url(str(raw_url))
            except ValueError:
                raise RuntimeError("AWS database secret contained an invalid PostgreSQL URL") from None
            url_config.update({k: v for k, v in normalized.items() if k != "raw_url"})
            normalized = url_config

        if "port" in normalized:
            try:
                normalized["port"] = int(normalized["port"])
            except (TypeError, ValueError):
                raise RuntimeError("AWS database secret contained an invalid port") from None

        required = {"host", "database", "username", "password"}
        if not required.issubset(normalized):
            raise RuntimeError("AWS database secret is missing required database fields")
        return normalized
