import streamlit as st
from google import genai
from pypdf import PdfReader
from pathlib import Path
import re

# Configuração da página
st.set_page_config(
    page_title="Chat com PDF",
    page_icon="📚",
    layout="wide"
)

# CSS Personalizado
st.markdown("""
<style>
    .correct-answer {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 10px 15px;
        border-radius: 5px;
        margin: 8px 0;
        font-weight: 600;
        display: inline-block;
    }
    .materia-info {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 12px 15px;
        border-radius: 5px;
        margin: 10px 0;
        color: #155724;
    }
    .materia-info strong {
        color: #155724;
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
    .stSelectbox label {
        font-weight: 600;
    }
    /* Esconder menu padrão do Streamlit para visual mais limpo */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Título principal (substitui o antigo + subtítulo)
st.title("Selecione uma matéria e faça perguntas sobre o conteúdo!")

# ==================== BARRA LATERAL ====================
with st.sidebar:
    # Verificar API Key (só mostra erro se falhar)
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("❌ API Key não configurada")
        st.stop()
    
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        st.error(f"❌ Erro na API: {e}")
        st.stop()
    
    st.divider()
    
    # ==================== SELEÇÃO DE MATÉRIA ====================
    st.header("📖 Selecionar Matéria")
    
    pdf_folder = Path("pdfs")
    
    # Criar pasta se não existir
    if not pdf_folder.exists():
        pdf_folder.mkdir(parents=True, exist_ok=True)
    
    # Listar PDFs de forma robusta (aceita qualquer nome)
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
        # Criar dicionário mantendo nomes originais
        pdf_options = {}
        for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
            nome_original = pdf_path.name
            nome_exibicao = nome_original.replace(".pdf", "").replace(".PDF", "")
            pdf_options[nome_exibicao] = {
                'path': pdf_path,
                'original_name': nome_original
            }
        
        # Dropdown para selecionar matéria
        selected_materia = st.selectbox(
            "Escolha a matéria:",
            options=list(pdf_options.keys()),
            index=0,
            help="Selecione o PDF que será usado como fonte para as respostas"
        )
        
        selected_pdf_info = pdf_options[selected_materia]
        selected_pdf = selected_pdf_info['path']

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
    """Extrai todo o texto de um PDF com tratamento de erros robusto"""
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
        st.session_state.messages = []  # Limpar chat ao trocar de matéria

# ==================== MOSTRAR MATÉRIA SELECIONADA (VERDE) ====================
if st.session_state.pdf_content:
    st.markdown(f"""
    <div class="materia-info">
        <strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome} • 
        <small>{st.session_state.caracteres_count:,} caracteres</small>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ==================== ÁREA DO CHAT ====================
st.header("💬 Chat de Dúvidas")

# Mostrar histórico de mensagens
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f"""
        <div class="user-message">
            <strong>👤 Você:</strong><br>{message["content"]}
        </div>
        """, unsafe_allow_html=True)
    else:
        resposta_formatada = formatar_resposta(message["content"])
        st.markdown(f"""
        <div class="assistant-message">
            <strong>🤖 Assistente:</strong><br>{resposta_formatada}
        </div>
        """, unsafe_allow_html=True)

# ==================== FUNÇÃO PARA FORMATAR RESPOSTA ====================
def formatar_resposta(texto):
    """Destaca alternativas corretas e formata a resposta"""
    padroes = [
        (r'\*\*CORRETA\*\*', '<span class="correct-answer">✅ CORRETA</span>'),
        (r'\*\*Correta\*\*', '<span class="correct-answer">✅ Correta</span>'),
        (r'(CORRETA|Correta|correta):', r'<span class="correct-answer">\1:</span>'),
        (r'✅\s*(CORRETA|Correta|correta)', r'<span class="correct-answer">✅ \1</span>'),
        (r'(Alternativa|Letra)\s*([A-E])\s*[-–:]\s*Correta', r'<span class="correct-answer">\1 \2 - Correta</span>'),
    ]
    
    for padrao, substituicao in padroes:
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE)
    
    # Formatar alternativas: A) texto → <strong>A)</strong> texto
    texto = re.sub(r'(\n|^)([A-E])\)', r'\1<strong>\2)</strong>', texto, flags=re.IGNORECASE)
    
    # Remover asteriscos duplos restantes
    texto = texto.replace('**', '')
    
    # Quebras de linha para HTML
    texto = texto.replace('\n', '<br>')
    
    return texto

# ==================== INPUT DO USUÁRIO ====================
if prompt := st.chat_input("Digite sua pergunta sobre a matéria..."):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        # Adicionar mensagem do usuário
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Mostrar mensagem do usuário
        st.markdown(f"""
        <div class="user-message">
            <strong>👤 Você:</strong><br>{prompt}
        </div>
        """, unsafe_allow_html=True)
        
        # Gerar resposta da IA
        with st.spinner("Analisando..."):
            try:
                full_prompt = f"""
Você é um professor assistente especializado em {st.session_state.materia_nome}.

REGRAS:
1. Responda APENAS com base no conteúdo do material fornecido
2. Se houver alternativas (A, B, C, D, E), indique qual está **CORRETA**
3. Destaque a correta com a palavra **CORRETA** em negrito
4. Se não encontrar a informação, diga: "Não encontrei essa informação no material"
5. Seja claro e objetivo

MATERIAL:
{st.session_state.pdf_content[:400000]}

PERGUNTA:
{prompt}

RESPOSTA (indique **CORRETA** se houver alternativas):
"""
                
                # Chamada à NOVA API google.genai
                response = client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=full_prompt
                )
                resposta = response.text
                
                # Adicionar resposta ao histórico
                st.session_state.messages.append({"role": "assistant", "content": resposta})
                
                # Mostrar resposta formatada
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

# ==================== RODAPÉ ====================
st.divider()
st.markdown("""
<div style='text-align: center; color: gray; padding: 10px;'>
    <small>📚 Chat com PDF • Powered by Google Gemini</small>
</div>
""", unsafe_allow_html=True)
