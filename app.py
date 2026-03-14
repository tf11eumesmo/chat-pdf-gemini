import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re
import base64

st.set_page_config(page_title="Chat com PDF e Imagem", page_icon="📚", layout="wide")

# ---------- CSS ----------
st.markdown("""
<style>
/* OCULTAR HEADER PADRÃO */
header {visibility: hidden;}

/* REMOVER LINHAS DIVISÓRIAS (HR) */
hr { display: none !important; }

.block-container { padding-top: 150px; }

/* BOTÃO DE FECHAR SIDEBAR (OCULTAR) */
[data-testid="stSidebarCloseButton"] { visibility: hidden !important; pointer-events: none; }
button[aria-label="Close sidebar"], button[kind="headerNoPadding"] { display: none !important; }

/* TOPO FIXO */
.top-fixed {
    position: fixed; top: 0; left: 300px; right: 0;
    background: white; z-index: 999;
    border-bottom: 1px solid #ddd; padding: 15px 40px;
}
.main-title { font-size: 1.35rem; font-weight: 600; }
.chat-title { font-size: 0.95rem; font-weight: 600; margin-top: 8px; text-align: center; }
.materia-info {
    background-color: #d4edda; border-left: 4px solid #28a745;
    padding: 10px 12px; border-radius: 5px; margin-top: 8px;
    color: #155724;
}

/* CHAT */
.user-message {
    background-color: #e3f2fd; border-left: 4px solid #2196f3;
    padding: 15px; border-radius: 10px; margin: 10px 0;
}
.assistant-message {
    background-color: #f5f5f5; border-left: 4px solid #4caf50;
    padding: 15px; border-radius: 10px; margin: 10px 0;
}
.correct-answer {
    background-color: #d4edda; border-left: 4px solid #28a745;
    padding: 8px 12px; border-radius: 5px; margin: 6px 0;
    font-weight: 600; color: #155724; display: block;
}

/* IMAGEM NO CHAT */
.chat-image-preview {
    max-width: 300px;
    max-height: 300px;
    border-radius: 8px;
    margin-top: 10px;
    border: 1px solid #ccc;
    display: block;
}

.stSelectbox label { font-weight: 600; }

/* Upload button styling */
.stFileUploader {
    margin-bottom: 0px;
}
</style>
""", unsafe_allow_html=True)

# ---------- SIDEBAR (CONFIGURAÇÃO) ----------
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
    
    selected_pdf = None
    selected_materia = None

    if len(pdf_files) == 0:
        st.warning("⚠️ Nenhum PDF encontrado na pasta 'pdfs'")
    else:
        pdf_options = {}
        for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
            nome_original = pdf_path.name
            nome_exibicao = nome_original.replace(".pdf", "").replace(".PDF", "")
            pdf_options[nome_exibicao] = {'path': pdf_path, 'original_name': nome_original}
        
        selected_materia = st.selectbox("", options=list(pdf_options.keys()), index=0)
        selected_pdf_info = pdf_options[selected_materia]
        selected_pdf = selected_pdf_info['path']
    
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
if "current_image" not in st.session_state:
    st.session_state.current_image = None

# ---------- FUNÇÕES ----------
def extract_pdf_text(pdf_path):
    try:
        reader = PdfReader(str(pdf_path))
        text = ""
        for page_num, page in enumerate(reader.pages, 1):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text += page_text + "\n\n"
            except Exception:
                continue
        if not text.strip():
            return None, "PDF vazio ou contém apenas imagens"
        return text, None
    except Exception as e:
        return None, f"Erro ao ler PDF: {str(e)}"

def formatar_resposta(texto):
    """Formata a resposta para diferentes tipos de questão"""
    texto = texto.replace('</div>', '').replace('<div>', '').replace('<br>', '\n')
    texto = re.sub(r'<[^>]+>', '', texto).strip()
    
    padroes_correta = [
        (r'([A-E])\)\s*([^\n]*?)\s*\*\*CORRETA\*\*', r'<span class="correct-answer">\1) \2</span>'),
        (r'([A-E])\)\s*([^\n]*?)\s*\*\*Correta\*\*', r'<span class="correct-answer">\1) \2</span>'),
        (r'([A-E])\)\s*([^\n]*?)\s*CORRETA:', r'<span class="correct-answer">\1) \2</span>'),
        (r'([A-E])\)\s*([^\n]*?)\s*✅\s*CORRETA', r'<span class="correct-answer">\1) \2</span>'),
        (r'([A-E])\)\s*([^\n]*?)\s*\(Correta\)', r'<span class="correct-answer">\1) \2</span>'),
        (r'([A-E])\)\s*([^\n]*?)\s*\(CORRETA\)', r'<span class="correct-answer">\1) \2</span>'),
        (r'✅\s*([A-E])\)\s*([^\n]*)', r'<span class="correct-answer">✅ \1) \2</span>'),
    ]
    
    for padrao, substituicao in padroes_correta:
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE)
    
    padroes_vf = [
        (r'(VERDADEIRO|V)\s*[-:]?\s*(CORRETO|CERTO|CORRETA)?\s*\*\*', r'<span class="correct-answer">✅ VERDADEIRO</span>'),
        (r'(FALSO|F)\s*[-:]?\s*(INCORRETO|ERRADO|ERRADA)?\s*\*\*', r'<span style="color: #d32f2f; font-weight: bold;">❌ FALSO</span>'),
        (r'✅\s*(VERDADEIRO|V)', r'<span class="correct-answer">✅ VERDADEIRO</span>'),
        (r'❌\s*(FALSO|F)', r'<span style="color: #d32f2f; font-weight: bold;">❌ FALSO</span>'),
    ]
    
    for padrao, substituicao in padroes_vf:
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE)
    
    texto = re.sub(r'(\n|^)(\d+\.\s*[^\n]*?)\s*\*\*CORRETO\*\*', r'\1<span class="correct-answer">✅ \2</span>', texto, flags=re.IGNORECASE)
    texto = re.sub(r'(RESPOSTA|Resposta):\s*\*\*(.*?)\*\*', r'<span class="correct-answer">✅ Resposta: \2</span>', texto, flags=re.IGNORECASE)
    texto = re.sub(r'(\n|^)([A-E])\)\s*', r'\1<strong>\2)</strong> ', texto, flags=re.IGNORECASE)
    texto = texto.replace('**', '').replace('\n', '<br>')
    
    return texto

