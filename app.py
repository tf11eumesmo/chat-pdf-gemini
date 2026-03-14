import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# CSS Personalizado com cabeçalho fixo
st.markdown("""
<style>
    /* ========== CABEÇALHO FIXO NO TOPO ========== */
    .fixed-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background-color: #ffffff;
        z-index: 9999;
        padding: 15px 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        border-bottom: 1px solid #e0e0e0;
    }
    
    .main-title {
        font-size: 1.3rem !important;
        font-weight: 600;
        margin: 0 0 10px 0;
        color: #1a1a1a;
    }
    
    .materia-info {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 8px 12px;
        border-radius: 5px;
        margin: 0;
        color: #155724;
        font-size: 0.9rem;
    }
    .materia-info strong { color: #155724; }
    
    /* Espaço para compensar o cabeçalho fixo */
    .header-spacer {
        height: 120px;
    }
    
    /* ========== CHAT COM SCROLL ========== */
    .chat-container {
        max-height: calc(100vh - 250px);
        overflow-y: auto;
        padding-bottom: 20px;
    }
    
    .chat-section-title {
        font-size: 1.1rem !important;
        font-weight: 600;
        color: #1a1a1a;
        margin: 10px 0 15px 0;
    }
    
    /* ========== MENSAGENS DO CHAT ========== */
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
    .correct-answer::before { content: "✅ "; }
    
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
    
    /* ========== SIDEBAR ========== */
    .stSelectbox label { font-weight: 600; }
    
    /* ========== INPUT DO CHAT FIXO NA BASE ========== */
    .stChatInputContainer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: #ffffff;
        padding: 15px 20px;
        z-index: 9999;
        box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
    }
    
    /* Esconder elementos padrão do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppHeader {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==================== BARRA LATERAL ====================
with st.sidebar:
    st.header("📖 Selecionar Matéria")
    
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
            nome_original = pdf_path.name
            nome_exibicao = nome_original.replace(".pdf", "").replace(".PDF", "")
            pdf_options[nome_exibicao] = {'path': pdf_path, 'original_name': nome_original}
        
        selected_materia = st.selectbox("Escolha a matéria:", options=list(pdf_options.keys()), index=0)
        selected_pdf_info = pdf_options[selected_materia]
        selected_pdf = selected_pdf_info['path']
    
    st.divider()
    
    if "COHERE_API_KEY" not in st.secrets:
        st.error("❌ COHERE_API_KEY não configurada")
        st.stop()
    
    try:
        co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])
    except Exception as e:
        st.error(f"❌ Erro na API: {e}")
        st.stop()

# ==================== ESTADO DA SESSÃO ====================
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

# ==================== FUNÇÃO PARA EXTRAIR TEXTO ====================
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

# ==================== CARREGAR PDF QUANDO SELECIONADO ====================
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

# ==================== CABEÇALHO FIXO NO TOPO ====================
st.markdown('<div class="header-spacer"></div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="fixed-header">
    <h1 class="main-title">📚 Selecione uma matéria e faça perguntas sobre o conteúdo!</h1>
    <div class="materia-info">
        <strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome if st.session_state.materia_nome else 'Nenhuma selecionada'} • 
        <small>{st.session_state.caracteres_count:, if st.session_state.caracteres_count else 0} caracteres</small>
    </div>
</div>
""", unsafe_allow_html=True)

# ==================== ÁREA DO CHAT (COM SCROLL) ====================
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
st.markdown('<h2 class="chat-section-title">💬 Chat de Dúvidas</h2>', unsafe_allow_html=True)

