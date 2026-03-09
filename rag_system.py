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
    INITIAL_TOP_K,
    RERANKER_MODEL_NAME,
    VECTOR_WEIGHT,
    BM25_WEIGHT,
)
from prompts import SYSTEM_PROMPT
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
import re


@dataclass
class IndexedChunk:
    article_id: str
    doc_id: str
    source: str
    text: str
    metadata: Dict[str, str] = None


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

        self._embedding_model = SentenceTransformer(self.embedding_model_name, device="cpu")
        self._reranker_model = CrossEncoder(RERANKER_MODEL_NAME, device="cpu")
        self._client = OpenAI()

        self._chunks: List[IndexedChunk]
        self._embeddings: np.ndarray
        self._bm25: BM25Okapi
        self._chunks, self._embeddings, self._bm25 = self._load_index()

    def _load_index(self) -> Tuple[List[IndexedChunk], np.ndarray, BM25Okapi]:
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
                        metadata=item.get("metadata", {})
                    )
                )

        if not chunks:
            raise ValueError(
                f"El índice {self.index_path} no contiene fragmentos utilizables."
            )

        # El modelo intfloat/multilingual-e5-small requiere prefijo "passage: "
        texts_for_embedding = [f"passage: {c.text}" for c in chunks]
        embeddings = self._embedding_model.encode(
            texts_for_embedding,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        texts = [c.text for c in chunks]
        tokenized_corpus = [text.lower().split() for text in texts]
        bm25 = BM25Okapi(tokenized_corpus)

        return chunks, embeddings, bm25

    def _rewrite_query(self, query: str) -> str:
        """
        Usa un LLM rápido y pequeño para expandir la pregunta del usuario con sinónimos y términos técnicos.
        """
        try:
            expansion_prompt = (
                "Eres un experto en impuestos de Colombia. "
                "Reescribe la siguiente consulta de un usuario para que sea óptima para un motor de búsqueda vectorial (RAG) sobre el Estatuto Tributario y normatividad DIAN. "
                "Incluye sinónimos legales, el número del artículo si se menciona, y los conceptos técnicos relevantes. "
                "NO des la respuesta a la pregunta, SOLAMENTE devuelve la consulta reescrita y expandida en una sola línea.\n\n"
                f"Consulta original: {query}"
            )
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": expansion_prompt}],
                temperature=0.0,
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Warning: Query rewriting failed ({e}). Usando query original.")
            return query

    def retrieve(
        self,
        question: str,
        top_k: int | None = None,
    ) -> List[Tuple[float, IndexedChunk]]:
        question = question.strip()
        if not question:
            raise ValueError("La pregunta no puede estar vacía.")

        # Expansión de Query usando LLM
        expanded_query = self._rewrite_query(question)
        print(f"Query original: {question}\nQuery expandida: {expanded_query}")

        final_top_k = top_k or self.top_k
        initial_k = min(INITIAL_TOP_K, len(self._chunks))

        # 1. Búsqueda Vectorial
        # El modelo intfloat/multilingual-e5-small requiere prefijo "query: "
        q_emb = self._embedding_model.encode(
            [f"query: {expanded_query}"],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        vector_scores = np.dot(self._embeddings, q_emb)
        if vector_scores.size > 0:
            v_max = np.max(vector_scores)
            v_min = np.min(vector_scores)
            if v_max > v_min:
                vector_scores = (vector_scores - v_min) / (v_max - v_min)
            else:
                vector_scores = np.zeros_like(vector_scores)

        # 2. Búsqueda BM25 (Palabras Clave)
        # Buscar si el usuario mencionó un artículo explícitamente en la query original o expandida
        # ej "artículo 475" o "art 475"
        art_match = re.search(r"(?i)art[íi]culo\s+(\d+(?:-\d+)?)", question + " " + expanded_query)
        target_article = art_match.group(1) if art_match else None
        
        tokenized_q = expanded_query.lower().split()
        bm25_scores = self._bm25.get_scores(tokenized_q)
        if bm25_scores.size > 0:
            b_max = np.max(bm25_scores)
            b_min = np.min(bm25_scores)
            if b_max > b_min:
                bm25_scores = (bm25_scores - b_min) / (b_max - b_min)
            else:
                bm25_scores = np.zeros_like(bm25_scores)
                
        # Bono manual masivo si el metadata "articulo" coincide exactamente
        if target_article:
            for i, chunk in enumerate(self._chunks):
                if chunk.metadata and chunk.metadata.get("articulo") == target_article:
                    bm25_scores[i] += 2.0  # Massive score boost for exact metadata match

        # 3. Combinación (híbrida)
        combined_scores = VECTOR_WEIGHT * vector_scores + BM25_WEIGHT * bm25_scores
        
        ranked_idx = np.argsort(combined_scores)[::-1][:initial_k]
        candidates = [self._chunks[i] for i in ranked_idx]

        if not candidates:
            return []
            
        # 4. Re-Ranking con Cross-Encoder
        # Para rankear se recomienda comparar con la query condensada en lugar de la inmensa, pero probaremos con ambas
        cross_inp = [[question, c.text] for c in candidates]
        cross_scores = self._reranker_model.predict(cross_inp)
        
        reranked = [
            (float(score), candidate) 
            for score, candidate in zip(cross_scores, candidates)
        ]
        reranked.sort(key=lambda x: x[0], reverse=True)

        return reranked[:final_top_k]

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


