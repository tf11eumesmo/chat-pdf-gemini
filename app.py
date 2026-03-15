import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re
import time

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# ---------- CSS PARA SCROLL ----------
st.markdown("""
<style>
/* OCULTAR HEADER PADRÃO */
header {visibility: hidden;}
hr {display: none !important;}

/* SIDEBAR */
[data-testid="stSidebarCloseButton"] {visibility: hidden !important; pointer-events: none;}
button[aria-label="Close sidebar"], button[kind="headerNoPadding"] {display: none !important;}

/* TOPO FIXO */
.top-fixed {
    position: fixed;
    top: 0;
    left: 300px;
    right: 0;
    background: white;
    z-index: 999;
    border-bottom: 1px solid #ddd;
    padding: 15px 40px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
.materia-info {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
    padding: 10px 12px;
    border-radius: 5px;
    color: #155724;
}
.chat-title {
    font-size: 0.95rem;
    font-weight: 600;
    margin-top: 8px;
    text-align: center;
}

/* ÁREA DO CHAT COM SCROLL - SOLUÇÃO COMPATÍVEL */
.chat-scroll-area {
    height: 520px !important;
    overflow-y: auto !important;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    padding: 10px 5px;
    background-color: #fafafa;
    margin: 10px 0 20px 0;
}

/* Scrollbar personalizada */
.chat-scroll-area::-webkit-scrollbar {width: 10px;}
.chat-scroll-area::-webkit-scrollbar-track {background: #f1f1f1; border-radius: 5px;}
.chat-scroll-area::-webkit-scrollbar-thumb {background: #888; border-radius: 5px;}
.chat-scroll-area::-webkit-scrollbar-thumb:hover {background: #555;}

/* Mensagens nativas do Streamlit */
.stChatMessage {margin: 8px 0 !important;}

/* Input fixo visualmente */
.stChatInputContainer {
    position: sticky;
    bottom: 10px;
    z-index: 100;
    background: white;
    padding: 10px 0;
    border-top: 1px solid #eee;
}
</style>
""", unsafe_allow_html=True)

# Função para forçar scroll via JavaScript
def scroll_to_bottom(key):
    st.markdown(f"""
    <script>
    setTimeout(() => {{
        const container = document.querySelector('.chat-scroll-area');
        if (container) {{
            container.scrollTop = container.scrollHeight;
        }}
    }}, 100);
    </script>
    """, unsafe_allow_html=True)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("📖 Escolha a matéria:")
    
    pdf_folder = Path("pdfs")
    if not pdf_folder.exists():
        pdf_folder.mkdir(parents=True, exist_ok=True)
    
    pdf_files = []
    try:
        for item in pdf_folder.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                pdf_files.append(item)
    except Exception as e:
        st.error(f"Erro ao listar PDFs: {e}")
    
    if len(pdf_files) == 0:
        st.warning("⚠️ Nenhum PDF encontrado na pasta 'pdfs'")
        selected_pdf = None
        selected_materia = None
    else:
        pdf_options = {}
        for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
            nome_exibicao = pdf_path.name.replace(".pdf", "").replace(".PDF", "")
            pdf_options[nome_exibicao] = {'path': pdf_path, 'original_name': pdf_path.name}
        
        selected_materia = st.selectbox("", options=list(pdf_options.keys()), index=0)
        selected_pdf = pdf_options[selected_materia]['path']
    
    if "COHERE_API_KEY" not in st.secrets:
        st.error("❌ COHERE_API_KEY não configurada")
        st.stop()
    
    try:
        co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])
    except Exception as e:
        st.error(f"❌ Erro na API: {e}")
        st.stop()

# ---------- SESSION STATE ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_pdf" not in st.session_state:
    st.session_state.current_pdf = None
if "pdf_content" not in st.session_state:
    st.session_state.pdf_content = ""
if "materia_nome" not in st.session_state:
    st.session_state.materia_nome = ""
if "caracteres_count" not in st.session_state:
    st.session_state.caracteres_count = 0
if "chat_key" not in st.session_state:
    st.session_state.chat_key = 0

# ---------- CARREGAR PDF ----------
def extract_pdf_text(pdf_path):
    try:
        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text += page_text + "\n\n"
        if not text.strip():
            return None, "PDF vazio ou contém apenas imagens"
        return text, None
    except Exception as e:
        return None, f"Erro ao ler PDF: {str(e)}"

if selected_pdf and selected_pdf != st.session_state.current_pdf:
    texto, erro = extract_pdf_text(selected_pdf)
    if erro:
        st.error(f"❌ {erro}")
        st.session_state.pdf_content = ""
        st.session_state.current_pdf = None
        st.session_state.caracteres_count = 0
    else:
        st.session_state.pdf_content = texto
        st.session_state.current_pdf = selected_pdf
        st.session_state.materia_nome = selected_materia
        st.session_state.caracteres_count = len(texto)
        st.session_state.messages = []
        st.session_state.chat_key += 1

