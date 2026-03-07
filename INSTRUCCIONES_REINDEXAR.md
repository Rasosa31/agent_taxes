Instrucciones para reindexar documentos
=======================================

Actualmente el proyecto incluye un índice preconstruido en:

- `vectorstore/article_index.json`

Ese archivo contiene fragmentos de normativa (texto completo) ya
segmentados. No incluye embeddings; estos se calculan en memoria
cada vez que se inicializa el motor RAG (`TaxRAG` en `rag_system.py`).

Flujo general para reindexar
----------------------------

1. **Preparar las fuentes**  
   - Coloca los nuevos documentos (por ejemplo, PDFs del Estatuto
     Tributario, leyes, decretos, conceptos DIAN, etc.) en una
     carpeta de trabajo, por ejemplo `data/`.

2. **Extraer y segmentar texto**  
   - Usa una herramienta de extracción de texto desde PDF/HTML a
     texto plano (por ejemplo, `pypdf`, `pdfplumber` o similar).
   - Segmenta el texto en fragmentos manejables (por ejemplo, por
     artículo, por encabezados o por bloques de N párrafos).

3. **Construir el `article_index.json`**  
   - Genera un diccionario de la forma:

     ```json
     {
       "90": [
         {
           "doc_id": "estatuto_tributario.pdf_...",
           "source": "estatuto_tributario.pdf",
           "content_preview": "Primeros caracteres del fragmento...",
           "full_content": "Texto completo del fragmento..."
         }
       ],
       "91": [
         ...
       ]
     }
     ```

   - La clave de primer nivel (`"90"`, `"91"`, etc.) puede ser el
     número de artículo, capítulo u otro identificador lógico.

4. **Sobrescribir el índice actual**  
   - Una vez generado el nuevo `article_index.json`, reemplaza el
     archivo existente en `vectorstore/`.
   - La próxima vez que ejecutes `app.py` o `run.sh`, el motor RAG
     recalculará los embeddings a partir del nuevo contenido.

Notas
-----

- El umbral de similitud que define si el sistema responde o no con
  base en los documentos se configura en `config.py`
  (`SIMILARITY_THRESHOLD`).
- Si quieres que implementemos un script automático de reindexación
  (por ejemplo, `scripts/reindex.py` que lea PDFs y genere el JSON),
  se puede añadir fácilmente sobre esta base.

