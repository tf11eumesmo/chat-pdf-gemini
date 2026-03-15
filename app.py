import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# ---------- CSS ----------
st.markdown("""
<style>

/* OCULTAR HEADER PADRÃO */
header {visibility: hidden;}

/* REMOVER LINHAS DIVISÓRIAS (HR) */
hr {
    display: none !important;
}

.block-container {
    padding-top: 150px;
}

/* BOTÃO DE FECHAR SIDEBAR (OCULTAR) */
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

/* CONTAINER DO CHAT COM ROLAGEM */
.chat-container {
    height: 60vh;
    overflow-y: auto;
    padding-right: 10px;
    margin-bottom: 20px;
}

/* BARRA DE SCROLL PERSONALIZADA */
.chat-container::-webkit-scrollbar { width: 8px; }
.chat-container::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 4px; }
.chat-container::-webkit-scrollbar-thumb { background: #888; border-radius: 4px; }
.chat-container::-webkit-scrollbar-thumb:hover { background: #555; }
.chat-container { scrollbar-width: thin; scrollbar-color: #888 #f1f1f1; }

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

/* ALTERNATIVA CORRETA — inline style como fallback garantido */
.correct-answer {
    background-color: #d4edda !important;
    border-left: 4px solid #28a745 !important;
    padding: 8px 12px !important;
    border-radius: 5px !important;
    margin: 6px 0 !important;
    font-weight: 700 !important;
    color: #155724 !important;
    display: block !important;
}

.stSelectbox label { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

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

# ---------- TOPO FIXO ----------
st.markdown(f"""
<div class="top-fixed">
<div class="materia-info">
<strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome} • 
<small>{st.session_state.caracteres_count:,} caracteres</small>
</div>
<div class="chat-title">💬 Chat de Questões</div>
</div>
""", unsafe_allow_html=True)


def formatar_resposta(texto):
    """
    Formata a resposta marcando a alternativa correta com fundo verde e ✅.
    Suporta os padrões: **CORRETA**, *Correta*, CORRETA, ✅ CORRETA, (Correta), (CORRETA).
    Usa inline style para garantir que o verde seja aplicado mesmo com sanitização do Streamlit.
    """

    # 1. Limpar tags HTML que possam ter vindo da resposta
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = texto.strip()

    CORRETA_STYLE = (
        'display:block;'
        'background-color:#d4edda;'
        'border-left:4px solid #28a745;'
        'padding:8px 12px;'
        'border-radius:5px;'
        'margin:6px 0;'
        'font-weight:700;'
        'color:#155724;'
    )
    ERRADA_STYLE = 'color:#d32f2f;font-weight:bold;'

    # 2. Padrões que sinalizam alternativa correta (flexíveis, case-insensitive)
    #    Captura: letra, parêntese, espaço, texto da alternativa, marcação de correta
    padroes_mc = [
        # A) texto **CORRETA**  /  A) texto **Correta**
        r'([A-E])\)\s*(.*?)\s*\*\*(CORRETA|Correta|correta)\*\*',
        # A) texto *Correta*
        r'([A-E])\)\s*(.*?)\s*\*(CORRETA|Correta|correta)\*',
        # A) texto CORRETA  (palavra sozinha no final da linha)
        r'([A-E])\)\s*(.*?)\s+(CORRETA|Correta)(?=\s|$)',
        # A) texto ✅ CORRETA  ou  ✅ A) texto
        r'([A-E])\)\s*(.*?)\s*✅\s*(?:CORRETA|Correta)?',
        r'✅\s*([A-E])\)\s*(.*)',
        # A) texto (Correta) / (CORRETA)
        r'([A-E])\)\s*(.*?)\s*\((?:CORRETA|Correta|correta)\)',
    ]

    def substituir_mc(m):
        """Recebe um match com grupos (letra, texto) e devolve HTML verde."""
        letra = m.group(1)
        texto_alt = m.group(2).strip()
        # Remove asteriscos residuais do texto
        texto_alt = texto_alt.replace('**', '').replace('*', '').strip()
        return f'<span style="{CORRETA_STYLE}">✅ {letra}) {texto_alt}</span>'

    for padrao in padroes_mc:
        texto = re.sub(padrao, substituir_mc, texto, flags=re.IGNORECASE | re.MULTILINE)

    # 3. Verdadeiro / Falso
    texto = re.sub(
        r'✅\s*(VERDADEIRO|V\b)',
        f'<span style="{CORRETA_STYLE}">✅ VERDADEIRO</span>',
        texto, flags=re.IGNORECASE
    )
    texto = re.sub(
        r'(VERDADEIRO|V\b)\s*[-–:]?\s*\*\*(CORRETO|CERTO|CORRETA)?\*\*',
        f'<span style="{CORRETA_STYLE}">✅ VERDADEIRO</span>',
        texto, flags=re.IGNORECASE
    )
    texto = re.sub(
        r'❌\s*(FALSO|F\b)',
        f'<span style="{ERRADA_STYLE}">❌ FALSO</span>',
        texto, flags=re.IGNORECASE
    )
    texto = re.sub(
        r'(FALSO|F\b)\s*[-–:]?\s*\*\*(INCORRETO|ERRADO|ERRADA)?\*\*',
        f'<span style="{ERRADA_STYLE}">❌ FALSO</span>',
        texto, flags=re.IGNORECASE
    )

    # 4. Enumeração  "1. item **CORRETO**"
    texto = re.sub(
        r'(\d+\.\s*)(.*?)\s*\*\*(CORRETO|CORRETA)\*\*',
        lambda m: f'<span style="{CORRETA_STYLE}">✅ {m.group(1)}{m.group(2).strip()}</span>',
        texto, flags=re.IGNORECASE | re.MULTILINE
    )

    # 5. Questão aberta  "Resposta: **texto**"
    texto = re.sub(
        r'(RESPOSTA|Resposta)\s*:\s*\*\*(.*?)\*\*',
        lambda m: f'<span style="{CORRETA_STYLE}">✅ Resposta: {m.group(2).strip()}</span>',
        texto, flags=re.IGNORECASE
    )

    # 6. Negrito residual nas demais alternativas  A) texto
    texto = re.sub(r'(?<!\w)([A-E])\)\s*', r'<strong>\1)</strong> ', texto)

    # 7. Remover ** restantes e converter quebras de linha
    texto = texto.replace('**', '')
    texto = texto.replace('\n', '<br>')

    return texto


# ---------- EXIBIÇÃO DO HISTÓRICO ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for message in st.session_state.messages:
    if message["role"] == "user":
        pergunta_limpa = re.sub(r'<[^>]+>', '', message["content"]).strip()
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

# ---------- INPUT ----------
if prompt := st.chat_input("Envie suas questões sobre a matéria selecionada"):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        pergunta_limpa = re.sub(r'<[^>]+>', '', prompt).strip()
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
1. Responda APENAS com base no conteúdo do material fornecido abaixo.
2. RETORNE A QUESTÃO COMPLETA (pergunta + TODAS as alternativas).
3. Indique qual alternativa está correta escrevendo exatamente " **CORRETA**" LOGO APÓS o texto da alternativa correta, sem quebra de linha entre eles.
4. NÃO adicione justificativas, explicações extras ou comentários.
5. Formato EXATO para múltipla escolha:
   Pergunta completa aqui?
   A) texto da alternativa A
   B) texto da alternativa B
   C) texto da alternativa C
   D) texto da alternativa D **CORRETA**
   E) texto da alternativa E
6. Para V/F: na mesma linha escreva "✅ VERDADEIRO **CORRETO**" ou "❌ FALSO **INCORRETO**"
7. Para questões abertas: "Resposta: **resposta correta**"
8. Se não encontrar: "Não encontrei essa informação no material"

MATERIAL DE ESTUDO:
{texto_limitado}

PERGUNTA DO ALUNO:
{prompt}

RESPOSTA:
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
    
    st.rerun()

col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
