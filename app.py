import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# ---------- CSS ----------

st.markdown("""
<style>

header {visibility: hidden;}

.block-container {
    padding-top: 150px;
}

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
}

.main-title {
    font-size: 1.35rem;
    font-weight: 600;
}

.chat-title {
    font-size: 0.95rem;
    font-weight: 600;
    margin-top: 8px;
}

/* matéria atual */

.materia-info {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
    padding: 10px 12px;
    border-radius: 5px;
    margin-top: 8px;
    color: #155724;
}

/* chat */

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

# ---------- SIDEBAR ----------

with st.sidebar:

    st.header("📖 Selecionar Matéria")

    pdf_folder = Path("pdfs")

    if not pdf_folder.exists():
        pdf_folder.mkdir(parents=True, exist_ok=True)

    pdf_files = [f for f in pdf_folder.glob("*.pdf")]

    if len(pdf_files) == 0:
        st.warning("⚠️ Nenhum PDF encontrado")
        selected_pdf = None
        selected_materia = None

    else:

        pdf_options = {}

        for pdf in pdf_files:
            pdf_options[pdf.stem] = pdf

        selected_materia = st.selectbox(
            "Escolha a matéria:",
            list(pdf_options.keys())
        )

        selected_pdf = pdf_options[selected_materia]

    st.divider()

    if "COHERE_API_KEY" not in st.secrets:
        st.error("COHERE_API_KEY não configurada")
        st.stop()

    co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])

# ---------- SESSION ----------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pdf_content" not in st.session_state:
    st.session_state.pdf_content = ""

if "materia_nome" not in st.session_state:
    st.session_state.materia_nome = ""

if "caracteres_count" not in st.session_state:
    st.session_state.caracteres_count = 0

# ---------- LER PDF ----------

def extract_pdf_text(pdf_path):

    try:

        reader = PdfReader(str(pdf_path))
        text = ""

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n\n"

        return text

    except:
        return ""

if selected_pdf:

    texto = extract_pdf_text(selected_pdf)

    st.session_state.pdf_content = texto
    st.session_state.materia_nome = selected_materia
    st.session_state.caracteres_count = len(texto)

# ---------- TOPO FIXO ----------

st.markdown(f"""
<div class="top-fixed">

<div class="main-title">
📚 Selecione uma matéria e faça perguntas sobre o conteúdo!
</div>

<div class="materia-info">
<strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome} • 
{st.session_state.caracteres_count:,} caracteres
</div>

<div class="chat-title">
💬 Chat de Dúvidas
</div>

</div>
""", unsafe_allow_html=True)

# ---------- FORMATAR RESPOSTA ----------

def formatar_resposta(texto):

    texto = texto.replace('</div>', '')
    texto = re.sub(r'<[^>]+>', '', texto)

    texto = re.sub(
        r'([A-E])\)\s*(.*?)\s*\*\*CORRETA\*\*',
        r'<span class="correct-answer">\1) \2</span>',
        texto,
        flags=re.IGNORECASE
    )

    texto = texto.replace("\n", "<br>")

    return texto

# ---------- CHAT ----------

for message in st.session_state.messages:

    if message["role"] == "user":

        pergunta = re.sub(r'<[^>]+>', '', message["content"])

        st.markdown(f"""
        <div class="user-message">
        <strong>👤 Você:</strong><br>{pergunta}
        </div>
        """, unsafe_allow_html=True)

    else:

        resposta = formatar_resposta(message["content"])

        st.markdown(f"""
        <div class="assistant-message">
        <strong>🤖 Assistente:</strong><br>{resposta}
        </div>
        """, unsafe_allow_html=True)

# ---------- BOTÃO LIMPAR ----------

col1, col2, col3 = st.columns([3,2,3])

with col2:

    if st.button("🗑️ Limpar Histórico", use_container_width=True):

        st.session_state.messages = []
        st.rerun()

# ---------- INPUT ----------

if prompt := st.chat_input("Envie suas questões sobre a matéria selecionada"):

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Analisando..."):

        texto_limitado = st.session_state.pdf_content[:100000]

        full_prompt = f"""
Você é professor especialista em {st.session_state.materia_nome}.

Responda apenas usando o material abaixo.

MATERIAL:
{texto_limitado}

PERGUNTA:
{prompt}

Retorne a questão completa e marque a correta com **CORRETA**
"""

        response = co.chat(
            model="command-a-03-2025",
            message=full_prompt,
            temperature=0.3,
            max_tokens=2048
        )

        resposta = response.text

        st.session_state.messages.append(
            {"role": "assistant", "content": resposta}
        )

        st.rerun()
