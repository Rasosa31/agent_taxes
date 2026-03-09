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


import re
import tiktoken
from config import INDEX_PATH, TOKENIZER_MODEL

def _get_tokenizer():
    return tiktoken.get_encoding(TOKENIZER_MODEL)

def _fallback_chunk_text(text: str, max_tokens: int = 600, overlap_tokens: int = 100) -> List[str]:
    text = text.strip()
    if not text:
        return []

    tokenizer = _get_tokenizer()
    tokens = tokenizer.encode(text)

    chunks: List[str] = []
    start = 0
    length = len(tokens)

    while start < length:
        end = min(start + max_tokens, length)
        chunk_tokens = tokens[start:end]
        chunk = tokenizer.decode(chunk_tokens).strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = max(0, end - overlap_tokens)

    return chunks


def _split_long_article(article_number: str, article_full_text: str) -> List[Dict[str, str]]:
    """Subdivide un artículo largo asegurando que cada pedazo tenga el contexto del artículo."""
    # Dividir por Parágrafos y/o doble salto de línea
    pattern = r"(?i)(?:^|\n)\s*(par[áa]grafo\s*[0-9]*[.\s]*|transitorio[.\s]*)"
    sub_parts = re.split(pattern, article_full_text)
    
    sub_chunks = []
    
    # sub_parts[0] es texto inicial (generalmente la regla general del artículo)
    base_rule = sub_parts[0].strip()
    if base_rule:
        sub_chunks.append({
            "article_id": article_number, 
            "text": base_rule
        })
        
    for i in range(1, len(sub_parts), 2):
        para_label = sub_parts[i].strip()
        para_text = sub_parts[i+1].strip() if i+1 < len(sub_parts) else ""
        
        combined_text = f"Contexto: Artículo {article_number}. \nSección: {para_label} {para_text}"
        
        # Aún así podría ser muy largo, aplicar un split por tokens como último recurso
        tokenizer = _get_tokenizer()
        if len(tokenizer.encode(combined_text)) > 700:
            frag_chunks = _fallback_chunk_text(combined_text, max_tokens=600, overlap_tokens=100)
            for j, fc in enumerate(frag_chunks):
                sub_chunks.append({
                    "article_id": article_number,
                    "text": fc
                })
        else:
            sub_chunks.append({
                "article_id": article_number,
                "text": combined_text
            })
            
    return sub_chunks


def _chunk_by_article(text: str) -> List[Dict[str, str]]:
    """
    Divide el texto de la normativa en fragmentos estructurados por Artículo.
    Retorna una lista de diccionarios con 'article_id' y 'text' enriquecido con metadatos.
    """
    # Expresión regular para detectar "Artículo XX." "ARTICULO XX." "Art. XX."
    # Captura el número (que puede incluir letras o guiones, ej. 114-1)
    pattern = r"(?i)(?:^|\n)\s*(?:art[íi]culo|art\.)\s+([0-9]+(?:-[0-9]+)?)[.\s]"
    
    parts = re.split(pattern, text)
    chunks = []
    
    preamble = parts[0].strip()
    if len(preamble) > 100:
        raw_preamble = _fallback_chunk_text(preamble)
        for i, rp in enumerate(raw_preamble):
            chunks.append({"article_id": "preambulo", "text": rp})
            
    for i in range(1, len(parts), 2):
        article_number = parts[i].strip()
        article_text = parts[i+1].strip() if i+1 < len(parts) else ""
        
        full_text = f"Artículo {article_number}. {article_text}"
        
        tokenizer = _get_tokenizer()
        if len(tokenizer.encode(full_text)) > 700:
            sub_chunks = _split_long_article(article_number, full_text)
            chunks.extend(sub_chunks)
        else:
            chunks.append({"article_id": article_number, "text": full_text})
            
    # Fallback si no hay artículos (ej. conceptos, sentencias)
    if not chunks and text.strip():
        raw_chunks = _fallback_chunk_text(text)
        for i, rc in enumerate(raw_chunks):
            chunks.append({"article_id": f"gen_{i}", "text": rc})
            
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

        chunks = _chunk_by_article(text)
        if not chunks:
            continue

        n_files += 1

        base = Path(filename).stem
        for i, chunk_dict in enumerate(chunks):
            art_num = chunk_dict["article_id"]
            chunk_txt = chunk_dict["text"]
            
            # Simple heuristic for 'tema': take the first 6-10 words after "Artículo XX. "
            # if we have a clean article.
            tema = ""
            if art_num != "preambulo" and not art_num.startswith("gen_"):
                # Clean up to try to catch the title
                match = re.search(r"(?i)art[íi]culo\s+[\d\-]+\.?\s+([^\.]+)\.", chunk_txt)
                if match:
                    tema = match.group(1).strip()
                else:
                    # just grab the first 10 words as fallback for theme
                    words = chunk_txt.replace(f"Artículo {art_num}.", "").strip().split()
                    tema = " ".join(words[:10])
            
            # Add metadata payload directly to text and index
            # This makes it searchable by exact match and easy to read
            metadata = {
                "articulo": art_num,
                "tema": tema
            }
            
            article_id = f"user::{base}::{art_num}"
            entry = {
                "doc_id": f"{filename}_{i}",
                "source": filename,
                "content_preview": chunk_txt[:500],
                "full_content": chunk_txt,
                "metadata": metadata, # Saved for reference
            }
            bucket = index.setdefault(article_id, [])
            bucket.append(entry)
            n_chunks += 1

    if n_chunks > 0:
        _save_index(index, index_path)

    return {"n_files": n_files, "n_chunks": n_chunks}

def get_all_files(index_path: Path | None = None, docs_dir: Path | str = "documentos") -> List[str]:
    """
    Retorna la lista de archivos disponibles tanto en la carpeta de documentos
    como en el índice actual.
    """
    index_path = index_path or INDEX_PATH
    index = _load_index(index_path)

    files = set()
    # 1. Escanear carpeta de documentos físicos
    docs_path = Path(docs_dir)
    if docs_path.is_dir():
        for file in docs_path.iterdir():
            if file.is_file() and not file.name.startswith("."):
                files.add(file.name)

    # 2. Escanear el índice JSON por "source"
    for bucket in index.values():
        for entry in bucket:
            source = entry.get("source")
            if source:
                files.add(source)

    return sorted(list(files))

def delete_specific_files(filenames: List[str], index_path: Path | None = None, docs_dir: Path | str = "documentos") -> Dict[str, Any]:
    """
    Elimina archivos de forma física de la carpeta de documentos y/o del índice.
    """
    index_path = index_path or INDEX_PATH
    index = _load_index(index_path)

    removed_files_physical = 0
    removed_chunks = 0
    
    # 1. Eliminar archivos físicos
    docs_path = Path(docs_dir)
    if docs_path.is_dir():
        for fname in filenames:
            file_path = docs_path / fname
            if file_path.is_file():
                try:
                    file_path.unlink()
                    removed_files_physical += 1
                except Exception:
                    pass
                
    # 2. Eliminar del índice (cualquier fragmento cuyo "source" esté en la lista)
    keys_to_remove = []
    for k, bucket in index.items():
        # Filtrar bucket para mantener solo las entradas que NO tengan un source a borrar
        new_bucket = [e for e in bucket if e.get("source") not in filenames]
        removed_chunks += len(bucket) - len(new_bucket)
        
        if not new_bucket:
            keys_to_remove.append(k)
        else:
            index[k] = new_bucket

    for k in keys_to_remove:
        del index[k]

    if removed_chunks > 0:
        _save_index(index, index_path)

    return {"removed_physical": removed_files_physical, "removed_chunks": removed_chunks}

