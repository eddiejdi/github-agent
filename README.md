#  GitHub Agent

Agente AI para interação com repositórios GitHub usando LLM local (Ollama).

##  Funcionalidades

-  Análise de repositórios GitHub
-  Busca de issues e PRs
-  Sugestões de código usando LLM
-  Ações rápidas pré-configuradas

##  Acesso

| Tipo | URL |
|------|-----|
| Local | http://192.168.15.2:8502 |
| Externo | https://homelab-tunnel-sparkling-sun-3565.fly.dev/github |

##  Tecnologias

- **Frontend**: Streamlit
- **LLM**: Ollama (qwen2.5-coder:7b)
- **API**: GitHub REST API

##  Configuração

### Variáveis de Ambiente
\\ash
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=qwen2.5-coder:7b
GITHUB_TOKEN=<seu_token>
\
### Serviço Systemd
\\ash
# Status
sudo systemctl status github-agent

# Logs
journalctl -u github-agent -f

# Reiniciar
sudo systemctl restart github-agent
\
##  Estrutura

\github-agent/
 github_agent_streamlit.py  # App principal
 prompts/                   # Prompts do LLM
 utils/                     # Utilitários
 README.md
\
##  Licença

MIT
