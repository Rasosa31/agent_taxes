Quickstart (Streamlit + Secrets)
================================

1) Crear y activar entorno

```bash
cd /Users/ramirososa/agent_taxes
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2) Configurar la key de OpenAI (elige una opción)

Opción A: variable de entorno

```bash
export OPENAI_API_KEY="TU_OPENAI_API_KEY_AQUI"
```

Opción B: Streamlit secrets (recomendado)

```bash
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<'EOF'
OPENAI_API_KEY = "TU_OPENAI_API_KEY_AQUI"
EOF
```

3) Ejecutar

```bash
./run.sh
```

Abre la URL que imprime Streamlit (normalmente `http://localhost:8501`).

