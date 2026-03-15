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
hr { display: none !important; }

.block-container { padding-top: 140px; }

/* BOTÃO DE FECHAR SIDEBAR (OCULTAR) */
[data-testid="stSidebarCloseButton"] { visibility: hidden !important; pointer-events: none; }
button[aria-label="Close sidebar"], button[kind="headerNoPadding"] { display: none !important; }

/* TOPO FIXO */
.top-fixed {
    position: fixed;
    top: 0;
    left: 0; /* Ajustado para ocupar toda largura e evitar sobreposição */
    right: 0;
    background: white;
    z-index: 999;
    border-bottom: 1px solid #ddd;
    padding: 10px 40px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}

/* Ajuste para não cobrir a sidebar no mobile */
@media (max-width: 768px) {
    .top-fixed { left: 0; }
}

.main-title { font-size: 1.35rem; font-weight: 600; }
.chat-title { font-size: 0.95rem; font-weight: 600; margin-top: 5px; text-align: center; color: #555; }

.materia-info {
    background-color: #f0f9f4;
    border-left: 5px solid #28a745;
    padding: 10px 15px;
    border-radius: 4px;
    margin-top: 5px;
    color: #155724;
    font-size: 0.9rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* CONTAINER DO CHAT COM ROLAGEM */
.chat-container {
    height: 65vh;
    overflow-y: auto;
    padding: 10px;
    margin-bottom: 20px;
    border: 1px solid #eee;
    border-radius: 8px;
    background-color: #fafafa;
}

/* BARRA DE SCROLL PERSONALIZADA */
.chat-container::-webkit-scrollbar { width: 8px; }
.chat-container::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 4px; }
.chat-container::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }
.chat-container::-webkit-scrollbar-thumb:hover { background: #aaa; }
.chat-container { scrollbar-width: thin; scrollbar-color: #ccc #f1f1f1; }

/* CHAT MESSAGES */
.user-message {
    background-color: #e3f2fd;
    border-left: 5px solid #2196f3;
    padding: 15px;
    border-radius: 8px;
    margin: 15px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.assistant-message {
    background-color: #ffffff;
    border-left: 5px solid #4caf50;
    padding: 15px;
    border-radius: 8px;
    margin: 15px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    line-height: 1.6;
}

/* DESTAQUE DA RESPOSTA CORRETA */
.correct-answer {
    background-color: #d4edda !important;
    border-left: 4px solid #28a745 !important;
    padding: 10px 12px !important;
    border-radius: 4px;
    margin: 8px 0 !important;
    font-weight: 700 !important;
    color: #155724 !important;
    display: block !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.stSelectbox label { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("📖 Configuração")
    
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
        
        selected_materia = st.selectbox("Escolha a matéria:", options=list(pdf_options.keys()), index=0)
        selected_pdf_info = pdf_options[selected_materia]
        selected_pdf = selected_pdf_info['path']
    
    if "COHERE_API_KEY" not in st.secrets:
        st.error("❌ COHERE_API_KEY não configurada no .streamlit/secrets.toml")
        st.stop()
    
    try:
        co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])
    except Exception as e:
        st.error(f"❌ Erro na API: {e}")
        st.stop()

# ---------- ESTADO DA SESSÃO ----------
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
        
        # Limpeza básica de quebras excessivas
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        if not text.strip():
            return None, "PDF vazio ou contém apenas imagens"
        return text, None
    except Exception as e:
        return None, f"Erro ao ler PDF: {str(e)}"

# Carregar PDF se mudou
if selected_pdf and selected_pdf != st.session_state.current_pdf:
    with st.spinner("Lendo PDF..."):
        texto, erro = extract_pdf_text(selected_pdf)
        if erro:
            st.error(f"❌ {erro}")
            st.session_state.pdf_content = ""
            st.session_state.current_pdf = None
            st.session_state.messages = [] # Limpa chat se erro
        else:
            st.session_state.pdf_content = texto
            st.session_state.current_pdf = selected_pdf
            st.session_state.materia_nome = selected_materia
            st.session_state.caracteres_count = len(texto)
            st.session_state.messages = [] # Limpa chat ao trocar matéria
            st.success("PDF carregado com sucesso!")

# ---------- TOPO FIXO ----------
st.markdown(f"""
<div class="top-fixed">
    <div class="materia-info">
        <span><strong>📚 {st.session_state.materia_nome if st.session_state.materia_nome else "Nenhuma"}</strong></span>
        <small>{st.session_state.caracteres_count:,} chars</small>
    </div>
    <div class="chat-title">💬 Chat de Questões</div>
</div>
""", unsafe_allow_html=True)

def formatar_resposta(texto):
    """Formata a resposta para destacar alternativas corretas de forma robusta"""
    if not texto:
        return ""
    
    # 1. Limpeza de tags HTML indesejadas que a IA possa gerar
    texto = re.sub(r'<div>|</div>', '', texto)
    texto = texto.replace('<br>', '\n')
    texto = re.sub(r'<[^>]+>', '', texto) # Remove qualquer outra tag HTML residual
    
    # 2. Normalizar quebras de linha para facilitar o regex
    texto = texto.replace('\r\n', '\n').replace('\r', '\n')
    
    # 3. Regex para Múltipla Escolha (A, B, C, D, E)
    # Procura por: Letra) Texto ... (Correta/✅/**CORRETA**)
    # Captura o bloco inteiro para colocar no span verde
    padroes_correta = [
        # Caso: A) Texto da alternativa **CORRETA**
        (r'([A-E])\)\s*(.+?)\s*(\*\*CORRETA\*\*|✅|Correta|CORRETA)', r'<span class="correct-answer">\1) \2 ✅</span>'),
        # Caso: ✅ A) Texto da alternativa
        (r'(✅)\s*([A-E])\)\s*(.+?)(?=\n|[A-E]\)|$)', r'<span class="correct-answer">\1 \2) \3</span>'),
        # Caso: Resposta: A
        (r'(Resposta|Gabarito):\s*([A-E])(?=\s|\.|$)', r'<span class="correct-answer">✅ Gabarito: \2</span>'),
    ]
    
    for padrao, substituicao in padroes_correta:
        # MULTILINE e IGNORECASE para pegar variações
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE | re.DOTALL)
    
    # 4. Regex para Verdadeiro/Falso
    padroes_vf = [
        (r'(VERDADEIRO|V)\s*[-:]?\s*(CORRETO|CERTO|CORRETA)?\s*\*\*', r'<span class="correct-answer">✅ VERDADEIRO</span>'),
        (r'(FALSO|F)\s*[-:]?\s*(INCORRETO|ERRADO|ERRADA)?\s*\*\*', r'<span style="color: #d32f2f; font-weight: bold; background:#ffebee; padding:5px; border-radius:4px;">❌ FALSO</span>'),
        (r'✅\s*(VERDADEIRO|V)', r'<span class="correct-answer">✅ VERDADEIRO</span>'),
        (r'❌\s*(FALSO|F)', r'<span style="color: #d32f2f; font-weight: bold; background:#ffebee; padding:5px; border-radius:4px;">❌ FALSO</span>'),
    ]
    
    for padrao, substituicao in padroes_vf:
        texto = re.sub(padrao, substituicao, texto, flags=re.IGNORECASE)

    # 5. Formatação visual final (Quebras de linha e negrito residual)
    texto = texto.replace('**', '') # Remove markdown bold residual se já formatado
    texto = re.sub(r'\n{3,}', '\n\n', texto) # Remove quebras excessivas
    texto = texto.replace('\n', '<br>')
    
    return texto

# ---------- ÁREA DO CHAT ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

if not st.session_state.messages and st.session_state.pdf_content:
    st.markdown("<div style='text-align:center; color:#888; margin-top:50px;'>👋 Envie uma questão ou cole o texto de uma pergunta para começar.</div>", unsafe_allow_html=True)

for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]
    
    # Limpeza básica para exibição do usuário
    if role == "user":
        display_content = re.sub(r'<[^>]+>', '', content).replace('<br>', ' ').strip()
        st.markdown(f"""
        <div class="user-message">
            <strong>👤 Você:</strong><br>{display_content}
        </div>
        """, unsafe_allow_html=True)
    else:
        resposta_formatada = formatar_resposta(content)
        st.markdown(f"""
        <div class="assistant-message">
            <strong>🤖 Assistente:</strong><br>{resposta_formatada}
        </div>
        """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ---------- INPUT DO CHAT ----------
if prompt := st.chat_input("Cole a questão ou faça uma pergunta sobre o PDF"):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria na barra lateral primeiro!")
    else:
        # 1. Adiciona mensagem do usuário ao histórico
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 2. Preparar contexto (Corte inteligente para não quebrar palavras)
        max_chars = 80000 # Limite seguro para não estourar token + custo
        contexto_completo = st.session_state.pdf_content
        
        if len(contexto_completo) > max_chars:
            # Tenta cortar no último parágrafo antes do limite
            corte = contexto_completo.rfind('\n\n', 0, max_chars)
            if corte == -1:
                corte = max_chars
            contexto_completo = contexto_completo[:corte] + "\n\n...(conteúdo truncado para otimização)..."

        # 3. Prompt do Sistema Otimizado
        system_instruction = f"""
Você é um professor assistente especialista em {st.session_state.materia_nome}.
Sua tarefa é responder questões baseadas EXCLUSIVAMENTE no MATERIAL DE ESTUDO fornecido.

REGRAS DE FORMATAÇÃO OBRIGATÓRIAS (NÃO IGNORE):
1. Se for múltipla escolha: Retorne a pergunta e TODAS as alternativas.
2. Na alternativa CORRETA, você DEVE adicionar no final da frase: ` ✅ **CORRETA**`
3. Destaque a alternativa correta visualmente repetindo o texto dela com o marcador.
4. Se for Verdadeiro/Falso: Use `✅ VERDADEIRO **CORRETO**` ou `❌ FALSO **INCORRETO**`.
5. Se o usuário enviar VÁRIAS questões de uma vez, separe as respostas com `---`.
6. Não dê explicações longas. Foque na questão e no gabarito.
7. Se não souber, diga: "Não encontrei essa informação no material fornecido."

EXEMPLO DE SAÍDA ESPERADA:
1. Qual a capital da França?
A) Londres
B) Paris ✅ **CORRETA**
C) Berlim

MATERIAL DE ESTUDO:
{contexto_completo}
"""

        with st.spinner("Analisando questão no PDF..."):
            try:
                response = co.chat(
                    model="command-r-plus", # Modelo mais robusto para instruções
                    message=prompt,
                    preamble=system_instruction,
                    temperature=0.2, # Baixa temperatura para consistência
                    max_tokens=2048,
                )
                resposta = response.text
                
                # 4. Adiciona resposta da IA ao histórico
                st.session_state.messages.append({"role": "assistant", "content": resposta})
                
                # 5. Rerun para atualizar a interface com o novo histórico
                st.rerun()
                
            except Exception as e:
                erro_msg = f"❌ Erro na API Cohere: {str(e)}"
                st.session_state.messages.append({"role": "assistant", "content": erro_msg})
                st.rerun()

# ---------- BOTÃO LIMPAR ----------
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico do Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
