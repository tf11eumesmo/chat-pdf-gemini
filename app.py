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

hr {
    display: none !important;
}

.block-container {
    padding-top: 150px;
}

/* SIDEBAR */
[data-testid="stSidebarCloseButton"] {
    visibility: hidden !important;
    pointer-events: none;
}

button[aria-label="Close sidebar"],
button[kind="headerNoPadding"] {
    display: none !important;
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

/* CONTAINER DO CHAT (ROLAGEM) */

.chat-container {
    height: 60vh;
    overflow-y: auto;
    padding-right: 10px;
}

/* BARRA DE SCROLL BONITA */

.chat-container::-webkit-scrollbar {
    width: 8px;
}

.chat-container::-webkit-scrollbar-track {
    background: #f1f1f1;
}

.chat-container::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 4px;
}

.chat-container::-webkit-scrollbar-thumb:hover {
    background: #555;
}

.main-title {
    font-size: 1.35rem;
    font-weight: 600;
}

.chat-title {
    font-size: 0.95rem;
    font-weight: 600;
    margin-top: 8px;
    text-align: center;
}

.materia-info {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
    padding: 10px 12px;
    border-radius: 5px;
    margin-top: 8px;
    color: #155724;
}

/* CHAT MESSAGES */

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

.stSelectbox label { font-weight: 600; }

</style>
""", unsafe_allow_html=True)

# ---------- SIDEBAR ----------

with st.sidebar:
    st.header("📖 Escolha a matéria:")
    
    pdf_folder = Path("pdfs")
    pdf_folder.mkdir(exist_ok=True)

    pdf_files = [p for p in pdf_folder.iterdir() if p.suffix.lower()==".pdf"]

    if not pdf_files:
        st.warning("⚠️ Nenhum PDF encontrado")
        selected_pdf=None
        selected_materia=None
    else:
        pdf_options={}
        for p in pdf_files:
            nome=p.stem
            pdf_options[nome]=p

        selected_materia=st.selectbox("",list(pdf_options.keys()))
        selected_pdf=pdf_options[selected_materia]

    co=cohere.Client(api_key=st.secrets["COHERE_API_KEY"])

# ---------- SESSION ----------

if "messages" not in st.session_state:
    st.session_state.messages=[]

if "pdf_content" not in st.session_state:
    st.session_state.pdf_content=""

if "current_pdf" not in st.session_state:
    st.session_state.current_pdf=None

if "materia_nome" not in st.session_state:
    st.session_state.materia_nome=""

# ---------- LER PDF ----------

def extract_pdf_text(pdf_path):

    reader=PdfReader(str(pdf_path))
    text=""

    for page in reader.pages:
        page_text=page.extract_text()
        if page_text:
            text+=page_text+"\n"

    return text

if selected_pdf and selected_pdf!=st.session_state.current_pdf:

    text=extract_pdf_text(selected_pdf)

    st.session_state.pdf_content=text
    st.session_state.current_pdf=selected_pdf
    st.session_state.materia_nome=selected_materia
    st.session_state.messages=[]

# ---------- TOPO ----------

st.markdown(f"""
<div class="top-fixed">

<div class="materia-info">
<strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome}
</div>

<div class="chat-title">
💬 Chat de Questões
</div>

</div>
""",unsafe_allow_html=True)

# ---------- FORMATAÇÃO ----------

def formatar_resposta(texto):

    texto=texto.replace("**CORRETA**","<span class='correct-answer'>CORRETA</span>")
    texto=texto.replace("\n","<br>")

    return texto

# ---------- CHAT (CONTAINER COM SCROLL) ----------

chat_html='<div class="chat-container">'

for msg in st.session_state.messages:

    if msg["role"]=="user":

        chat_html+=f"""
        <div class="user-message">
        <strong>👤 Você:</strong><br>
        {msg["content"]}
        </div>
        """

    else:

        resposta=formatar_resposta(msg["content"])

        chat_html+=f"""
        <div class="assistant-message">
        <strong>🤖 Assistente:</strong><br>
        {resposta}
        </div>
        """

chat_html+="</div>"

st.markdown(chat_html,unsafe_allow_html=True)

# ---------- INPUT ----------

if prompt:=st.chat_input("Envie sua pergunta"):

    st.session_state.messages.append({"role":"user","content":prompt})

    with st.spinner("Analisando..."):

        texto_limitado=st.session_state.pdf_content[:100000]

        full_prompt=f"""
Responda usando o material.

MATERIAL:
{texto_limitado}

PERGUNTA:
{prompt}
"""

        response=co.chat(
            model="command-a-03-2025",
            message=full_prompt,
            temperature=0.3,
            max_tokens=1500
        )

        resposta=response.text

    st.session_state.messages.append({"role":"assistant","content":resposta})

    st.rerun()

# ---------- LIMPAR ----------

if st.button("🗑️ Limpar Histórico",use_container_width=True):
    st.session_state.messages=[]
    st.rerun()
