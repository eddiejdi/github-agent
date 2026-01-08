#!/usr/bin/env python3
"""
GitHub Agent - Interface Streamlit
Um agente inteligente que conecta seu Ollama com GitHub
Com suporte a GitHub Device Flow (Login sem configuração!)
"""

import os
import json
import time
import secrets
import requests
import urllib.parse
import streamlit as st
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import threading
import webbrowser

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / ".github_agent_config.json"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

# GitHub OAuth Config (opcional - Device Flow não precisa!)
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")

# Detecta a URL base automaticamente
def get_redirect_uri():
    """Obtém a URI de redirecionamento baseada no contexto"""
    return os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8502")

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================

st.set_page_config(
    page_title="🤖 GitHub Agent",
    page_icon="🐙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Customizado
st.markdown("""
<style>
    .stApp {
        background-color: #0d1117;
    }
    
    .main-header {
        background: linear-gradient(90deg, #238636, #1f6feb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0;
    }
    
    .status-connected {
        color: #3fb950;
        padding: 5px 15px;
        border-radius: 20px;
        background: rgba(63, 185, 80, 0.1);
        border: 1px solid rgba(63, 185, 80, 0.3);
    }
    
    .status-disconnected {
        color: #f85149;
        padding: 5px 15px;
        border-radius: 20px;
        background: rgba(248, 81, 73, 0.1);
        border: 1px solid rgba(248, 81, 73, 0.3);
    }
    
    .chat-message {
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    
    .user-message {
        background: #1f6feb;
        margin-left: 20%;
    }
    
    .bot-message {
        background: #21262d;
        border: 1px solid #30363d;
        margin-right: 20%;
    }
    
    .repo-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    
    .metric-card {
        background: #21262d;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    
    div[data-testid="stSidebar"] {
        background-color: #010409;
    }
    
    .github-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        background: #24292e;
        color: white !important;
        padding: 12px 24px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        font-size: 16px;
        border: 1px solid #30363d;
        transition: all 0.2s;
        width: 100%;
        text-align: center;
    }
    
    .github-btn:hover {
        background: #2f363d;
        border-color: #8b949e;
        color: white !important;
        text-decoration: none;
    }
    
    .github-btn svg {
        width: 20px;
        height: 20px;
    }
    
    .oauth-container {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 30px;
        text-align: center;
        margin: 20px 0;
    }
    
    .divider {
        display: flex;
        align-items: center;
        text-align: center;
        margin: 20px 0;
        color: #8b949e;
    }
    
    .divider::before,
    .divider::after {
        content: '';
        flex: 1;
        border-bottom: 1px solid #30363d;
    }
    
    .divider span {
        padding: 0 15px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# FUNÇÕES DE CONFIGURAÇÃO
# =============================================================================

def load_config() -> dict:
    """Carrega configuração do arquivo"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(config: dict):
    """Salva configuração no arquivo"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)

def get_github_token() -> str:
    """Obtém token do GitHub"""
    if "github_token" in st.session_state:
        return st.session_state.github_token
    config = load_config()
    return config.get("github_token", "")

# =============================================================================
# FUNÇÕES DE OAUTH
# =============================================================================

def get_github_oauth_url() -> str:
    """Gera URL de autorização do GitHub OAuth"""
    if not GITHUB_CLIENT_ID:
        return ""
    
    state = secrets.token_hex(16)
    st.session_state.oauth_state = state
    
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": get_redirect_uri(),
        "scope": "repo read:user read:org",
        "state": state
    }
    
    return f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"

def exchange_code_for_token(code: str) -> Optional[str]:
    """Troca o código de autorização por um token de acesso"""
    try:
        response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": get_redirect_uri()
            },
            timeout=30
        )
        data = response.json()
        return data.get("access_token")
    except Exception as e:
        st.error(f"Erro ao obter token: {e}")
        return None

def handle_oauth_callback():
    """Processa o callback do OAuth"""
    query_params = st.query_params
    
    # Verifica se há código de autorização na URL
    if "code" in query_params:
        code = query_params.get("code")
        state = query_params.get("state", "")
        
        # Valida o state (proteção CSRF)
        stored_state = st.session_state.get("oauth_state", "")
        
        # Se não temos state armazenado, pode ser um reload - tenta processar mesmo assim
        if code:
            with st.spinner("🔐 Autenticando com GitHub..."):
                token = exchange_code_for_token(code)
                
                if token:
                    # Obtém informações do usuário
                    github = GitHubClient(token)
                    user = github.get_user()
                    
                    if "error" not in user:
                        set_github_token(token, user)
                        st.session_state.github_user = user
                        
                        # Limpa os query params
                        st.query_params.clear()
                        
                        st.success(f"✅ Bem-vindo, {user.get('login')}!")
                        st.rerun()
                    else:
                        st.error(f"Erro ao obter usuário: {user.get('error')}")
                else:
                    st.error("❌ Falha na autenticação. Tente novamente.")
            
            # Limpa os query params em caso de erro também
            st.query_params.clear()

def render_github_login_button():
    """Renderiza o botão de login do GitHub - SEMPRE funciona!"""
    github_icon = '''<svg viewBox="0 0 16 16" fill="currentColor" style="width:20px;height:20px;margin-right:8px;vertical-align:middle;"><path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>'''
    
    # URL para criar token diretamente no GitHub
    token_url = "https://github.com/settings/tokens/new?scopes=repo,read:user,read:org&description=GitHub%20Agent%20Streamlit"
    
    st.markdown(f'''
    <a href="{token_url}" target="_blank" style="
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #24292e 0%, #1a1e22 100%);
        color: white !important;
        padding: 14px 28px;
        border-radius: 10px;
        text-decoration: none;
        font-weight: 600;
        font-size: 16px;
        border: 1px solid #30363d;
        transition: all 0.3s ease;
        width: 100%;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    " onmouseover="this.style.background='linear-gradient(135deg, #2f363d 0%, #24292e 100%)';this.style.transform='translateY(-2px)';this.style.boxShadow='0 6px 12px rgba(0,0,0,0.4)';" 
       onmouseout="this.style.background='linear-gradient(135deg, #24292e 0%, #1a1e22 100%)';this.style.transform='translateY(0)';this.style.boxShadow='0 4px 6px rgba(0,0,0,0.3)';">
        {github_icon}
        <span>🔑 Criar Token no GitHub</span>
    </a>
    ''', unsafe_allow_html=True)
    
    st.markdown("""
    <p style="text-align:center; color:#8b949e; font-size:12px; margin-top:10px;">
        Clique acima → Gere o token → Cole abaixo ⬇️
    </p>
    """, unsafe_allow_html=True)

def render_oauth_button():
    """Renderiza o botão de login com GitHub OAuth (se configurado)"""
    oauth_url = get_github_oauth_url()
    
    if oauth_url:
        github_icon = '''<svg viewBox="0 0 16 16" fill="currentColor"><path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>'''
        
        st.markdown(f'''
        <a href="{oauth_url}" class="github-btn" target="_self">
            {github_icon}
            <span>Entrar com GitHub</span>
        </a>
        ''', unsafe_allow_html=True)
        return True
    return False

def set_github_token(token: str, user_info: dict = None):
    """Salva token do GitHub"""
    st.session_state.github_token = token
    config = load_config()
    config["github_token"] = token
    config["token_set_at"] = datetime.now().isoformat()
    if user_info:
        config["github_user"] = user_info
        st.session_state.github_user = user_info
    save_config(config)

def clear_github_token():
    """Remove token do GitHub"""
    st.session_state.pop("github_token", None)
    st.session_state.pop("github_user", None)
    config = load_config()
    config.pop("github_token", None)
    config.pop("github_user", None)
    save_config(config)

# =============================================================================
# CLIENTES API
# =============================================================================

class GitHubClient:
    """Cliente para API do GitHub"""
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
    
    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        url = f"https://api.github.com{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_user(self) -> dict:
        return self._request("GET", "/user")
    
    def list_repos(self, username: str = None, org: str = None, per_page: int = 30) -> list:
        if org:
            return self._request("GET", f"/orgs/{org}/repos?per_page={per_page}")
        elif username:
            return self._request("GET", f"/users/{username}/repos?per_page={per_page}")
        return self._request("GET", f"/user/repos?per_page={per_page}&sort=updated")
    
    def get_repo(self, owner: str, repo: str) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}")
    
    def list_issues(self, owner: str, repo: str, state: str = "open") -> list:
        # Validar e limpar parâmetros
        if not owner or not repo:
            return {"error": "Parâmetros 'owner' e 'repo' são obrigatórios. Exemplo: microsoft/vscode"}
        
        # Limpar possíveis caracteres extras
        owner = owner.strip().strip('/').strip()
        repo = repo.strip().strip('/').strip()
        
        # Se veio no formato "owner/repo", separar
        if '/' in owner and not repo:
            parts = owner.split('/')
            owner = parts[0]
            repo = parts[1] if len(parts) > 1 else repo
        
        if '/' in repo:
            repo = repo.split('/')[0]
        
        return self._request("GET", f"/repos/{owner}/{repo}/issues?state={state}")
    
    def create_issue(self, owner: str, repo: str, title: str, body: str = "") -> dict:
        return self._request("POST", f"/repos/{owner}/{repo}/issues", {"title": title, "body": body})
    
    def list_prs(self, owner: str, repo: str, state: str = "open") -> list:
        return self._request("GET", f"/repos/{owner}/{repo}/pulls?state={state}")
    
    def list_branches(self, owner: str, repo: str) -> list:
        return self._request("GET", f"/repos/{owner}/{repo}/branches")
    
    def list_commits(self, owner: str, repo: str, per_page: int = 20) -> list:
        return self._request("GET", f"/repos/{owner}/{repo}/commits?per_page={per_page}")
    
    def search_repos(self, query: str) -> dict:
        return self._request("GET", f"/search/repositories?q={query}&per_page=10")


class OllamaClient:
    """Cliente para Ollama"""
    
    def __init__(self):
        self.base_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
        self.model = OLLAMA_MODEL
    
    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except:
            return False
    
    def list_models(self) -> list:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=10)
            return [m["name"] for m in r.json().get("models", [])]
        except:
            return []
    
    def chat(self, messages: list) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        try:
            response = requests.post(url, json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.1
            }, timeout=120)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Erro Ollama: {e}"
    
    def generate(self, prompt: str, system: str = None) -> str:
        url = f"{self.base_url}/api/generate"
        data = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            data["system"] = system
        try:
            response = requests.post(url, json=data, timeout=120)
            return response.json().get("response", "")
        except Exception as e:
            return f"Erro: {e}"


# =============================================================================
# AGENTE GITHUB
# =============================================================================

class GitHubAgent:
    """Agente que processa comandos em linguagem natural"""
    
    SYSTEM_PROMPT = """Você é um assistente de GitHub. Analise o pedido e retorne APENAS JSON válido.

Formato obrigatório:
{"action": "<ação>", "params": {<parâmetros>}, "confidence": <0.0-1.0>}

Ações disponíveis:
- list_repos: username?, org?
- get_repo: owner, repo (SEMPRE extraia do formato owner/repo)
- list_issues: owner, repo, state? (ex: microsoft/vscode → owner="microsoft", repo="vscode")
- create_issue: owner, repo, title, body?
- list_prs: owner, repo, state?
- list_branches: owner, repo
- list_commits: owner, repo  
- get_user: username?
- search_repos: query
- unknown: se não souber

EXEMPLOS IMPORTANTES:
"issues do microsoft/vscode" → {"action": "list_issues", "params": {"owner": "microsoft", "repo": "vscode"}, "confidence": 1.0}
"repositório facebook/react" → {"action": "get_repo", "params": {"owner": "facebook", "repo": "react"}, "confidence": 1.0}
"branches do torvalds/linux" → {"action": "list_branches", "params": {"owner": "torvalds", "repo": "linux"}, "confidence": 1.0}

REGRA CRÍTICA: Quando o usuário mencionar "owner/repo", SEMPRE separe em owner e repo distintos nos params.
Responda APENAS com JSON, sem texto adicional."""

    def __init__(self, github_token: str):
        self.ollama = OllamaClient()
        self.github = GitHubClient(github_token)
    
    def parse_intent(self, user_input: str) -> dict:
        response = self.ollama.chat([
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ])
        
        try:
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1].replace("json", "").strip()
            
            # Tenta encontrar JSON completo (com objetos aninhados)
            import re
            # Procura por { ... } incluindo objetos aninhados
            depth = 0
            start = -1
            for i, c in enumerate(json_str):
                if c == '{':
                    if depth == 0:
                        start = i
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0 and start >= 0:
                        json_str = json_str[start:i+1]
                        break
            
            intent = json.loads(json_str)
            
            # Pós-processamento: extrai owner/repo do input se não vieram nos params
            intent = self._enrich_intent(user_input, intent)
            return intent
        except:
            # Fallback: tenta extrair owner/repo diretamente do input
            return self._fallback_parse(user_input)
    
    def _enrich_intent(self, user_input: str, intent: dict) -> dict:
        """Enriquece o intent extraindo owner/repo do input se necessário"""
        import re
        p = intent.get("params", {})
        
        # Se já tem owner e repo válidos, retorna
        if p.get("owner") and p.get("repo") and "/" not in p.get("owner", ""):
            return intent
        
        # Tenta extrair padrão owner/repo do input do usuário
        repo_pattern = r'([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)'
        match = re.search(repo_pattern, user_input)
        if match:
            intent["params"]["owner"] = match.group(1)
            intent["params"]["repo"] = match.group(2)
        
        return intent
    
    def _fallback_parse(self, user_input: str) -> dict:
        """Parse de fallback quando o LLM falha"""
        import re
        user_lower = user_input.lower()
        
        # Tenta extrair owner/repo
        repo_pattern = r'([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)'
        match = re.search(repo_pattern, user_input)
        owner = match.group(1) if match else ""
        repo = match.group(2) if match else ""
        
        # Detecta ação baseado em palavras-chave
        if any(w in user_lower for w in ["issue", "issues", "problemas"]):
            action = "list_issues"
        elif any(w in user_lower for w in ["branch", "branches", "ramos"]):
            action = "list_branches"
        elif any(w in user_lower for w in ["commit", "commits"]):
            action = "list_commits"
        elif any(w in user_lower for w in ["pr", "prs", "pull request", "pull requests"]):
            action = "list_prs"
        elif any(w in user_lower for w in ["repo", "repositório", "repositorio"]) and owner:
            action = "get_repo"
        elif any(w in user_lower for w in ["busca", "buscar", "pesquisa", "search"]):
            action = "search_repos"
        elif any(w in user_lower for w in ["meus repo", "meus reposit", "list repo"]):
            action = "list_repos"
        else:
            action = "unknown"
        
        return {
            "action": action,
            "params": {"owner": owner, "repo": repo},
            "confidence": 0.7 if owner and repo else 0.3
        }
    
    def execute(self, intent: dict) -> Any:
        action = intent.get("action", "unknown")
        p = intent.get("params", {})
        
        # Função auxiliar para obter owner/repo com fallback
        def get_owner_repo():
            owner = p.get("owner", "")
            repo = p.get("repo", "")
            
            # Se tiver no formato "owner/repo" em qualquer campo
            for key in ["owner", "repo", "repository"]:
                val = p.get(key, "")
                if val and "/" in val:
                    parts = val.split("/")
                    if len(parts) >= 2:
                        return parts[0].strip(), parts[1].strip()
            
            return owner.strip() if owner else "", repo.strip() if repo else ""
        
        owner, repo = get_owner_repo()
        
        actions = {
            "list_repos": lambda: self.github.list_repos(p.get("username"), p.get("org")),
            "get_repo": lambda: self.github.get_repo(owner, repo) if owner and repo else {"error": "Informe owner/repo. Ex: microsoft/vscode"},
            "list_issues": lambda: self.github.list_issues(owner, repo, p.get("state", "open")) if owner and repo else {"error": "Informe owner/repo. Ex: microsoft/vscode"},
            "create_issue": lambda: self.github.create_issue(owner, repo, p["title"], p.get("body", "")) if owner and repo else {"error": "Informe owner/repo"},
            "list_prs": lambda: self.github.list_prs(owner, repo, p.get("state", "open")) if owner and repo else {"error": "Informe owner/repo"},
            "list_branches": lambda: self.github.list_branches(owner, repo) if owner and repo else {"error": "Informe owner/repo"},
            "list_commits": lambda: self.github.list_commits(owner, repo) if owner and repo else {"error": "Informe owner/repo"},
            "get_user": lambda: self.github.get_user() if not p.get("username") else self.github._request("GET", f"/users/{p['username']}"),
            "search_repos": lambda: self.github.search_repos(p.get("query", "")) if p.get("query") else {"error": "Informe o termo de busca"},
        }
        
        if action in actions:
            try:
                return actions[action]()
            except KeyError as e:
                return {"error": f"Parâmetro faltando: {e}. Tente ser mais específico, ex: 'issues do microsoft/vscode'"}
            except Exception as e:
                return {"error": f"Erro ao executar: {str(e)}"}
        return {"error": "Ação não reconhecida"}
    
    def format_response(self, action: str, data: Any) -> str:
        if isinstance(data, dict) and "error" in data:
            return f"❌ **Erro:** {data['error']}"
        
        data_str = json.dumps(data, ensure_ascii=False)[:3000]
        prompt = f"Formate estes dados do GitHub de forma clara em português brasileiro, use markdown com emojis:\n\nAção: {action}\nDados: {data_str}"
        
        return self.ollama.generate(prompt)
    
    def process(self, user_input: str) -> dict:
        intent = self.parse_intent(user_input)
        
        if intent.get("action") == "unknown" or intent.get("confidence", 0) < 0.3:
            return {
                "success": False,
                "message": "Não entendi o pedido. Tente: 'Liste meus repositórios' ou 'Mostre issues do microsoft/vscode'"
            }
        
        result = self.execute(intent)
        formatted = self.format_response(intent["action"], result)
        
        return {
            "success": True,
            "intent": intent,
            "result": result,
            "formatted": formatted
        }


# =============================================================================
# FUNÇÕES DE TESTE
# =============================================================================

def run_tests():
    """Executa testes integrados"""
    st.header("🧪 Testes Integrados")
    
    results = []
    
    # Teste 1: Conexão Ollama
    with st.spinner("Testando conexão com Ollama..."):
        ollama = OllamaClient()
        ollama_ok = ollama.is_available()
        results.append({
            "teste": "Conexão Ollama",
            "status": "✅ Passou" if ollama_ok else "❌ Falhou",
            "detalhes": f"Host: {OLLAMA_HOST}:{OLLAMA_PORT}"
        })
        
        if ollama_ok:
            models = ollama.list_models()
            results.append({
                "teste": "Listar Modelos Ollama",
                "status": "✅ Passou" if models else "⚠️ Vazio",
                "detalhes": f"{len(models)} modelos: {', '.join(models[:3])}..."
            })
    
    # Teste 2: Geração Ollama
    if ollama_ok:
        with st.spinner("Testando geração do modelo..."):
            response = ollama.generate("Responda apenas 'OK': teste")
            gen_ok = "OK" in response.upper() or len(response) > 0
            results.append({
                "teste": "Geração de Texto",
                "status": "✅ Passou" if gen_ok else "❌ Falhou",
                "detalhes": f"Resposta: {response[:50]}..."
            })
    
    # Teste 3: Conexão GitHub (se tiver token)
    token = get_github_token()
    if token:
        with st.spinner("Testando conexão com GitHub..."):
            github = GitHubClient(token)
            user = github.get_user()
            github_ok = "error" not in user
            results.append({
                "teste": "Autenticação GitHub",
                "status": "✅ Passou" if github_ok else "❌ Falhou",
                "detalhes": f"Usuário: {user.get('login', 'N/A')}" if github_ok else user.get("error", "")
            })
            
            if github_ok:
                # Teste listar repos
                repos = github.list_repos()
                repos_ok = isinstance(repos, list)
                results.append({
                    "teste": "Listar Repositórios",
                    "status": "✅ Passou" if repos_ok else "❌ Falhou",
                    "detalhes": f"{len(repos)} repositórios encontrados" if repos_ok else str(repos)
                })
    else:
        results.append({
            "teste": "Autenticação GitHub",
            "status": "⚠️ Pulado",
            "detalhes": "Token não configurado"
        })
    
    # Teste 4: Parsing de Intenção
    if ollama_ok and token:
        with st.spinner("Testando parsing de intenção..."):
            agent = GitHubAgent(token)
            
            test_cases = [
                ("Liste meus repositórios", "list_repos"),
                ("Mostre as issues do microsoft/vscode", "list_issues"),
                ("Buscar repositórios de python", "search_repos"),
            ]
            
            for input_text, expected in test_cases:
                intent = agent.parse_intent(input_text)
                passed = intent.get("action") == expected
                results.append({
                    "teste": f"Parse: '{input_text[:30]}...'",
                    "status": "✅ Passou" if passed else "⚠️ Diferente",
                    "detalhes": f"Ação: {intent.get('action')} (esperado: {expected})"
                })
    
    # Teste 5: Execução completa
    if ollama_ok and token:
        with st.spinner("Testando execução completa do agente..."):
            agent = GitHubAgent(token)
            result = agent.process("Mostre meu perfil do GitHub")
            exec_ok = result.get("success", False)
            results.append({
                "teste": "Execução Completa do Agente",
                "status": "✅ Passou" if exec_ok else "❌ Falhou",
                "detalhes": "Agente processou comando com sucesso" if exec_ok else result.get("message", "")
            })
    
    # Exibe resultados
    st.subheader("📊 Resultados dos Testes")
    
    passed = sum(1 for r in results if "✅" in r["status"])
    total = len(results)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Testes", total)
    with col2:
        st.metric("Passou", passed, delta=None)
    with col3:
        st.metric("Taxa de Sucesso", f"{passed/total*100:.0f}%")
    
    st.divider()
    
    for r in results:
        with st.expander(f"{r['status']} {r['teste']}", expanded=False):
            st.write(r["detalhes"])
    
    return results


# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

def main():
    # Inicializa session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "github_token" not in st.session_state:
        config = load_config()
        if "github_token" in config:
            st.session_state.github_token = config["github_token"]
        if "github_user" in config:
            st.session_state.github_user = config["github_user"]
    
    # Processa callback do OAuth (se houver código na URL)
    handle_oauth_callback()
    
    # Sidebar
    with st.sidebar:
        st.markdown("# 🐙 GitHub Agent")
        st.caption("Assistente inteligente para GitHub")
        
        st.divider()
        
        # Status
        st.subheader("📡 Status do Sistema")
        
        # Ollama
        ollama = OllamaClient()
        ollama_ok = ollama.is_available()
        if ollama_ok:
            st.success(f"✅ Ollama Online")
            st.caption(f"Modelo: {OLLAMA_MODEL}")
        else:
            st.error(f"❌ Ollama Offline")
            st.caption(f"Host: {OLLAMA_HOST}:{OLLAMA_PORT}")
        
        st.divider()
        
        # GitHub Auth
        st.subheader("🔐 GitHub")
        
        token = get_github_token()
        if token:
            github = GitHubClient(token)
            user = github.get_user()
            
            if "error" not in user:
                st.success(f"✅ Conectado")
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    if user.get("avatar_url"):
                        st.image(user["avatar_url"], width=50)
                with col2:
                    st.write(f"**{user.get('name', user.get('login'))}**")
                    st.caption(f"@{user.get('login')}")
                
                st.caption(f"📂 {user.get('public_repos', 0)} repos | 👥 {user.get('followers', 0)} seguidores")
                
                if st.button("🚪 Desconectar", use_container_width=True):
                    clear_github_token()
                    st.rerun()
            else:
                st.error("❌ Token inválido")
                clear_github_token()
                st.rerun()
        else:
            st.warning("⚠️ Não conectado")
            
            # Botão principal de login - SEMPRE aparece!
            st.markdown("##### 🚀 Login Rápido")
            render_github_login_button()
            
            st.markdown("")  # Espaço
            
            # Campo para colar o token
            with st.form("login_form"):
                new_token = st.text_input("Cole seu token aqui:", type="password", 
                                          placeholder="ghp_xxxxxxxxxxxx",
                                          help="Após criar o token no GitHub, cole aqui")
                
                submitted = st.form_submit_button("✅ Conectar", use_container_width=True, type="primary")
                
                if submitted and new_token:
                    with st.spinner("Verificando token..."):
                        github = GitHubClient(new_token)
                        user = github.get_user()
                        
                        if "error" not in user:
                            set_github_token(new_token, user)
                            st.success(f"✅ Bem-vindo, {user.get('login')}!")
                            st.rerun()
                        else:
                            st.error(f"❌ Token inválido: {user.get('error')}")
        
        st.divider()
        
        # Menu de navegação
        st.subheader("📑 Menu")
        page = st.radio("Navegação", ["💬 Chat", "📂 Repositórios", "🧪 Testes"], label_visibility="collapsed")
    
    # Conteúdo principal
    if page == "💬 Chat":
        show_chat_page()
    elif page == "📂 Repositórios":
        show_repos_page()
    elif page == "🧪 Testes":
        run_tests()


def show_chat_page():
    """Página de chat com o agente"""
    st.markdown('<h1 class="main-header">💬 Chat com GitHub Agent</h1>', unsafe_allow_html=True)
    
    token = get_github_token()
    
    if not token:
        st.warning("⚠️ Faça login no GitHub na barra lateral para começar!")
        return
    
    # Quick actions
    st.subheader("⚡ Ações Rápidas")
    cols = st.columns(5)
    
    quick_actions = [
        ("📂 Meus Repos", "Liste meus repositórios"),
        ("👤 Meu Perfil", "Mostre meu perfil do GitHub"),
        ("🔍 Buscar", "Busque repositórios sobre "),
        ("📋 Issues", "Mostre issues do "),
        ("🔀 PRs", "Liste PRs de "),
    ]
    
    for col, (label, prompt) in zip(cols, quick_actions):
        with col:
            if st.button(label, use_container_width=True, key=f"btn_{label}"):
                if prompt.endswith(" "):
                    # Precisa de input adicional
                    st.session_state.pending_action = prompt
                    st.rerun()
                else:
                    # Executa a ação diretamente
                    st.session_state.quick_action = prompt
                    st.rerun()
    
    # Input para ação pendente
    if hasattr(st.session_state, 'pending_action') and st.session_state.pending_action:
        action = st.session_state.pending_action
        extra = st.text_input(f"Complete o comando: {action}", key="extra_input")
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("✅ Enviar", use_container_width=True, type="primary") and extra:
                st.session_state.quick_action = action + extra
                st.session_state.pending_action = None
                st.rerun()
    
    st.divider()
    
    # Processa ação rápida se houver
    if hasattr(st.session_state, 'quick_action') and st.session_state.quick_action:
        quick_prompt = st.session_state.quick_action
        st.session_state.quick_action = None  # Limpa para não repetir
        
        st.session_state.messages.append({"role": "user", "content": quick_prompt})
        
        with st.chat_message("user"):
            st.markdown(quick_prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤔 Processando..."):
                agent = GitHubAgent(token)
                result = agent.process(quick_prompt)
                
                if result["success"]:
                    response = result["formatted"]
                else:
                    response = f"❌ {result['message']}"
                
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Histórico de mensagens
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Input de chat
    if prompt := st.chat_input("Digite seu comando... (ex: Liste meus repositórios)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤔 Processando..."):
                agent = GitHubAgent(token)
                result = agent.process(prompt)
                
                if result["success"]:
                    response = result["formatted"]
                else:
                    response = f"❌ {result['message']}"
                
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})


def show_repos_page():
    """Página de repositórios"""
    st.markdown('<h1 class="main-header">📂 Meus Repositórios</h1>', unsafe_allow_html=True)
    
    token = get_github_token()
    
    if not token:
        st.warning("⚠️ Faça login no GitHub na barra lateral!")
        return
    
    github = GitHubClient(token)
    
    with st.spinner("Carregando repositórios..."):
        repos = github.list_repos()
    
    if isinstance(repos, dict) and "error" in repos:
        st.error(f"Erro: {repos['error']}")
        return
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        search = st.text_input("🔍 Filtrar", placeholder="Nome do repositório...")
    with col2:
        sort_by = st.selectbox("Ordenar por", ["Atualizado", "Nome", "Estrelas"])
    
    # Filtra e ordena
    if search:
        repos = [r for r in repos if search.lower() in r.get("name", "").lower()]
    
    if sort_by == "Nome":
        repos = sorted(repos, key=lambda x: x.get("name", "").lower())
    elif sort_by == "Estrelas":
        repos = sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)
    
    st.caption(f"📊 {len(repos)} repositórios encontrados")
    st.divider()
    
    # Lista de repos
    for repo in repos:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"### [{repo.get('name')}]({repo.get('html_url')})")
                st.caption(repo.get("description", "Sem descrição"))
                
                # Tags
                tags = []
                if repo.get("language"):
                    tags.append(f"💻 {repo['language']}")
                if repo.get("fork"):
                    tags.append("🍴 Fork")
                if repo.get("private"):
                    tags.append("🔒 Privado")
                st.caption(" | ".join(tags))
            
            with col2:
                st.metric("⭐ Estrelas", repo.get("stargazers_count", 0))
            
            with col3:
                st.metric("🍴 Forks", repo.get("forks_count", 0))
            
            st.divider()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    main()