for message in st.session_state.messages:
    if message["role"] == "user":
        pergunta_limpa = message["content"]
        pergunta_limpa = pergunta_limpa.replace('</div>', '')
        pergunta_limpa = pergunta_limpa.replace('<div>', '')
        pergunta_limpa = pergunta_limpa.replace('<br>', ' ')
        pergunta_limpa = re.sub(r'<[^>]+>', '', pergunta_limpa)
        pergunta_limpa = pergunta_limpa.strip()
        
        st.markdown(f"""
        <div class="user-message">
            <strong>👤 Você:</strong><br>{pergunta_limpa}
        </div>
        """, unsafe_allow_html=True)
    else:
        resposta_formatada = formatar_resposta(message["content"])
        st.markdown(f"""
        <div class="assistant-message">
            <strong>🤖 Assistente:</strong><br>{resposta_formatada}
        </div>
        """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ==================== FUNÇÃO PARA FORMATAR RESPOSTA ====================
def formatar_resposta(texto):
    """Formata a resposta para diferentes tipos de questão"""
    
    texto = texto.replace('</div>', '')
    texto = texto.replace('<div>', '')
    texto = texto.replace('<br>', '\n')
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = texto.strip()
    
    # QUESTÕES DE MÚLTIPLA ESCOLHA (A, B, C, D, E)
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
    
    # QUESTÕES VERDADEIRO/FALSO (V/F)
    padroes_vf = [
        (r'(VERDADEIRO|V)\s*[-:]?\s*(CORRETO|CERTO|CORRETA)?\s*\*\*', r'<span class="correct-answer">✅ VERDADEIRO</span>'),
        (r'(FALSO|F)\s*[-:]?\s*(INCORRETO|ERRADO|ERRADA)?\s*\*\*', r'<span style="color: #d32f2f; font-weight: bold;">❌ FALSO</span>'),
        (r'✅\s*(VERDADEIRO|V)', r'<span class="correct-answer">✅ VERDADEIRO</span>'),
        (r'❌\s*(FALSO|F)', r'<span style="color: #d32f2f; font-weight: bold;">❌ FALSO</span>'),
    ]
    
    for padrao, substituicao in padroes_vf:
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE)
    
    # ENUMERAÇÃO/NUMERAÇÃO (1, 2, 3...)
    texto = re.sub(
        r'(\n|^)(\d+\.\s*[^\n]*?)\s*\*\*CORRETO\*\*',
        r'\1<span class="correct-answer">✅ \2</span>',
        texto,
        flags=re.IGNORECASE
    )
    
    # QUESTÕES ABERTAS/DISCURSIVAS
    texto = re.sub(
        r'(RESPOSTA|Resposta):\s*\*\*(.*?)\*\*',
        r'<span class="correct-answer">✅ Resposta: \2</span>',
        texto,
        flags=re.IGNORECASE
    )
    
    # FORMATAÇÃO GERAL
    texto = re.sub(r'(\n|^)([A-E])\)\s*', r'\1<strong>\2)</strong> ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'(\n|^)(V|v)\)\s*', r'\1<strong>V)</strong> ', texto)
    texto = re.sub(r'(\n|^)(F|f)\)\s*', r'\1<strong>F)</strong> ', texto)
    
    texto = texto.replace('**', '')
    texto = texto.replace('\n', '<br>')
    
    return texto

# ==================== INPUT DO USUÁRIO ====================
if prompt := st.chat_input("Envie suas questões sobre a matéria selecionada"):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        pergunta_limpa = prompt.replace('</div>', '').replace('<div>', '')
        pergunta_limpa = re.sub(r'<[^>]+>', '', pergunta_limpa).strip()
        
        st.markdown(f"""
        <div class="user-message">
            <strong>👤 Você:</strong><br>{pergunta_limpa}
        </div>
        """, unsafe_allow_html=True)
        
        with st.spinner("Analisando..."):
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
   - Exemplo: "D) 800 metros, devido ao risco... **CORRETA**"
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
                resposta_formatada = formatar_resposta(resposta)
                st.markdown(f"""
                <div class="assistant-message">
                    <strong>🤖 Assistente:</strong><br>{resposta_formatada}
                </div>
                """, unsafe_allow_html=True)
                
            except Exception as e:
                erro_msg = f"❌ Erro na API: {str(e)}"
                st.error(erro_msg)
                st.session_state.messages.append({"role": "assistant", "content": erro_msg})

# ==================== BOTÃO PARA LIMPAR CHAT ====================
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
