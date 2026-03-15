import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# ---------- CSS OTIMIZADO ----------
st.markdown("""
<style>
/* OCULTAR HEADER PADRÃO DO STREAMLIT */
header {visibility: hidden;}
footer {visibility: hidden;}

/* REMOVER LINHAS DIVISÓRIAS */
hr {display: none !important;}

/* AJUSTE DO CONTAINER PRINCIPAL PARA NÃO FICAR ATRÁS DO HEADER FIXO */
.block-container {
    padding-top: 140px; 
    padding-bottom: 50px;
}

/* OCULTAR BOTÃO DE FECHAR SIDEBAR */
[data-testid="stSidebarCloseButton"] {visibility: hidden !important; pointer-events: none;}
button[aria-label="Close sidebar"], button[kind="headerNoPadding"] {display: none !important;}

/* TOPO FIXO */
.top-fixed {
    position: fixed;
    top: 0;
    left: 0; /* Ajustado para ocupar toda largura e sidebar cuidar do resto */
    right: 0;
    background: rgba(255, 255, 255, 0.95);
    z-index: 999;
    border-bottom: 1px solid #ddd;
    padding: 10px 40px;
    backdrop-filter: blur(5px);
}

/* Ajuste para quando a sidebar está aberta (Streamlit adiciona classe no body, mas via CSS puro é limitado) */
/* Vamos assumir que o conteúdo principal começa após a sidebar visualmente */

.main-title {font-size: 1.35rem; font-weight: 600; color: #333;}
.chat-title {font-size: 0.95rem; font-weight: 600; margin-top: 5px; text-align: center; color: #555;}

.materia-info {
    background-color: #f0fdf4;
    border: 1px solid #bbf7d0;
    padding: 8px 15px;
    border-radius: 6px;
    margin-top: 5px;
    color: #166534;
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

/* SCROLLBAR */
.chat-container::-webkit-scrollbar {width: 8px;}
.chat-container::-webkit-scrollbar-track {background: #f1f1f1; border-radius: 4px;}
.chat-container::-webkit-scrollbar-thumb {background: #ccc; border-radius: 4px;}
.chat-container::-webkit-scrollbar-thumb:hover {background: #aaa;}

/* MENSAGENS DO CHAT */
.user-message {
    background-color: #e3f2fd;
    border-left: 5px solid #2196f3;
    padding: 15px;
    border-radius: 8px;
    margin: 15px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.assistant-message {
    background-color: #ffffff;
    border-left: 5px solid #4caf50;
    padding: 15px;
    border-radius: 8px;
    margin: 15px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    line-height: 1.6;
}

/* DESTAQUE DA RESPOSTA CORRETA */
.correct-answer {
    background-color: #dcfce7 !important;
    color: #166534 !important;
    border: 1px solid #86efac;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 700;
    display: inline-block;
    margin: 2px 0;
}

/* SEPARADOR DE QUESTÕES MÚLTIPLAS */
.question-separator {
    border-top: 2px dashed #ddd;
    margin: 20px 0;
}

.stSelectbox label {font-weight: 600;}
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
        st.warning("⚠️ Nenhum PDF na pasta 'pdfs'")
    else:
        pdf_options = {}
        for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
            nome_exibicao = pdf_path.stem # Remove extensão automaticamente
            pdf_options[nome_exibicao] = {'path': pdf_path}
        
        selected_materia = st.selectbox("Escolha a matéria:", options=list(pdf_options.keys()), index=0)
        selected_pdf_info = pdf_options[selected_materia]
        selected_pdf = selected_pdf_info['path']
    
    # Verificação da API Key
    if "COHERE_API_KEY" not in st.secrets:
        st.error("❌ Configure COHERE_API_KEY no secrets")
        st.stop()
    
    try:
        co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])
    except Exception as e:
        st.error(f"❌ Erro na API: {e}")
        st.stop()

# ---------- GERENCIAMENTO DE ESTADO ----------
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
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                # Limpeza básica de quebras de linha excessivas
                text += re.sub(r'\n\s*\n', '\n', page_text) + "\n\n"
        
        if not text.strip():
            return None, "PDF vazio"
        return text, None
    except Exception as e:
        return None, f"Erro: {str(e)}"

# Carregar PDF se mudou a seleção
if selected_pdf and selected_pdf != st.session_state.current_pdf:
    with st.spinner("Lendo PDF..."):
        texto, erro = extract_pdf_text(selected_pdf)
        if erro:
            st.error(f"❌ {erro}")
            st.session_state.pdf_content = ""
            st.session_state.current_pdf = None
        else:
            st.session_state.pdf_content = texto
            st.session_state.current_pdf = selected_pdf
            st.session_state.materia_nome = selected_materia
            st.session_state.caracteres_count = len(texto)
            st.session_state.messages = [] # Limpa chat ao trocar matéria
            st.success("Matéria carregada com sucesso!")

# ---------- TOPO FIXO ----------
# Usamos container para garantir que apareça mesmo se não houver PDF
materia_display = st.session_state.materia_nome if st.session_state.materia_nome else "Nenhuma"
chars_display = f"{st.session_state.caracteres_count:,}" if st.session_state.caracteres_count > 0 else "0"

st.markdown(f"""
<div class="top-fixed">
    <div class="main-title">🎓 Assistente de Estudos</div>
    <div class="materia-info">
        <span><strong>📚 Matéria:</strong> {materia_display}</span>
        <span><small>📄 {chars_display} caracteres</small></span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------- FUNÇÃO DE FORMATAÇÃO ----------
def formatar_resposta(texto):
    if not texto:
        return ""
    
    # 1. Limpeza de tags HTML indesejadas que a IA possa gerar
    texto = re.sub(r'<[^>]+>', '', texto)
    
    # 2. Padronização de Quebras de Linha
    texto = texto.replace('\r\n', '\n').replace('\r', '\n')
    
    # 3. Destacar o Gabarito (Prioridade Máxima)
    # Procura por padrões como: ✅ [GABARITO], **CORRETA**, (Gabarito: A)
    
    # Padrão 1: Tag explícita que pedimos no prompt
    texto = re.sub(r'(✅\s*\[GABARITO\])', r'<span class="correct-answer">\1</span>', texto, flags=re.IGNORECASE)
    
    # Padrão 2: Palavras CORRETA/GABARITO entre asteriscos ou parênteses após a alternativa
    # Ex: A) Texto **CORRETA**  ou  A) Texto (GABARITO)
    texto = re.sub(r'(\*\*CORRETA\*\*|\*CORRETA\*|\(GABARITO\)|\(CORRETA\))', r'<span class="correct-answer">✅ \1</span>', texto, flags=re.IGNORECASE)
    
    # Padrão 3: Alternativa seguida de indicação de verdade (Ex: A) ... Verdadeiro)
    texto = re.sub(r'(VERDADEIRO|V)\s*[-:]?\s*(CORRETO|CERTO)?\s*\*\*', r'<span class="correct-answer">✅ \1 \2</span>', texto, flags=re.IGNORECASE)
    
    # Padrão 4: Se a IA apenas listar o gabarito no final (Ex: Gabarito: A)
    # Tentamos destacar essa linha específica
    linhas = texto.split('\n')
    linhas_formatadas = []
    for linha in linhas:
        if re.search(r'GABARITO|RESPOSTA\s*:', linha, re.IGNORECASE):
            if not '<span class="correct-answer">' in linha:
                linha = f'<span class="correct-answer">{linha}</span>'
        linhas_formatadas.append(linha)
    texto = '\n'.join(linhas_formatadas)

    # 4. Formatação Visual das Alternativas
    # Deixa A), B), C) em negrito
    texto = re.sub(r'(\n|^)([A-E])\)\s*', r'\1<strong>\2)</strong> ', texto, flags=re.IGNORECASE)
    
    # 5. Separador de Múltiplas Questões
    texto = texto.replace('---', '<div class="question-separator"></div>')
    
    # 6. Converter quebras de linha restantes para <br> para HTML
    # Cuidado para não quebrar as tags que já criamos
    partes = texto.split('<div class="question-separator"></div>')
    partes_formatadas = []
    for parte in partes:
        # Só aplica <br> se não estiver dentro de uma tag (simplificado)
        p = parte.replace('\n', '<br>')
        partes_formatadas.append(p)
    
    texto_final = '<div class="question-separator"></div>'.join(partes_formatadas)
    
    return texto_final

# ---------- ÁREA DO CHAT ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown("""
    <div style="text-align: center; color: #888; margin-top: 50px;">
        <h3>👋 Olá! Selecione uma matéria e envie suas questões.</h3>
        <p>Posso resolver questões de múltipla escolha, V/F e abertas.</p>
    </div>
    """, unsafe_allow_html=True)

for message in st.session_state.messages:
    if message["role"] == "user":
        # Limpeza básica para exibição segura
        content_safe = re.sub(r'<[^>]+>', '', message["content"])
        st.markdown(f"""
        <div class="user-message">
            <strong>👤 Você:</strong><br>{content_safe}
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

# ---------- INPUT DO USUÁRIO ----------
if prompt := st.chat_input("Cole a questão ou faça uma pergunta sobre o material..."):
    if not st.session_state.pdf_content:
        st.error("⚠️ Por favor, selecione uma matéria na barra lateral primeiro.")
    else:
        # 1. Adiciona pergunta do usuário ao histórico
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 2. Prepara o contexto (Limita tokens para não estourar, mas mantém integridade)
        # 100k caracteres é seguro para a maioria dos modelos Command
        contexto = st.session_state.pdf_content
        if len(contexto) > 120000:
            contexto = contexto[:120000] + "\n\n...[Conteúdo truncado devido ao tamanho]..."

        # 3. Prompt de Sistema Otimizado
        system_instruction = f"""
Você é um professor assistente especialista em {st.session_state.materia_nome}.
Sua tarefa é responder questões baseando-se EXCLUSIVAMENTE no MATERIAL DE ESTUDO fornecido.

REGRAS RÍGIDAS DE FORMATAÇÃO:
1. REPITA A QUESTÃO COMPLETA (Enunciado + Todas as Alternativas). Não resuma.
2. IDENTIFIQUE A RESPOSTA CORRETA.
3. MARQUE A RESPOSTA: Ao final da alternativa correta, adicione EXATAMENTE: ` ✅ [GABARITO]`
4. NÃO dê explicações longas antes da resposta. Vá direto ao ponto.
5. Se o usuário enviar VÁRIAS QUESTÕES, separe cada resposta com uma linha contendo apenas: `---`
6. Se não encontrar a resposta no texto, diga: "Não encontrei essa informação no material fornecido."

EXEMPLO DE SAÍDA ESPERADA:
1. Qual a capital da França?
A) Londres
B) Paris ✅ [GABARITO]
C) Berlim

MATERIAL DE ESTUDO:
{contexto}
"""

        # 4. Chama a API
        with st.spinner("Analisando questões..."):
            try:
                response = co.chat(
                    model="command-r-plus", # Modelo mais robusto para instruções complexas
                    message=prompt,
                    preamble=system_instruction,
                    temperature=0.2, # Baixa temperatura para seguir regras estritas
                    max_tokens=2500
                )
                resposta_ia = response.text
                
                # 5. Salva resposta no histórico
                st.session_state.messages.append({"role": "assistant", "content": resposta_ia})
                
                # 6. Rerun para atualizar a interface limpa
                st.rerun()
                
            except Exception as e:
                erro_msg = f"❌ Erro na comunicação com a IA: {str(e)}"
                st.session_state.messages.append({"role": "assistant", "content": erro_msg})
                st.rerun()

# ---------- BOTÃO LIMPAR ----------
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico do Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
