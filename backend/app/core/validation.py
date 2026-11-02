"""Validación de entradas - Operativa.ia"""

import unicodedata
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints


def clean_text(value):
    """Normaliza el texto y elimina caracteres de control e invisibles (conserva \\n y \\t)."""
    if not isinstance(value, str):
        return value
    normalized = unicodedata.normalize("NFC", value)
    return "".join(
        ch for ch in normalized if ch in "\n\t" or unicodedata.category(ch) not in {"Cc", "Cf", "Cs", "Co"}
    ).strip()


def CleanStr(min_length: int = 1, max_length: int = 255):
    return Annotated[
        str,
        BeforeValidator(clean_text),
        StringConstraints(min_length=min_length, max_length=max_length),
    ]


class StrictModel(BaseModel):
    """Rechaza campos desconocidos y conversiones implícitas de tipo."""

    model_config = ConfigDict(extra="forbid", strict=True)


def is_safe_https_url(url) -> bool:
    """Solo acepta enlaces https con dominio y sin credenciales incrustadas."""
    if not isinstance(url, str) or any(ord(c) <= 32 for c in url):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme == "https" and bool(parts.hostname) and not parts.username
