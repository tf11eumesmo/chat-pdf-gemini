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

.chat-container {
    height: 60vh;
    overflow-y: auto;
    padding-right: 10px;
}

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

# ---------- SIDEBAR ----------
with st.sidebar:

    st.header("📖 Escolha a matéria")

    pdf_folder = Path("pdfs")
    pdf_folder.mkdir(exist_ok=True)

    pdf_files = [p for p in pdf_folder.glob("*.pdf")]

    if len(pdf_files) == 0:
        st.warning("Nenhum PDF encontrado")
        selected_pdf = None
        selected_materia = None

    else:

        pdf_dict = {p.stem: p for p in pdf_files}

        selected_materia = st.selectbox(
            "Matéria",
            list(pdf_dict.keys())
        )

        selected_pdf = pdf_dict[selected_materia]

    if "COHERE_API_KEY" not in st.secrets:
        st.error("COHERE_API_KEY não configurada")
        st.stop()

    co = cohere.Client(st.secrets["COHERE_API_KEY"])


# ---------- SESSION STATE ----------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_pdf" not in st.session_state:
    st.session_state.current_pdf = None

if "pdf_content" not in st.session_state:
    st.session_state.pdf_content = ""

if "materia_nome" not in st.session_state:
    st.session_state.materia_nome = ""


# ---------- LER PDF ----------
def extract_pdf_text(pdf_path):

    try:

        reader = PdfReader(str(pdf_path))

        text = ""

        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"

        return text

    except Exception as e:

        st.error(f"Erro ao ler PDF: {e}")

        return ""


# ---------- CARREGAR PDF ----------
if selected_pdf and selected_pdf != st.session_state.current_pdf:

    texto = extract_pdf_text(selected_pdf)

    st.session_state.pdf_content = texto
    st.session_state.current_pdf = selected_pdf
    st.session_state.materia_nome = selected_materia
    st.session_state.messages = []


# ---------- TOPO ----------
st.markdown(f"""
<div class="top-fixed">

<b>📚 Matéria Atual:</b> {st.session_state.materia_nome}

</div>
""", unsafe_allow_html=True)


# ---------- FORMATAR RESPOSTA ----------
def formatar_resposta(texto):

    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.strip()

    linhas = texto.split("\n")

    novas_linhas = []

    for linha in linhas:

        linha = linha.strip()

        # Detecta alternativas
        match = re.match(r'^([A-E])\)\s*(.*)', linha, re.I)

        if match:

            letra = match.group(1).upper()
            conteudo = match.group(2)

            if re.search(r'correta|certa|verdadeira|✔|✅', conteudo, re.I):

                conteudo = re.sub(r'correta|certa|verdadeira', '', conteudo, flags=re.I)

                linha = f'<div class="correct-answer">✅ {letra}) {conteudo}</div>'

            else:

                linha = f"<strong>{letra})</strong> {conteudo}"

        novas_linhas.append(linha)

    return "<br>".join(novas_linhas)


# ---------- CHAT ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for message in st.session_state.messages:

    if message["role"] == "user":

        st.markdown(f"""
        <div class="user-message">
        <strong>👤 Você:</strong><br>
        {message["content"]}
        </div>
        """, unsafe_allow_html=True)

    else:

        resposta = formatar_resposta(message["content"])

        st.markdown(f"""
        <div class="assistant-message">
        <strong>🤖 Assistente:</strong><br>
        {resposta}
        </div>
        """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)


# ---------- INPUT ----------
if prompt := st.chat_input("Envie sua questão"):

    if not st.session_state.pdf_content:

        st.error("Selecione um PDF primeiro")

    else:

        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        st.markdown(f"""
        <div class="user-message">
        <strong>👤 Você:</strong><br>{prompt}
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("Analisando..."):

            try:

                texto_limitado = st.session_state.pdf_content[:120000]

                full_prompt = f"""

Você é um professor especialista em {st.session_state.materia_nome}.

REGRAS OBRIGATÓRIAS:

1 Retorne SEMPRE a pergunta completa
2 Retorne TODAS alternativas
3 Marque a correta com a palavra CORRETA no final
4 NÃO explique nada
5 NÃO remova alternativas
6 Se houver várias questões responda todas

FORMATO:

Pergunta

A) alternativa  
B) alternativa  
C) alternativa  
D) alternativa  
E) alternativa CORRETA


MATERIAL:

{texto_limitado}


PERGUNTA:

{prompt}

"""

                response = co.chat(
                    model="command-a-03-2025",
                    message=full_prompt,
                    temperature=0.2,
                    max_tokens=2000
                )

                resposta = response.text

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": resposta
                })

                resposta_formatada = formatar_resposta(resposta)

                st.markdown(f"""
                <div class="assistant-message">
                <strong>🤖 Assistente:</strong><br>
                {resposta_formatada}
                </div>
                """, unsafe_allow_html=True)

            except Exception as e:

                erro = f"Erro na API: {e}"

                st.error(erro)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": erro
                })

        st.rerun()


# ---------- LIMPAR HISTÓRICO ----------
if st.button("🗑️ Limpar Histórico"):

    st.session_state.messages = []

    st.rerun()
