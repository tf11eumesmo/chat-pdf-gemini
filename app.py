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
hr { display: none !important; }

/* TOPO FIXO */
.top-fixed {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: white;
    z-index: 999;
    border-bottom: 1px solid #ddd;
    padding: 12px 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.header-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 15px;
    flex-wrap: wrap;
}

.header-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #333;
    white-space: nowrap;
}

.selector-container {
    display: flex;
    align-items: center;
    gap: 8px;
}

.selector-container label {
    font-weight: 600;
    font-size: 0.9rem;
    color: #555;
    white-space: nowrap;
}

.selector-container .stSelectbox {
    min-width: 200px;
    max-width: 300px;
}

.materia-info {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
    padding: 8px 12px;
    border-radius: 5px;
    color: #155724;
    font-size: 0.9rem;
    white-space: nowrap;
}

.chat-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #2196f3;
}

/* CHAT - ajuste de padding para não ficar atrás do header */
.block-container {
    padding-top: 140px !important;
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

/* Sidebar minimalista */
.sidebar-warning { font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ---------- SIDEBAR (apenas configurações) ----------
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Verificação da API Key
    if "COHERE_API_KEY" not in st.secrets:
        st.error("❌ COHERE_API_KEY não configurada")
        st.stop()
    
    try:
        co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])
        st.success("✅ API conectada")
    except Exception as e:
        st.error(f"❌ Erro na API: {e}")
        st.stop()
    
    st.markdown("---")
    st.markdown('<p class="sidebar-warning">💡 Dica: Selecione a matéria no topo da página para começar!</p>', unsafe_allow_html=True)

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

# Inicialização do session_state
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

# Seletor de matéria (fora do header para lógica, mas exibido no header)
selected_pdf = None
selected_materia = None

if len(pdf_files) == 0:
    selected_materia = None
    selected_pdf = None
else:
    pdf_options = {}
    for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
        nome_original = pdf_path.name
        nome_exibicao = nome_original.replace(".pdf", "").replace(".PDF", "")
        pdf_options[nome_exibicao] = {'path': pdf_path, 'original_name': nome_original}
    
    # Seletor na sidebar temporariamente para capturar valor, depois movemos para o header
    with st.sidebar:
        st.markdown("##### 📖 Matéria:")
        selected_materia = st.selectbox("", options=list(pdf_options.keys()), index=0, key="header_selector")
        selected_pdf_info = pdf_options[selected_materia]
        selected_pdf = selected_pdf_info['path']

# Carregar PDF quando mudar a seleção
if selected_pdf and selected_pdf != st.session_state.current_pdf:
    texto, erro = extract_pdf_text(selected_pdf)
    if erro:
        st.error(f"❌ {erro}")
        st.session_state.pdf_content = ""
        st.session_state.current_pdf = None
        st.session_state.caracteres_count = 0
        st.session_state.materia_nome = ""
    else:
        st.session_state.pdf_content = texto
        st.session_state.current_pdf = selected_pdf
        st.session_state.materia_nome = selected_materia
        st.session_state.caracteres_count = len(texto)
        st.session_state.messages = []

# ---------- CABEÇALHO FLUTUANTE COM SELETOR ----------
st.markdown(f"""
<div class="top-fixed">
    <div class="header-content">
        <div class="header-left">
            <span class="header-title">📚 Escolha a matéria:</span>
            <div class="selector-container">
                <!-- O selectbox será injetado aqui via Streamlit -->
            </div>
        </div>
        
        <div class="materia-info">
            <strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome if st.session_state.materia_nome else "Nenhuma"} • 
            <small>{st.session_state.caracteres_count:,} caracteres</small>
        </div>
        
        <div class="chat-title">💬 Chat de Dúvidas</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Injetar o selectbox dentro do header usando container HTML + Streamlit hack
# Como não podemos colocar widgets diretamente em HTML, usamos columns no topo
col_sel, col_info, col_chat = st.columns([2, 2, 1])
with col_sel:
    if len(pdf_files) > 0:
        # Selectbox invisível que sincroniza com o do sidebar
        selected_materia_header = st.selectbox(
            "", 
            options=list(pdf_options.keys()), 
            index=0 if selected_materia in pdf_options else 0,
            key="header_main_selector",
            label_visibility="collapsed"
        )
        # Sincronizar seleção
        if selected_materia_header != selected_materia:
            selected_materia = selected_materia_header
            selected_pdf = pdf_options[selected_materia_header]['path']
            texto, erro = extract_pdf_text(selected_pdf)
            if not erro:
                st.session_state.pdf_content = texto
                st.session_state.current_pdf = selected_pdf
                st.session_state.materia_nome = selected_materia_header
                st.session_state.caracteres_count = len(texto)
                st.session_state.messages = []

with col_info:
    st.markdown(f"""
    <div style="background:#d4edda;border-left:4px solid #28a745;padding:8px 12px;border-radius:5px;font-size:0.9rem;color:#155724;">
        <strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome} • 
        <small>{st.session_state.caracteres_count:,} caracteres</small>
    </div>
    """, unsafe_allow_html=True)

with col_chat:
    st.markdown('<div style="padding-top:8px;font-weight:600;color:#2196f3;">💬 Chat de Dúvidas</div>', unsafe_allow_html=True)

st.markdown("---")  # Separador visual após o header

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
for message in st.session_state.messages:
    if message["role"] == "user":
        pergunta_limpa = re.sub(r'<[^>]+>', '', message["content"].replace('</div>', '').replace('<div>', '').replace('<br>', ' ')).strip()
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

# ---------- INPUT DO CHAT ----------
if prompt := st.chat_input("Envie suas questões sobre a matéria selecionada"):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        pergunta_limpa = re.sub(r'<[^>]+>', '', prompt.replace('</div>', '').replace('<div>', '').replace('<br>', ' ')).strip()
        
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

# ---------- BOTÃO LIMPAR ----------
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
