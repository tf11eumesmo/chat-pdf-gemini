import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# ---------- CSS MINIMALISTA ----------
st.markdown("""
<style>
/* Esconder elementos padrão do Streamlit */
header {visibility: hidden;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* Remover divisórias */
hr {display: none !important;}

/* Container principal do chat */
.chat-container {
    padding: 20px 0;
    max-width: 900px;
    margin: 0 auto;
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

/* Destaque para resposta correta */
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

/* Container do topo com seleção */
.top-selector-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 25px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.top-selector-container .stSelectbox label {
    color: white;
    font-weight: 600;
    font-size: 1.1rem;
}

.top-selector-container .stSelectbox > div {
    background: white !important;
    border-radius: 8px;
}

.materia-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background-color: rgba(255,255,255,0.95);
    padding: 10px 16px;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: 500;
    color: #2d3748;
}

.chat-header {
    text-align: center;
    padding: 15px 0;
    margin: 10px 0 25px 0;
    border-bottom: 2px solid #e2e8f0;
}

.chat-header h2 {
    margin: 0;
    color: #4a5568;
    font-size: 1.4rem;
}

/* Input do chat centralizado */
.stChatInputContainer {
    max-width: 900px;
    margin: 20px auto !important;
    padding: 0 20px;
}
</style>
""", unsafe_allow_html=True)

# ---------- LÓGICA DE PDFs ----------
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

# ---------- CONTAINER DE SELEÇÃO NO TOPO ----------
with st.container():
    col_sel1, col_sel2, col_sel3 = st.columns([1, 3, 1])
    with col_sel2:
        st.markdown('<div class="top-selector-container">', unsafe_allow_html=True)
        
        if len(pdf_files) == 0:
            st.warning("⚠️ Nenhum PDF encontrado na pasta 'pdfs'")
            selected_pdf = None
            selected_materia = None
        else:
            pdf_options = {}
            for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
                nome_original = pdf_path.name
                nome_exibicao = nome_original.replace(".pdf", "").replace(".PDF", "")
                pdf_options[nome_exibicao] = {'path': pdf_path, 'original_name': nome_original}
            
            selected_materia = st.selectbox("📖 Escolha a matéria:", options=list(pdf_options.keys()), index=0)
            selected_pdf_info = pdf_options[selected_materia]
            selected_pdf = selected_pdf_info['path']
            
            # Badge da matéria atual
            st.markdown(f'''
            <div class="materia-badge">
                📚 <strong>Matéria Atual:</strong> {selected_materia}
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# ---------- API COHERE ----------
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

# ---------- FUNÇÃO DE EXTRAÇÃO ----------
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

# Carregar PDF quando mudar a seleção
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
        st.rerun()  # Rerun para limpar mensagens antigas

# ---------- CABEÇALHO DO CHAT ----------
st.markdown('<div class="chat-header"><h2>💬 Chat de Dúvidas</h2></div>', unsafe_allow_html=True)

# ---------- FUNÇÃO DE FORMATAÇÃO ----------
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
    
    texto = re.sub(
        r'(\n|^)(\d+\.\s*[^\n]*?)\s*\*\*CORRETO\*\*',
        r'\1<span class="correct-answer">✅ \2</span>',
        texto, flags=re.IGNORECASE
    )
    
    texto = re.sub(
        r'(RESPOSTA|Resposta):\s*\*\*(.*?)\*\*',
        r'<span class="correct-answer">✅ Resposta: \2</span>',
        texto, flags=re.IGNORECASE
    )
    
    texto = re.sub(r'(\n|^)([A-E])\)\s*', r'\1<strong>\2)</strong> ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'(\n|^)(V|v)\)\s*', r'\1<strong>V)</strong> ', texto)
    texto = re.sub(r'(\n|^)(F|f)\)\s*', r'\1<strong>F)</strong> ', texto)
    
    texto = texto.replace('**', '').replace('\n', '<br>')
    return texto

# ---------- EXIBIR MENSAGENS ----------
with st.container():
    chat_col1, chat_col2, chat_col3 = st.columns([1, 4, 1])
    with chat_col2:
        for message in st.session_state.messages:
            if message["role"] == "user":
                pergunta_limpa = re.sub(r'<[^>]+>', '', message["content"].replace('<br>', ' ')).strip()
                st.markdown(f'<div class="user-message"><strong>👤 Você:</strong><br>{pergunta_limpa}</div>', unsafe_allow_html=True)
            else:
                resposta_formatada = formatar_resposta(message["content"])
                st.markdown(f'<div class="assistant-message"><strong>🤖 Assistente:</strong><br>{resposta_formatada}</div>', unsafe_allow_html=True)

# ---------- INPUT DO CHAT ----------
if prompt := st.chat_input("Envie suas questões sobre a matéria selecionada..."):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        pergunta_limpa = re.sub(r'<[^>]+>', '', prompt.replace('<br>', ' ')).strip()
        
        with st.container():
            chat_col1, chat_col2, chat_col3 = st.columns([1, 4, 1])
            with chat_col2:
                st.markdown(f'<div class="user-message"><strong>👤 Você:</strong><br>{pergunta_limpa}</div>', unsafe_allow_html=True)
        
        with st.spinner("🔍 Analisando conteúdo..."):
            try:
                texto_limitado = st.session_state.pdf_content[:100000]
                
                full_prompt = f"""
Você é um professor assistente especializado em {st.session_state.materia_nome}.

INSTRUÇÕES OBRIGATÓRIAS:
1. Responda APENAS com base no conteúdo do material fornecido abaixo
2. RETORNE A QUESTÃO COMPLETA (pergunta + TODAS as alternativas)
3. Indique qual alternativa está correta usando **CORRETA** após a alternativa
4. NÃO adicione justificativas, explicações extras ou comentários
5. Formato EXATO para múltipla escolha:
   - Retorne a pergunta completa
   - Retorne TODAS as alternativas (A, B, C, D, E)
   - Após a correta, escreva: " **CORRETA**"
6. Para V/F: "✅ VERDADEIRO **CORRETO**" ou "❌ FALSO **INCORRETO**"
7. Para enumeração: "1. Item **CORRETO**"
8. Para questões abertas: "Resposta: **resposta correta**"
9. Se não encontrar: "Não encontrei essa informação no material"

MATERIAL DE ESTUDO:
{texto_limitado}

PERGUNTA DO ALUNO:
{prompt}

RESPOSTA (questão completa + alternativa correta marcada, SEM justificativa):
"""
                
                response = co.chat(
                    model="command-a-03-2025",
                    message=full_prompt,
                    temperature=0.3,
                    max_tokens=2048,
                    preamble="Você é um assistente útil e preciso."
                )
                resposta = response.text
                
                st.session_state.messages.append({"role": "assistant", "content": resposta})
                
                with st.container():
                    chat_col1, chat_col2, chat_col3 = st.columns([1, 4, 1])
                    with chat_col2:
                        resposta_formatada = formatar_resposta(resposta)
                        st.markdown(f'<div class="assistant-message"><strong>🤖 Assistente:</strong><br>{resposta_formatada}</div>', unsafe_allow_html=True)
                
            except Exception as e:
                erro_msg = f"❌ Erro na API: {str(e)}"
                st.error(erro_msg)
                st.session_state.messages.append({"role": "assistant", "content": erro_msg})

# ---------- BOTÃO LIMPAR HISTÓRICO ----------
with st.container():
    col_btn1, col_btn2, col_btn3 = st.columns([1, 4, 1])
    with col_btn2:
        if st.session_state.messages:
            if st.button("🗑️ Limpar Histórico", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
