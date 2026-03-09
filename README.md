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
- Una clave válida de OpenAI configurada como `OPENAI_API_KEY` (ver “Secrets”).

Instalación rápida
------------------

Desde la raíz del proyecto:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Secrets (OPENAI_API_KEY)
------------------------

Este proyecto **no guarda claves en archivos del repo**. Hay dos formas recomendadas:

1) Variable de entorno (local)

```bash
export OPENAI_API_KEY="TU_OPENAI_API_KEY_AQUI"
```

2) Secrets de Streamlit (local o deploy)

- Crea el archivo `.streamlit/secrets.toml` (este archivo está ignorado por git):

```toml
OPENAI_API_KEY = "TU_OPENAI_API_KEY_AQUI"
```

Ejecución (Streamlit)
---------------------

```bash
./run.sh
```

La app abrirá (o te mostrará) una URL local, típicamente `http://localhost:8501`.
Luego escribe tus preguntas sobre normativa tributaria colombiana, por ejemplo:

```text
¿Cómo se determina la renta bruta en la enajenación de activos según el artículo 90?
```

Si el sistema no encuentra información suficientemente relacionada en
los documentos indexados, responderá exactamente:

```text
No encuentro esta información en los documentos indexados.
```

Indexación desde la app
-----------------------

En la barra lateral puedes **subir documentos (`.pdf` / `.txt`)** y presionar
“Indexar documentos” para añadirlos al índice existente (`vectorstore/article_index.json`).

Además, en la pestaña **Gestionar Archivos**, puedes revisar qué archivos tienes almacenados localmente y eliminarlos, lo que actualizará tu base de datos y limpiará recursos innecesarios.


