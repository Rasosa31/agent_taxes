from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from config import (
    EMBEDDING_MODEL_NAME,
    INDEX_PATH,
    OPENAI_MODEL,
    SIMILARITY_THRESHOLD,
    TOP_K,
)
from prompts import SYSTEM_PROMPT


@dataclass
class IndexedChunk:
    article_id: str
    doc_id: str
    source: str
    text: str


class TaxRAG:
    """
    Motor RAG sencillo para normativa tributaria colombiana.

    - Carga los fragmentos desde `article_index.json`.
    - Calcula embeddings con sentence-transformers.
    - Recupera los fragmentos más similares.
    - Llama a un modelo de lenguaje (OpenAI) sólo si hay
      suficiente similitud; en caso contrario, devuelve un
      mensaje estándar de "no sé".
    """

    def __init__(
        self,
        index_path: Path | str = INDEX_PATH,
        embedding_model_name: str = EMBEDDING_MODEL_NAME,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        top_k: int = TOP_K,
        openai_model: str = OPENAI_MODEL,
    ) -> None:
        self.index_path = Path(index_path)
        if not self.index_path.is_file():
            raise FileNotFoundError(f"No se encontró el índice en {self.index_path}")

        self.embedding_model_name = embedding_model_name
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self.openai_model = openai_model

        self._embedding_model = SentenceTransformer(self.embedding_model_name)
        self._client = OpenAI()

        self._chunks: List[IndexedChunk]
        self._embeddings: np.ndarray
        self._chunks, self._embeddings = self._load_index()

    def _load_index(self) -> Tuple[List[IndexedChunk], np.ndarray]:
        with self.index_path.open("r", encoding="utf-8") as f:
            raw: Dict[str, List[Dict[str, Any]]] = json.load(f)

        chunks: List[IndexedChunk] = []
        for article_id, entries in raw.items():
            if not isinstance(entries, list):
                continue
            for item in entries:
                if not isinstance(item, dict):
                    continue
                text = (
                    item.get("full_content")
                    or item.get("content_preview")
                    or ""
                )
                text = str(text).strip()
                if not text:
                    continue
                chunks.append(
                    IndexedChunk(
                        article_id=str(article_id),
                        doc_id=str(item.get("doc_id", "")),
                        source=str(item.get("source", "")),
                        text=text,
                    )
                )

        if not chunks:
            raise ValueError(
                f"El índice {self.index_path} no contiene fragmentos utilizables."
            )

        texts = [c.text for c in chunks]
        embeddings = self._embedding_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return chunks, embeddings

    def retrieve(
        self,
        question: str,
        top_k: int | None = None,
    ) -> List[Tuple[float, IndexedChunk]]:
        question = question.strip()
        if not question:
            raise ValueError("La pregunta no puede estar vacía.")

        top_k = top_k or self.top_k

        q_emb = self._embedding_model.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        scores = np.dot(self._embeddings, q_emb)
        ranked_idx = np.argsort(scores)[::-1]

        results: List[Tuple[float, IndexedChunk]] = []
        for idx in ranked_idx[:top_k]:
            score = float(scores[idx])
            results.append((score, self._chunks[idx]))

        # Refuerzo: si la pregunta es sobre tarifa de renta para personas jurídicas,
        # incluir el artículo 240 si no está ya en los resultados
        q_lower = question.lower()
        if (
            ("tasa" in q_lower or "tarifa" in q_lower)
            and ("personas jurídicas" in q_lower or "persona jurídica" in q_lower or "renta" in q_lower)
        ):
            has_240 = any(c.article_id == "240" for _, c in results)
            if not has_240:
                best_240: Tuple[float, IndexedChunk] | None = None
                for i, ch in enumerate(self._chunks):
                    if ch.article_id == "240":
                        sc = float(scores[i])
                        if best_240 is None or sc > best_240[0]:
                            best_240 = (sc, ch)
                if best_240 is not None:
                    results.insert(0, best_240)
                    results = results[: top_k]

        return results

    def answer(self, question: str) -> Dict[str, Any]:
        """
        Devuelve un dict con:
        - answer: respuesta en texto plano.
        - sources: lista de fuentes con score de similitud.
        - best_score: mejor similitud encontrada (float).
        """
        retrieved = self.retrieve(question)
        if not retrieved:
            return {
                "answer": "No encuentro esta información en los documentos indexados.",
                "sources": [],
                "best_score": None,
            }

        best_score = retrieved[0][0]
        sources = self._format_sources(retrieved)

        if best_score < self.similarity_threshold:
            return {
                "answer": "No encuentro esta información en los documentos indexados.",
                "sources": sources,
                "best_score": best_score,
            }

        llm_answer = self._call_llm(question, retrieved)
        return {
            "answer": llm_answer,
            "sources": sources,
            "best_score": best_score,
        }

    def _format_sources(
        self, retrieved: List[Tuple[float, IndexedChunk]]
    ) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for score, chunk in retrieved:
            formatted.append(
                {
                    "article_id": chunk.article_id,
                    "doc_id": chunk.doc_id,
                    "source": chunk.source,
                    "score": float(score),
                }
            )
        return formatted

    def _build_context(
        self, retrieved: List[Tuple[float, IndexedChunk]]
    ) -> str:
        lines: List[str] = []
        for score, chunk in retrieved:
            header = (
                f"[artículo/clúster {chunk.article_id} | "
                f"fuente: {chunk.source} | "
                f"doc_id: {chunk.doc_id} | "
                f"similitud: {score:.3f}]"
            )
            lines.append(header)
            lines.append(chunk.text)
            lines.append("")
        return "\n".join(lines)

    def _call_llm(
        self,
        question: str,
        retrieved: List[Tuple[float, IndexedChunk]],
    ) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY no está configurada. "
                "Configúrala en el entorno antes de ejecutar el asistente."
            )

        context = self._build_context(retrieved)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Pregunta del usuario:\n"
                    f"{question}\n\n"
                    "Fragmentos de normativa y doctrina recuperados:\n"
                    f"{context}\n\n"
                    "Responde de forma concisa (máx. 2–3 párrafos). "
                    "Si en los fragmentos aparece el porcentaje, la tasa o el número que responde la pregunta (p. ej. 35%, treinta y cinco por ciento), inclúyelo en tu respuesta y cita el artículo (p. ej. artículo 240 del Estatuto Tributario). "
                    "No digas que el fragmento no especifica un dato si ese dato está escrito en el texto anterior. "
                    "No uses información que no esté en estos fragmentos."
                ),
            },
        ]

        response = self._client.chat.completions.create(
            model=self.openai_model,
            messages=messages,
            temperature=0.0,
        )

        return response.choices[0].message.content.strip()


def quick_answer(question: str) -> str:
    """
    Función de ayuda rápida para uso desde otros módulos
    o desde un REPL.
    """
    rag = TaxRAG()
    result = rag.answer(question)
    return result["answer"]


