import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import os
from pathlib import Path
import urllib.parse

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
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
        font-weight: bold;
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
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
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
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        st.success("✅ API Gemini Conectada")
    else:
        st.error("❌ API Key não configurada nos Secrets")
        st.info("Configure em: Settings → Secrets → GEMINI_API_KEY")
        st.stop()
    
    st.divider()
    
    # ==================== SELEÇÃO DE MATÉRIA ====================
    st.header("📖 Selecionar Matéria")
    st.markdown("*PDFs disponíveis no repositório*")
    
    # Pasta dos PDFs
    pdf_folder = Path("pdfs")
    
    # Criar pasta se não existir
    if not pdf_folder.exists():
        pdf_folder.mkdir(parents=True, exist_ok=True)
    
    # Listar todos os PDFs (case-insensitive)
    pdf_extensions = ["*.pdf", "*.PDF"]
    pdf_files = []
    for ext in pdf_extensions:
        pdf_files.extend(pdf_folder.glob(ext))
    
    # Filtrar apenas arquivos válidos
    pdf_files = [f for f in pdf_files if f.is_file()]
    
    if len(pdf_files) == 0:
        st.warning("⚠️ Nenhum PDF encontrado")
        st.markdown("""
        **Como adicionar PDFs:**
        1. Vá no repositório GitHub
        2. Abra a pasta `pdfs`
        3. Clique em "Add file" → "Upload files"
        4. Envie seus PDFs
        5. Faça **Redeploy** no Streamlit
        """)
        selected_pdf = None
        selected_materia = None
    else:
        # Criar dicionário com nomes originais e amigáveis
        pdf_options = {}
        for pdf_path in pdf_files:
            # Nome original do arquivo (com espaços, acentos, etc.)
            nome_original = pdf_path.name
            
            # Nome amigável para exibição (remove extensão, formata)
            nome_sem_ext = pdf_path.stem
            nome_amigavel = nome_sem_ext.replace("_", " ").replace("-", " ").title()
            
            # Armazena: nome_amigavel → caminho completo
            pdf_options[nome_amigavel] = {
                'path': pdf_path,
                'original_name': nome_original
            }
        
        # Ordenar alfabeticamente
        pdf_options = dict(sorted(pdf_options.items()))
        
        # Dropdown para selecionar matéria
        selected_materia = st.selectbox(
            "Escolha a matéria:",
            options=list(pdf_options.keys()),
            index=0,
            help="Selecione o PDF que será usado como fonte para as respostas"
        )
        
        # Dados do PDF selecionado
        selected_pdf_info = pdf_options[selected_materia]
        selected_pdf = selected_pdf_info['path']
        
        # Mostrar informações
        st.success(f"📄 {selected_pdf_info['original_name']}")
        
        try:
            tamanho_kb = selected_pdf.stat().st_size / 1024
            st.info(f"📊 Tamanho: {tamanho_kb:.1f} KB")
        except:
            st.info("📊 Tamanho: Não disponível")

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
    """Extrai todo o texto de um PDF com tratamento de erros"""
    try:
        reader = PdfReader(str(pdf_path))
        text = ""
        total_pages = len(reader.pages)
        
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
            except Exception as e:
                text += f"[Página {i+1} não pôde ser lida]\n\n"
        
        if len(text.strip()) == 0:
            return None, "PDF vazio ou apenas imagens (sem texto selecionável)"
        
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
        <small>As respostas serão baseadas neste conteúdo</small>
    </div>
    """, unsafe_allow_html=True)
else:
    st.warning("⚠️ Selecione uma matéria acima para começar o chat!")

st.divider()

# ==================== ÁREA DO CHAT ====================
st.header("💬 Chat de Dúvidas")

# Container do chat
chat_container = st.container()

with chat_container:
    # Mostrar histórico de mensagens
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"""
            <div class="user-message">
                <strong>👤 Você:</strong><br>{message["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Formatando resposta (destacar corretas)
            resposta_formatada = formatar_resposta(message["content"])
            st.markdown(f"""
            <div class="assistant-message">
                <strong>🤖 Assistente:</strong><br>{resposta_formatada}
            </div>
            """, unsafe_allow_html=True)

# ==================== FUNÇÃO PARA FORMATAR RESPOSTA ====================
def formatar_resposta(texto):
    """Destaca alternativas corretas e formata a resposta"""
    import re
    
    # Destacar palavras-chave de resposta correta
    padroes_correta = [
        r'\*\*(CORRETA|Correta|correta)\*\*',
        r'(CORRETA|Correta|correta):',
        r'✅\s*(CORRETA|Correta|correta)',
        r'(Alternativa|Letra)\s*[A-E]\s*-\s*Correta',
    ]
    
    for padrao in padroes_correta:
        texto = re.sub(
            padrao, 
            '<span class="correct-answer">✅ \\1</span>', 
            texto, 
            flags=re.IGNORECASE
        )
    
    # Formatar alternativas (A), B), C), etc.
    texto = re.sub(
        r'\n([A-E])\)', 
        r'\n<strong>\1)</strong>', 
        texto, 
        flags=re.IGNORECASE
    )
    
    # Formatar negritos duplos
    texto = texto.replace('**', '')
    
    # Quebras de linha
    texto = texto.replace('\n', '<br>')
    
    return texto

# ==================== INPUT DO USUÁRIO ====================
if prompt := st.chat_input("Digite sua pergunta sobre a matéria..."):
    if not st.session_state.pdf_content:
        st.error("❌ Por favor, selecione uma matéria primeiro!")
    else:
        # Adicionar mensagem do usuário ao histórico
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Mostrar mensagem do usuário
        with chat_container:
            st.markdown(f"""
            <div class="user-message">
                <strong>👤 Você:</strong><br>{prompt}
            </div>
            """, unsafe_allow_html=True)
        
        # Gerar resposta da IA
        with st.spinner("🤔 Analisando conteúdo..."):
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Prompt otimizado
                full_prompt = f"""
Você é um professor assistente especializado em {st.session_state.materia_nome}.

REGRAS IMPORTANTES:
1. Responda APENAS com base no conteúdo do material fornecido
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
                
                response = model.generate_content(full_prompt)
                resposta = response.text
                
                # Adicionar resposta ao histórico
                st.session_state.messages.append({"role": "assistant", "content": resposta})
                
                # Mostrar resposta formatada
                with chat_container:
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
