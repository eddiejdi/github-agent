# GitHub Agent 🤖

Agente inteligente que conecta Ollama com GitHub API via linguagem natural.

## Funcionalidades
- 💬 Chat em linguagem natural
- 📂 Listar repositórios, issues, PRs
- 🔍 Buscar repositórios
- 🔐 Autenticação via token

## Stack
- Python 3.11+ / Streamlit / Ollama / GitHub API

## Instalação
```bash
python -m venv venv && source venv/bin/activate
pip install streamlit requests
streamlit run github_agent_streamlit.py --server.port 8502
```

## Licença
MIT