# ---------- TOPO FIXO ----------
st.markdown(f"""
<div class="top-fixed">
<div class="materia-info">
<strong>📚 Matéria:</strong> {st.session_state.materia_nome} • 
<small>{st.session_state.caracteres_count:,} caracteres</small>
</div>
<div class="chat-title">💬 Chat de Questões</div>
</div>
""", unsafe_allow_html=True)

# ---------- FORMATAR RESPOSTA ----------
def formatar_resposta(texto):
    texto = re.sub(r'</?div>', '', texto)
    texto = texto.replace('<br>', '\n')
    texto = re.sub(r'<[^>]+>', '', texto).strip()
    
    # Padrões para destacar resposta correta
    padroes = [
        (r'([A-E])\)\s*([^\n]*?)\s*\*\*CORRETA\*\*', r'✅ **\1) \2**'),
        (r'([A-E])\)\s*([^\n]*?)\s*\(CORRETA\)', r'✅ **\1) \2**'),
        (r'✅\s*([A-E])\)\s*([^\n]*)', r'✅ **\1) \2**'),
        (r'(VERDADEIRO|V)\s*[-:]?\s*(CORRETO|CERTO)?\s*\*\*', r'✅ **VERDADEIRO**'),
        (r'(FALSO|F)\s*[-:]?\s*(INCORRETO|ERRADO)?\s*\*\*', r'❌ **FALSO**'),
        (r'(RESPOSTA|Resposta):\s*\*\*(.*?)\*\*', r'✅ **Resposta: \2**'),
    ]
    
    for padrao, substituicao in padroes:
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE)
    
    # Formatar alternativas
    texto = re.sub(r'(\n|^)([A-E])\)\s*', r'\1**\2)** ', texto, flags=re.IGNORECASE)
    texto = texto.replace('**', '**')  # Manter markdown
    return texto

# ---------- ÁREA DO CHAT COM SCROLL ----------
# Container com classe CSS para scroll
st.markdown('<div class="chat-scroll-area">', unsafe_allow_html=True)

# Exibir histórico usando chat nativo do Streamlit
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            # Limpar HTML da mensagem do usuário
            content = re.sub(r'<[^>]+>', '', message["content"]).strip()
            st.markdown(content)
        else:
            # Formatar resposta do assistente
            formatted = formatar_resposta(message["content"])
            st.markdown(formatted)

st.markdown('</div>', unsafe_allow_html=True)

# Scroll automático após renderizar
scroll_to_bottom(st.session_state.chat_key)

# ---------- INPUT DO CHAT ----------
if prompt := st.chat_input("Envie suas questões sobre a matéria selecionada"):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        # Adiciona mensagem do usuário
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.chat_key += 1
        
        with st.spinner("🔍 Analisando..."):
            try:
                texto_limitado = st.session_state.pdf_content[:100000]
                
                full_prompt = f"""
Você é um professor assistente especializado em {st.session_state.materia_nome}.

REGRAS OBRIGATÓRIAS:
1. Responda APENAS com base no material fornecido
2. RETORNE A QUESTÃO COMPLETA (pergunta + TODAS as alternativas)
3. Marque a correta com **CORRETA** após a alternativa
4. NÃO adicione justificativas ou explicações extras
5. Formato múltipla escolha:
   - Pergunta completa
   - Todas as alternativas (A, B, C, D, E)
   - Após a correta: " **CORRETA**"
   - Ex: "D) 800 metros **CORRETA**"
6. V/F: "✅ VERDADEIRO **CORRETO**" ou "❌ FALSO **INCORRETO**"
7. Se não encontrar: "Não encontrei essa informação no material"

MATERIAL:
{texto_limitado}

PERGUNTA:
{prompt}

RESPOSTA (questão completa + alternativa marcada, SEM justificativa):
"""
                
                response = co.chat(
                    model="command-a-03-2025",
                    message=full_prompt,
                    temperature=0.3,
                    max_tokens=2048,
                    preamble="Você é um assistente útil e preciso."
                )
                
                # Adiciona resposta e atualiza
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response.text
                })
                st.session_state.chat_key += 1
                st.rerun()
                
            except Exception as e:
                erro_msg = f"❌ Erro: {str(e)}"
                st.error(erro_msg)
                st.session_state.messages.append({"role": "assistant", "content": erro_msg})
                st.rerun()

# ---------- BOTÃO LIMPAR ----------
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_key += 1
        st.rerun()
