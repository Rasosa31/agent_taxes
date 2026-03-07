from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict, List

from pypdf import PdfReader

from config import INDEX_PATH


def _extract_text_from_pdf_bytes(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts: List[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        text = text.strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _chunk_text(text: str, max_chars: int = 4000, overlap: int = 400) -> List[str]:
    text = text.strip()
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + max_chars, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = max(0, end - overlap)

    return chunks


def _load_index(index_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    if not index_path.is_file():
        return {}
    with index_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"El índice en {index_path} no tiene formato dict.")
    return raw


def _save_index(index: Dict[str, List[Dict[str, Any]]], index_path: Path) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def update_index_with_uploads(
    uploaded_files: List[Any],
    index_path: Path | None = None,
) -> Dict[str, int]:
    """
    Actualiza `article_index.json` a partir de archivos subidos desde Streamlit.

    - Soporta actualmente `.pdf` y `.txt`.
    - Cada fragmento generado se agrega como una entrada nueva en el índice.
    - La clave de primer nivel será de la forma `user::<nombre_archivo>::n`.
    """
    index_path = index_path or INDEX_PATH
    index = _load_index(index_path)

    n_files = 0
    n_chunks = 0

    for uf in uploaded_files:
        filename = getattr(uf, "name", "documento_sin_nombre")
        name_lower = filename.lower()
        try:
            data = uf.read()
        except Exception:  # noqa: BLE001
            # fallback para UploadedFile de Streamlit
            data = getattr(uf, "getvalue", lambda: b"")()

        if not data:
            continue

        if name_lower.endswith(".pdf"):
            text = _extract_text_from_pdf_bytes(data)
        elif name_lower.endswith(".txt"):
            text = data.decode("utf-8", errors="ignore")
        else:
            # Tipo no soportado; se ignora silenciosamente
            continue

        chunks = _chunk_text(text)
        if not chunks:
            continue

        n_files += 1

        base = Path(filename).stem
        for i, chunk in enumerate(chunks):
            article_id = f"user::{base}::{i}"
            entry = {
                "doc_id": f"{filename}_{i}",
                "source": filename,
                "content_preview": chunk[:500],
                "full_content": chunk,
            }
            bucket = index.setdefault(article_id, [])
            bucket.append(entry)
            n_chunks += 1

    if n_chunks > 0:
        _save_index(index, index_path)

    return {"n_files": n_files, "n_chunks": n_chunks}

