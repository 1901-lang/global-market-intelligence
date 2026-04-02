"""Security utilities: input sanitisation and Fernet field-level encryption.

Environment variables
---------------------
ENCRYPTION_KEY   Base-64 URL-safe Fernet key (32 bytes → 44 chars).
                 Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
                 If unset, encrypt_field / decrypt_field are no-ops.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt-injection / input sanitisation
# ---------------------------------------------------------------------------

_MAX_INPUT_LENGTH = 2000

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r, re.IGNORECASE | re.DOTALL)
    for r in [
        r"ignore\s+(all\s+)?(previous|prior|above|earlier|preceding)\s+(instructions?|prompts?|directives?|text)",
        r"forget\s+(everything|all)\s+(above|before|prior)",
        r"(act|pretend|behave)\s+as\s+(if\s+you('re|are)\s+)?(?:a\s+)?(?:different|new|another)\s+(?:ai|model|assistant|system)",
        r"\bjailbreak\b",
        r"\bDAN\s+(?:mode|prompt)\b",
        r"<\s*/?\s*(?:system|user|assistant)\s*>",
        r"\[SYSTEM\]",
        r"override\s+(all\s+)?(?:safety|security|content)\s+(?:guidelines?|filters?|restrictions?)",
        r"you\s+are\s+now\s+(?:in\s+)?(?:developer|unrestricted|unfiltered)\s+mode",
    ]
]


def sanitize_input(text: str, max_length: int = _MAX_INPUT_LENGTH) -> str:
    """Strip potential prompt-injection patterns and enforce a length limit.

    Raises ``ValueError`` when a suspicious pattern is detected so callers can
    return a 400 to the client instead of forwarding tainted input to the LLM.
    """
    if not text:
        return text
    text = text[:max_length]
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning("Potential prompt injection detected — input rejected")
            raise ValueError("Input contains disallowed content")
    return text.strip()


# ---------------------------------------------------------------------------
# Fernet field-level encryption
# ---------------------------------------------------------------------------

_ENCRYPTION_KEY_RAW: str = os.getenv("ENCRYPTION_KEY", "")
_fernet: Optional[object] = None


def _get_fernet():
    global _fernet
    if _fernet is None and _ENCRYPTION_KEY_RAW:
        try:
            from cryptography.fernet import Fernet  # type: ignore

            _fernet = Fernet(_ENCRYPTION_KEY_RAW.encode())
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to initialise Fernet encryption: %s", exc)
    return _fernet


def encrypt_field(text: str) -> str:
    """Encrypt *text* with Fernet symmetric encryption.

    Returns *text* unchanged when ``ENCRYPTION_KEY`` is not configured so the
    application works in development without any key material.
    """
    fernet = _get_fernet()
    if not fernet or not text:
        return text
    try:
        return fernet.encrypt(text.encode()).decode()  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning("encrypt_field failed: %s", exc)
        return text


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted field.

    Returns *ciphertext* unchanged when the key is missing or the value was
    never encrypted (backwards-compatible with unencrypted historical rows).
    """
    fernet = _get_fernet()
    if not fernet or not ciphertext:
        return ciphertext
    try:
        return fernet.decrypt(ciphertext.encode()).decode()  # type: ignore[union-attr]
    except Exception:
        return ciphertext
