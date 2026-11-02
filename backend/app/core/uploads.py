"""Guardado seguro de archivos - Operativa.ia

Aún no hay rutas de subida. Este módulo queda listo para los documentos de la base de conocimiento.
"""

import secrets
from pathlib import Path

from app.core.config import BACKEND_DIR

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"
WEB_ROOTS = (BACKEND_DIR.parent / "frontend",)

_PDF = ("application/pdf", b"%PDF-")
ALLOWED_TYPES = {
    ".pdf": _PDF,
    ".txt": ("text/plain", None),
    ".md": ("text/markdown", None),
}


class UploadRejected(ValueError):
    """El archivo no cumple las reglas de subida."""


def _is_plain_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def save_upload(data: bytes, filename: str, content_type: str, dest_dir: Path = UPLOAD_DIR) -> Path:
    """Valida tamaño, extensión, tipo MIME y firma; guarda con un nombre aleatorio."""
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise UploadRejected("Tamaño de archivo no permitido.")

    # Path(...).suffix solo mira el último componente, así que "a.pdf.exe" queda como .exe
    extension = Path(filename.replace("\\", "/")).suffix.lower()
    if extension not in ALLOWED_TYPES:
        raise UploadRejected("Extensión no permitida.")

    mime, magic = ALLOWED_TYPES[extension]
    if content_type.split(";")[0].strip().lower() != mime:
        raise UploadRejected("Tipo de archivo no permitido.")
    if magic is not None and not data.startswith(magic):
        raise UploadRejected("El contenido no coincide con el tipo de archivo.")
    if magic is None and not _is_plain_text(data):
        raise UploadRejected("El contenido no coincide con el tipo de archivo.")

    dest_dir = dest_dir.resolve()
    if any(dest_dir.is_relative_to(root.resolve()) for root in WEB_ROOTS):
        raise UploadRejected("El destino no puede estar dentro de la carpeta web.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{secrets.token_hex(16)}{extension}"
    target.touch(mode=0o600, exist_ok=False)
    target.write_bytes(data)
    return target
