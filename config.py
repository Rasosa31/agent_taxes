from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Ruta al índice de fragmentos de normativa
INDEX_PATH: Path = BASE_DIR / "vectorstore" / "article_index.json"

# Modelo de embeddings para búsqueda semántica
EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"

# Número máximo de fragmentos recuperados para una pregunta
# (más fragmentos ayudan a que el LLM vea artículos clave como el 240)
TOP_K: int = 10

# Umbral mínimo de similitud coseno para considerar que
# "hay información suficiente" en los documentos.
SIMILARITY_THRESHOLD: float = 0.45

# Modelo de lenguaje a usar para la respuesta final.
# Debes tener configurada la variable de entorno OPENAI_API_KEY.
OPENAI_MODEL: str = "gpt-4.1-mini"


