import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# ---------- CSS PARA FIXAR O TOPO ----------
st.markdown("""
<style>
    /* Remove espaço do topo */
    .block-container {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Esconde elementos desnecessários */
    header {display: none !important;}
    #MainMenu {display: none !important;}
    footer {display: none !important;}
    
    /* Container fixo no topo */
    .topo-fixo {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background-color: white;
        padding: 15px 20px;
        border-bottom: 2px solid #e0e0e0;
        z-index: 1000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    /* Container do chat (rolável) */
    .chat-rolavel {
        margin-top: 200px;
        padding: 10px 20px 100px 20px;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
    
    /* Estilo do select */
    .stSelectbox {
        max-width: 500px;
        margin: 0 auto !important;
    }
    
    /* Matéria atual */
    .materia-atual {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 10px 20px;
        border-radius: 8px;
        color: #155724;
        font-weight: 500;
        display: inline-block;
        margin: 10px auto;
        font-size: 1.1rem;
    }
    
    /* Contador de caracteres */
    .contador {
        font-size: 0.9rem;
        color: #666;
        margin-left: 10px;
    }
    
    /* Título do chat */
    .chat-titulo {
        font-size: 1.3rem;
        font-weight: 600;
        color: #2196f3;
        margin: 10px 0;
    }
    
    /* Mensagens */
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
    }
</style>
""", unsafe_allow_html=True)

# ---------- VERIFICAÇÃO DA API KEY ----------
if "COHERE_API_KEY" not in st.secrets:
    st.error("❌ COHERE_API_KEY não configurada")
    st.stop()

try:
    co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])
except Exception as e:
    st.error(f"❌ Erro na API Cohere: {e}")
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

def extract_pdf_text(pdf_path):
    try:
        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        if not text.strip():
            return None, "PDF vazio"
        return text, None
    except Exception as e:
        return None, f"Erro: {str(e)}"

# ---------- LISTAR PDFS ----------
pdf_folder = Path("pdfs")
pdf_folder.mkdir(parents=True, exist_ok=True)

pdf_files = []
for item in pdf_folder.iterdir():
    if item.is_file() and item.suffix.lower() == ".pdf":
        pdf_files.append(item)

pdf_options = {}
for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
    nome_exibicao = pdf_path.name.replace(".pdf", "").replace(".PDF", "")
    pdf_options[nome_exibicao] = pdf_path

# ========== TOPO FIXO ==========
st.markdown('<div class="topo-fixo">', unsafe_allow_html=True)

# 1. Escolha a matéria (select)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if pdf_options:
        selected_materia = st.selectbox(
            "📖 Escolha a matéria:", 
            options=list(pdf_options.keys()),
            key="select_materia"
        )
        selected_pdf = pdf_options[selected_materia]
    else:
        st.warning("⚠️ Nenhum PDF encontrado")
        selected_pdf = None
        selected_materia = None

# 2. Matéria atual com contador
if st.session_state.materia_nome:
    st.markdown(f'''
    <div class="materia-atual">
        📚 {st.session_state.materia_nome} 
        <span class="contador">({st.session_state.caracteres_count:,} caracteres)</span>
    </div>
    ''', unsafe_allow_html=True)
else:
    st.markdown('''
    <div class="materia-atual">
        📚 Nenhuma matéria selecionada
    </div>
    ''', unsafe_allow_html=True)

# 3. Título do chat
st.markdown('<div class="chat-titulo">💬 Chat de Dúvidas</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # Fecha topo-fixo

# ========== PROCESSAR PDF SELECIONADO ==========
if pdf_options and selected_pdf:
    if selected_pdf != st.session_state.current_pdf:
        texto, erro = extract_pdf_text(selected_pdf)
        if erro:
            st.error(erro)
        else:
            st.session_state.pdf_content = texto
            st.session_state.current_pdf = selected_pdf
            st.session_state.materia_nome = selected_materia
            st.session_state.caracteres_count = len(texto)
            st.session_state.messages = []

# ========== ÁREA DO CHAT (ROLÁVEL) ==========
st.markdown('<div class="chat-rolavel">', unsafe_allow_html=True)

# Função para formatar respostas
def formatar_resposta(texto):
    texto = re.sub(r'<[^>]+>', '', texto)
    
    # Marcar respostas corretas
    padroes = [
        (r'([A-E])\)\s*([^\n]*?)\s*\*\*CORRETA\*\*', r'<span class="correct-answer">✅ \1) \2</span>'),
        (r'([A-E])\)\s*([^\n]*?)\s*✅', r'<span class="correct-answer">✅ \1) \2</span>'),
    ]
    
    for padrao, sub in padroes:
        texto = re.sub(padrao, sub, texto, flags=re.IGNORECASE)
    
    texto = texto.replace('**', '')
    texto = texto.replace('\n', '<br>')
    return texto

# Mostrar mensagens
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f'''
        <div class="user-message">
            <strong>👤 Você:</strong><br>{message["content"]}
        </div>
        ''', unsafe_allow_html=True)
    else:
        resposta_formatada = formatar_resposta(message["content"])
        st.markdown(f'''
        <div class="assistant-message">
            <strong>🤖 Assistente:</strong><br>{resposta_formatada}
        </div>
        ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # Fecha chat-rolavel

# ========== INPUT DO CHAT ==========
if prompt := st.chat_input("Envie suas questões sobre a matéria selecionada"):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        # Adicionar mensagem do usuário
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Chamar API
        with st.spinner("Analisando..."):
            try:
                texto_limitado = st.session_state.pdf_content[:100000]
                
                full_prompt = f"""Você é um professor especializado em {st.session_state.materia_nome}.

MATERIAL: {texto_limitado}

PERGUNTA: {prompt}

INSTRUÇÕES:
- Responda apenas com base no material
- Se for múltipla escolha, mostre todas as alternativas e marque a correta com **CORRETA**
- Não adicione explicações extras

RESPOSTA:"""
                
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
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
