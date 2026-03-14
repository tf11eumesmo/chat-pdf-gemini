import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# ---------- CSS AGRESSIVO PARA HEADER FIXO ----------
st.markdown("""
<style>
/* FORÇAR HEADER FIXO NO TOPO */
#meu-header-fixo {
    position: sticky !important;
    top: 0 !important;
    z-index: 10000 !important;
    background-color: white !important;
    padding: 20px !important;
    border-bottom: 3px solid #28a745 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    margin-bottom: 20px !important;
}

/* Esconder header padrão */
header {visibility: hidden !important;}
#MainMenu {visibility: hidden !important;}

/* Ajustar padding do conteúdo */
.block-container {
    padding-top: 200px !important;
}

/* Estilo do seletor */
.stSelectbox {
    margin: 10px 0 !important;
}

/* Info da matéria */
.materia-info {
    background-color: #d4edda !important;
    border-left: 5px solid #28a745 !important;
    padding: 12px 15px !important;
    border-radius: 5px !important;
    margin: 10px 0 !important;
    color: #155724 !important;
    font-weight: 600 !important;
}

/* Título do chat */
.chat-title {
    font-size: 1.2rem !important;
    font-weight: 700 !important;
    color: #333 !important;
    margin-top: 10px !important;
}

/* Mensagens do chat */
.user-message {
    background-color: #e3f2fd;
    border-left: 4px solid #2196f3;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
}
.assistant-message {
    background-color: #f5f5f5;
    border-left: 4px solid #4caf50;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
}
.correct-answer {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
    padding: 8px 12px;
    border-radius: 5px;
    margin: 6px 0;
    font-weight: 600;
    color: #155724;
    display: block;
}
</style>
""", unsafe_allow_html=True)

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

# ========== HEADER FIXO - PRIMEIRA COISA A SER RENDERIZADA ==========
with st.container():
    st.markdown('<div id="meu-header-fixo">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.markdown("### 📖 Matéria:")
    
    with col2:
        # Lógica do seletor
        pdf_folder = Path("pdfs")
        if not pdf_folder.exists():
            pdf_folder.mkdir(parents=True, exist_ok=True)
        
        pdf_files = []
        try:
            for item in pdf_folder.iterdir():
                if item.is_file() and item.suffix.lower() == ".pdf":
                    pdf_files.append(item)
        except Exception as e:
            st.error(f"Erro: {e}")
        
        if len(pdf_files) == 0:
            st.warning("⚠️ Nenhum PDF na pasta 'pdfs'")
            selected_pdf = None
            selected_materia = None
        else:
            pdf_options = {}
            for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
                nome_exibicao = pdf_path.name.replace(".pdf", "").replace(".PDF", "")
                pdf_options[nome_exibicao] = {'path': pdf_path}
            
            selected_materia = st.selectbox(
                "", 
                options=list(pdf_options.keys()), 
                index=0, 
                key="header_selectbox", 
                label_visibility="collapsed"
            )
            selected_pdf = pdf_options[selected_materia]['path']
    
    with col3:
        if st.session_state.get("materia_nome"):
            st.markdown(f"""
            <div class="materia-info">
                📚 {st.session_state.materia_nome}
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('<div class="chat-title">💬 Chat de Dúvidas</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ========== SIDEBAR ==========
with st.sidebar:
    st.header("⚙️ Configurações")
    
    if "COHERE_API_KEY" not in st.secrets:
        st.error("❌ API Key não configurada")
        st.stop()
    
    try:
        co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])
    except Exception as e:
        st.error(f"❌ Erro: {e}")
        st.stop()

# ========== FUNÇÕES ==========
def extract_pdf_text(pdf_path):
    try:
        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        return text if text.strip() else (None, "PDF vazio")
    except Exception as e:
        return None, f"Erro: {str(e)}"

def formatar_resposta(texto):
    texto = re.sub(r'<[^>]+>', '', texto).strip()
    
    padroes = [
        (r'([A-E])\)\s*([^\n]*?)\s*\*\*CORRETA\*\*', r'<span class="correct-answer">\1) \2</span>'),
        (r'(VERDADEIRO|V)\s*\*\*CORRETO\*\*', r'<span class="correct-answer">✅ VERDADEIRO</span>'),
        (r'(FALSO|F)\s*\*\*INCORRETO\*\*', r'<span style="color: #d32f2f; font-weight: bold;">❌ FALSO</span>'),
    ]
    
    for padrao, substituicao in padroes:
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE)
    
    texto = texto.replace('**', '').replace('\n', '<br>')
    return texto

# ========== CARREGAR PDF ==========
if 'selected_pdf' in dir() and selected_pdf and selected_pdf != st.session_state.current_pdf:
    texto, erro = extract_pdf_text(selected_pdf)
    if erro:
        st.error(f"❌ {erro}")
    else:
        st.session_state.pdf_content = texto
        st.session_state.current_pdf = selected_pdf
        st.session_state.materia_nome = selected_materia
        st.session_state.caracteres_count = len(texto)
        st.session_state.messages = []
        st.rerun()

# ========== CHAT ==========
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f'<div class="user-message"><strong>👤 Você:</strong><br>{message["content"]}</div>', unsafe_allow_html=True)
    else:
        resposta_fmt = formatar_resposta(message["content"])
        st.markdown(f'<div class="assistant-message"><strong>🤖 Assistente:</strong><br>{resposta_fmt}</div>', unsafe_allow_html=True)

# ========== INPUT ==========
if prompt := st.chat_input("Envie sua questão"):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria!")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.spinner("Analisando..."):
            try:
                full_prompt = f"""
Você é um professor de {st.session_state.materia_nome}.

INSTRUÇÕES:
1. Responda APENAS com base no material
2. Retorne a questão completa com alternativas
3. Marque a correta com **CORRETA**
4. Sem justificativas

MATERIAL:
{st.session_state.pdf_content[:100000]}

PERGUNTA: {prompt}

RESPOSTA:
"""
                response = co.chat(
                    model="command-a-03-2025",
                    message=full_prompt,
                    temperature=0.3,
                    max_tokens=2048
                )
                
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erro: {str(e)}")

# ========== BOTÃO LIMPAR ==========
if st.button("🗑️ Limpar Histórico"):
    st.session_state.messages = []
    st.rerun()
