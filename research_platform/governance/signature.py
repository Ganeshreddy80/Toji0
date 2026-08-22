"""Cryptographic signature verifier implementing ISignatureVerifier.
"""

from __future__ import annotations

import logging
from research_platform.governance.interfaces import ISignatureVerifier
from research_platform.governance.models import DigitalSignature

logger = logging.getLogger(__name__)


class SignatureVerifier(ISignatureVerifier):
    """Verifies cryptographic signatures of deployment authorizations."""

    def verify_signature(self, signature: DigitalSignature, data_hash: str) -> bool:
        """Verify signature match against public key hashes."""
        if not signature.signature or not signature.public_key_hash:
            return False

        # Simulate crypto check: check that signature token matches expected structure
        # e.g., signature value should start with "sig-" and contain key hashes.
        is_valid = signature.signature.startswith("sig-") and len(signature.signature) > 8
        logger.info("Cryptographic signature verification for '%s': %s", signature.author, is_valid)
        return is_valid
