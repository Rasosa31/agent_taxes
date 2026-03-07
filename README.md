Asistente RAG sobre normativa tributaria colombiana
===================================================

Este proyecto implementa un asistente de preguntas y respuestas sobre
impuestos en Colombia usando RAG (Retrieval-Augmented Generation).

- El índice de normativa está en `vectorstore/article_index.json`.
- La búsqueda semántica se hace con `sentence-transformers`.
- La respuesta final se genera con un modelo de OpenAI.
- El sistema está configurado para **no responder** cuando la
  información no se encuentra en los documentos indexados.

Requisitos
----------

- Python 3.12 (recomendado, consistente con el `venv` existente).
- Dependencias de `requirements.txt`.
- Variable de entorno `OPENAI_API_KEY` con una clave válida de OpenAI.

Instalación rápida
------------------

Desde la raíz del proyecto:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Ejecución (CLI)
---------------

```bash
export OPENAI_API_KEY="TU_OPENAI_API_KEY_AQUI"
./run.sh
```

Luego escribe tus preguntas sobre normativa tributaria colombiana,
por ejemplo:

```text
¿Cómo se determina la renta bruta en la enajenación de activos según el artículo 90?
```

Si el sistema no encuentra información suficientemente relacionada en
los documentos indexados, responderá exactamente:

```text
No encuentro esta información en los documentos indexados.
```

Diagnóstico de recuperación
---------------------------

Para inspeccionar qué fragmentos se están recuperando y sus
similitudes, puedes ejecutar:

```bash
python diagnostico.py "pregunta sobre el artículo 90 del Estatuto Tributario"
```

Esto ayuda a ajustar el umbral de similitud definido en `config.py`
(`SIMILARITY_THRESHOLD`).

