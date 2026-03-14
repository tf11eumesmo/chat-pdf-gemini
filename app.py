import streamlit as st
from google import genai
from pypdf import PdfReader
from pathlib import Path
import re

# Configuração da página
st.set_page_config(
    page_title="Chat com Matérias",
    page_icon="📚",
    layout="wide"
)

# CSS Personalizado para destacar respostas
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
    .chat-container {
        max-width: 900px;
        margin: 0 auto;
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
    .materia-info {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 10px 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .stSelectbox label {
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Título
st.title("📚 Chat com Matérias Escolares")
st.markdown("Selecione uma matéria e faça perguntas sobre o conteúdo!")

# ==================== BARRA LATERAL ====================
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Verificar API Key
    if "GEMINI_API_KEY" in st.secrets:
        try:
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            st.success("✅ API Gemini Conectada")
        except Exception as e:
            st.error(f"❌ Erro ao conectar API: {e}")
            st.stop()
    else:
        st.error("❌ API Key não configurada nos Secrets")
        st.info("Configure em: Settings → Secrets → GEMINI_API_KEY")
        st.stop()
    
    st.divider()
    
    # ==================== SELEÇÃO DE MATÉRIA ====================
    st.header("📖 Selecionar Matéria")
    st.markdown("*PDFs disponíveis no repositório*")
    
    pdf_folder = Path("pdfs")
    
    # Criar pasta se não existir
    if not pdf_folder.exists():
        pdf_folder.mkdir(parents=True, exist_ok=True)
        st.info("📁 Pasta 'pdfs' criada. Adicione seus PDFs nela!")
    
    # Listar PDFs de forma robusta (aceita qualquer nome)
    pdf_files = []
    try:
        for item in pdf_folder.iterdir():
            if item.is_file() and item.suffix.lower() == ".pdf":
                pdf_files.append(item)
    except Exception as e:
        st.error(f"⚠️ Erro ao listar PDFs: {e}")
    
    if len(pdf_files) == 0:
        st.warning("⚠️ Nenhum PDF encontrado na pasta 'pdfs'")
        st.markdown("""
        **Como adicionar PDFs:**
        1. Vá no repositório GitHub
        2. Abra a pasta `pdfs`
        3. Clique em "Add file" → "Upload files"
        4. Envie seus PDFs (aceita nomes com espaços e acentos!)
        5. Faça **Redeploy** no Streamlit
        """)
        selected_pdf = None
        selected_materia = None
    else:
        # Criar dicionário mantendo nomes originais
        pdf_options = {}
        for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
            nome_original = pdf_path.name
            # Nome para exibição no dropdown (formatado, mas informativo)
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
        
        # Mostrar informações do arquivo
        try:
            tamanho_kb = selected_pdf.stat().st_size / 1024
            st.success(f"📄 {selected_pdf_info['original_name']}")
            st.info(f"📊 Tamanho: {tamanho_kb:.1f} KB")
        except:
            st.success(f"📄 {selected_pdf_info['original_name']}")

# ==================== ESTADO DA SESSÃO ====================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_pdf" not in st.session_state:
    st.session_state.current_pdf = None
if "pdf_content" not in st.session_state:
    st.session_state.pdf_content = ""
if "materia_nome" not in st.session_state:
    st.session_state.materia_nome = ""

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
            except Exception as e:
                text += f"[Página {page_num} não pôde ser lida]\n\n"
                continue
        
        if not text.strip():
            return None, "PDF vazio ou contém apenas imagens (sem texto selecionável)"
        
        return text, None
        
    except Exception as e:
        return None, f"Erro ao ler PDF: {str(e)}"

# ==================== CARREGAR PDF QUANDO SELECIONADO ====================
if selected_pdf and selected_pdf != st.session_state.current_pdf:
    with st.spinner("📖 Carregando conteúdo da matéria..."):
        texto, erro = extract_pdf_text(selected_pdf)
        
        if erro:
            st.error(f"❌ {erro}")
            st.session_state.pdf_content = ""
            st.session_state.current_pdf = None
        else:
            st.session_state.pdf_content = texto
            st.session_state.current_pdf = selected_pdf
            st.session_state.materia_nome = selected_materia
            st.session_state.messages = []  # Limpar chat ao trocar de matéria
            st.success(f"✅ '{selected_materia}' carregada! ({len(texto):,} caracteres)")

# ==================== MOSTRAR MATÉRIA SELECIONADA ====================
if st.session_state.pdf_content:
    st.markdown(f"""
    <div class="materia-info">
        <strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome}<br>
        <small>As respostas serão baseadas apenas neste conteúdo</small>
    </div>
    """, unsafe_allow_html=True)
else:
    st.warning("⚠️ Selecione uma matéria acima para começar o chat!")

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
    # Destacar palavras-chave de resposta correta
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
    
    # Remover asteriscos duplos restantes (markdown)
    texto = texto.replace('**', '')
    
    # Quebras de linha para HTML
    texto = texto.replace('\n', '<br>')
    
    return texto

# ==================== INPUT DO USUÁRIO ====================
if prompt := st.chat_input("Digite sua pergunta sobre a matéria..."):
    if not st.session_state.pdf_content:
        st.error("❌ Por favor, selecione uma matéria primeiro!")
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
        with st.spinner("🤔 Analisando conteúdo..."):
            try:
                # Prompt otimizado para a nova API
                full_prompt = f"""
Você é um professor assistente especializado em {st.session_state.materia_nome}.

REGRAS OBRIGATÓRIAS:
1. Responda APENAS com base no conteúdo do material fornecido abaixo
2. Se houver questões com alternativas (A, B, C, D, E), indique claramente qual está **CORRETA**
3. Destaque a resposta correta usando a palavra **CORRETA** em negrito
4. Se não encontrar a informação no material, diga: "Não encontrei essa informação no material fornecido"
5. Seja claro, didático e objetivo
6. Se a pergunta for sobre conceitos, explique de forma simples

MATERIAL DE ESTUDO:
{st.session_state.pdf_content[:400000]}

PERGUNTA DO ALUNO:
{prompt}

RESPOSTA (indique a alternativa **CORRETA** se houver):
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
    if st.button("🗑️ Limpar Histórico do Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==================== RODAPÉ ====================
st.divider()
st.markdown("""
<div style='text-align: center; color: gray; padding: 20px;'>
    <small>📚 Chat com PDF • Powered by Google Gemini • 2026</small><br>
    <small>As respostas são baseadas apenas no conteúdo dos PDFs disponíveis</small>
</div>
""", unsafe_allow_html=True)
