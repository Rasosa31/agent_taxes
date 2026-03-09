from __future__ import annotations

import os

import streamlit as st

from rag_system import TaxRAG
from reindexar import delete_specific_files, get_all_files, update_index_with_uploads


@st.cache_resource
def get_rag() -> TaxRAG:
    return TaxRAG()


def main() -> None:
    st.set_page_config(
        page_title="Asistente tributario RAG",
        layout="wide",
    )

    st.title("Asistente tributario RAG (Colombia)")
    st.markdown(
        "Pregunta sobre **normativa de impuestos colombiana**. "
        "El asistente solo responde si encuentra soporte en los documentos indexados; "
        "en caso contrario responde:\n\n"
        "`No encuentro esta información en los documentos indexados.`"
    )

    if not os.getenv("OPENAI_API_KEY"):
        st.error(
            "No se encontró la variable de entorno `OPENAI_API_KEY`.\n\n"
            "- En local, expórtala antes de ejecutar: "
            "`export OPENAI_API_KEY=\"tu_clave\"`.\n"
            "- En despliegues de Streamlit, configúrala en los *secrets* del proyecto."
        )
        st.stop()

    with st.sidebar:
        st.header("Indexar documentos")
        st.markdown(
            "Sube nuevos documentos de normativa (`.pdf` o `.txt`). "
            "Se añadirán al índice existente."
        )
        uploaded_files = st.file_uploader(
            "Documentos a indexar",
            type=["pdf", "txt"],
            accept_multiple_files=True,
        )
        if st.button("Indexar documentos", use_container_width=True, type="primary"):
            if not uploaded_files:
                st.warning("Primero sube al menos un documento.")
            else:
                with st.spinner("Indexando documentos..."):
                    stats = update_index_with_uploads(uploaded_files)
                    # Limpiamos la caché del motor para que use el nuevo índice
                    get_rag.clear()
                if stats["n_chunks"] > 0:
                    st.success(
                        f"Indexación completada: {stats['n_files']} archivo(s), "
                        f"{stats['n_chunks']} fragmentos añadidos."
                    )
                else:
                    st.info(
                        "No se añadieron fragmentos. "
                        "Verifica que los archivos tengan texto legible."
                    )

    try:
        rag = get_rag()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error inicializando el motor RAG: {exc}")
        st.stop()

    tab_chat, tab_docs = st.tabs(["💬 Consultar Normativa", "📂 Gestionar Archivos"])

    with tab_chat:
        col1, col2 = st.columns([2, 1])

        with col1:
            question = st.text_area(
                "Escribe tu pregunta tributaria",
                placeholder=(
                    "Ejemplo: ¿Cómo se determina la renta bruta en la enajenación de activos "
                    "según el artículo 90?"
                ),
                height=120,
            )
            consultar = st.button("Consultar", type="primary")

        with col2:
            st.markdown("**Parámetros de búsqueda (solo lectura)**")
            st.write(f"- Umbral de similitud: `{rag.similarity_threshold}`")
            st.write(f"- Máx. fragmentos recuperados: `{rag.top_k}`")

        if consultar and question.strip():
            with st.spinner("Buscando en la normativa indexada..."):
                try:
                    result = rag.answer(question)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Error al generar la respuesta: {exc}")
                    return

            st.subheader("Respuesta")
            st.write(result.get("answer", "").strip())

            sources = result.get("sources") or []
            best = result.get("best_score")

            with st.expander("Ver fragmentos y similitudes"):
                if not sources:
                    st.write("No se encontraron fragmentos relevantes.")
                else:
                    st.write("Fragmentos utilizados (ordenados por similitud):")
                    for src in sources:
                        article = src.get("article_id", "?")
                        source_name = src.get("source", "?")
                        doc_id = src.get("doc_id", "")
                        score = src.get("score")
                        score_str = f"{score:.3f}" if isinstance(score, float) else "?"
                        st.write(
                            f"- **Artículo/clúster** `{article}` · **Fuente** `{source_name}` · "
                            f"**doc_id** `{doc_id}` · **similitud** `{score_str}`"
                        )

            if isinstance(best, (float, int)):
                st.caption(f"Mejor similitud encontrada: `{best:.3f}`")

    with tab_docs:
        st.header("Archivos Disponibles")
        st.write("Selecciona los archivos que deseas eliminar de la base de datos (físicos o indexados):")
        
        archivos_disponibles = get_all_files()
        
        if not archivos_disponibles:
            st.info("No hay archivos indexados o disponibles en la carpeta de documentos.")
        else:
            archivos_a_borrar = st.multiselect(
                "Archivos seleccionados para borrar",
                options=archivos_disponibles,
                default=[]
            )
            
            if st.button("Borrar Archivos Seleccionados", type="primary"):
                if not archivos_a_borrar:
                    st.warning("Selecciona al menos un archivo para borrar.")
                else:
                    with st.spinner("Borrando archivos y fragmentos..."):
                        stats = delete_specific_files(archivos_a_borrar)
                        get_rag.clear()
                    
                    st.success(
                        f"Archivos eliminados. "
                        f"Físicos: {stats['removed_physical']}, Fragmentos: {stats['removed_chunks']}."
                    )
                    st.rerun()


if __name__ == "__main__":
    main()