# ---------- CARREGAR PDF SE MUDAR ----------
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
        st.session_state.current_image = None

# ---------- TOPO FIXO ----------
st.markdown(f"""
<div class="top-fixed">
<div class="materia-info">
<strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome} • 
<small>{st.session_state.caracteres_count:,} caracteres</small>
</div>
<div class="chat-title">
💬 Chat de Questões (Texto ou Imagem)
</div>
</div>
""", unsafe_allow_html=True)

# ---------- ÁREA DE CHAT ----------
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        if message["role"] == "user":
            pergunta_limpa = message["content"]
            pergunta_limpa = re.sub(r'<[^>]+>', '', pergunta_limpa).strip()
            
            html_content = f"<strong>👤 Você:</strong><br>{pergunta_limpa}"
            
            if "image_data" in message and message["image_data"]:
                b64_img = base64.b64encode(message["image_data"]).decode()
                html_content += f'<br><img src="image/jpeg;base64,{b64_img}" class="chat-image-preview">'
            
            st.markdown(f"""
            <div class="user-message">
                {html_content}
            </div>
            """, unsafe_allow_html=True)
        else:
            resposta_formatada = formatar_resposta(message["content"])
            st.markdown(f"""
            <div class="assistant-message">
                <strong>🤖 Assistente:</strong><br>{resposta_formatada}
            </div>
            """, unsafe_allow_html=True)

# ---------- INPUTS (IMAGEM + TEXTO NA MESMA LINHA) ----------
st.markdown("---")

col_upload, col_input = st.columns([1, 4])

with col_upload:
    uploaded_file = st.file_uploader("Enviar Foto", type=['png', 'jpg', 'jpeg'], 
                                      key="img_uploader", label_visibility="collapsed")
    if uploaded_file is not None:
        st.session_state.current_image = uploaded_file.getvalue()

with col_input:
    prompt = st.chat_input("Digite sua questão ou envie uma foto...")

# Botão para limpar imagem
if st.session_state.current_image:
    col_empty, col_btn, col_empty2 = st.columns([3, 2, 3])
    with col_btn:
        if st.button("🗑️ Remover Foto", use_container_width=True):
            st.session_state.current_image = None
            st.rerun()

# ---------- LÓGICA DE ENVIO ----------
if prompt or st.session_state.current_image:
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria (PDF) primeiro!")
    else:
        user_msg = {
            "role": "user", 
            "content": prompt if prompt else "(Questão enviada via imagem)",
            "image_data": st.session_state.current_image
        }
        st.session_state.messages.append(user_msg)
        
        with chat_container:
            html_content = f"<strong>👤 Você:</strong><br>{prompt if prompt else '(Questão enviada via imagem)'}"
            if st.session_state.current_image:
                b64_img = base64.b64encode(st.session_state.current_image).decode()
                html_content += f'<br><img src="image/jpeg;base64,{b64_img}" class="chat-image-preview">'
            
            st.markdown(f"""
            <div class="user-message">
                {html_content}
            </div>
            """, unsafe_allow_html=True)
        
        texto_limitado = st.session_state.pdf_content[:100000]
        
        if st.session_state.current_image:
            instruction_msg = """
Você é um professor assistente. 
1. Analise a IMAGEM anexada para identificar a questão.
2. Use o MATERIAL DE ESTUDO (texto abaixo) para responder.
3. Siga o formato de resposta estrito (marcar correta, sem justificativa longa).
"""
            images_payload = [st.session_state.current_image]
        else:
            instruction_msg = """
Você é um professor assistente.
1. Responda APENAS com base no conteúdo do material fornecido abaixo.
2. A pergunta está no texto 'PERGUNTA DO ALUNO'.
3. Siga o formato de resposta estrito.
"""
            images_payload = []

        full_prompt = f"""
{instruction_msg}

MATERIAL DE ESTUDO:
{texto_limitado}

PERGUNTA DO ALUNO:
{prompt if prompt else "Veja a imagem anexa."}

RESPOSTA (questão completa + alternativa correta marcada, SEM justificativa):
"""
        
        with st.spinner("Analisando..."):
            try:
                response = co.chat(
                    model="command-r-plus", 
                    message=full_prompt,
                    images=images_payload,
                    temperature=0.3,
                    max_tokens=2048,
                    preamble="Você é um assistente útil e preciso."
                )
                resposta = response.text
                
                st.session_state.messages.append({"role": "assistant", "content": resposta})
                resposta_formatada = formatar_resposta(resposta)
                
                with chat_container:
                    st.markdown(f"""
                    <div class="assistant-message">
                        <strong>🤖 Assistente:</strong><br>{resposta_formatada}
                    </div>
                    """, unsafe_allow_html=True)
                
                st.session_state.current_image = None
                st.rerun()
                
            except Exception as e:
                erro_msg = f"❌ Erro na API: {str(e)}"
                st.error(erro_msg)
                st.session_state.messages.append({"role": "assistant", "content": erro_msg})
                st.session_state.current_image = None

# ---------- BOTÃO LIMPAR HISTÓRICO ----------
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.session_state.current_image = None
        st.rerun()
