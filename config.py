from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Rutas y modelos
INDEX_PATH: Path = BASE_DIR / "vectorstore" / "article_index.json"
EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-small"
RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"

# Modelo de Tokenización
TOKENIZER_MODEL: str = "cl100k_base"  # Modelo de OpenAI usado por tiktoken

# Parámetros de Búsqueda
# Número de fragmentos a recuperar en la fase inicial (Vector + BM25)
INITIAL_TOP_K: int = 20
# Número final de fragmentos tras el re-ranking
TOP_K: int = 5

# Pesos para la búsqueda híbrida (opcional si se usa Reciprocal Rank Fusion, 
# pero útil para combinación lineal simple)
VECTOR_WEIGHT: float = 0.5
BM25_WEIGHT: float = 0.5

# Umbral mínimo de similitud coseno (ya no se usa estrictamente igual tras el re-ranking, 
# pero puede aplicar a la puntuación final)
SIMILARITY_THRESHOLD: float = 0.0

# Modelo LLM
OPENAI_MODEL: str = "gpt-4o-mini"

