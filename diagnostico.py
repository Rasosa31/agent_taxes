from __future__ import annotations

import sys
from typing import NoReturn

from rag_system import TaxRAG


def main(argv: list[str] | None = None) -> NoReturn:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            "Uso: python diagnostico.py \"pregunta sobre impuestos\"\n\n"
            "Muestra los fragmentos más similares y sus puntuaciones,\n"
            "sin llamar al modelo de lenguaje.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    question = " ".join(argv).strip()
    rag = TaxRAG()
    retrieved = rag.retrieve(question)

    print(f"Pregunta: {question}\n")
    for score, chunk in retrieved:
        print(
            f"[similitud={score:.3f} | artículo/clúster={chunk.article_id} | "
            f"fuente={chunk.source} | doc_id={chunk.doc_id}]"
        )
        print(chunk.text[:1000])
        print("-" * 80)


if __name__ == "__main__":
    main()


