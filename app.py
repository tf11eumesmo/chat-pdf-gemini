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

/* REMOVER LINHAS DIVISÓRIAS (HR) */
hr {
    display: none !important;
}

/* AUMENTAR ESPAÇO NO TOPO PARA NÃO FICAR ATRÁS DO HEADER FIXO */
.block-container {
    padding-top: 280px; /* Aumentado de 150px para 280px */
}

/* TOPO FIXO */
.top-fixed {
    position: fixed;
    top: 0;
    left: 0; /* Ajustado para ocupar toda a largura disponível (sidebar lida com o resto) */
    right: 0;
    background: white;
    z-index: 999;
    border-bottom: 1px solid #ddd;
    padding: 20px 40px; /* Aumentado padding vertical */
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
}

.main-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #333;
    margin-bottom: 15px;
}

/* ESTILO DO SELETOR DENTRO DO HEADER */
.header-selectbox-container {
    margin-bottom: 15px;
    max-width: 400px;
}

.chat-title {
    font-size: 1rem;
    font-weight: 600;
    margin-top: 10px;
    text-align: center;
    color: #555;
}

.materia-info {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
    padding: 10px 12px;
    border-radius: 5px;
    margin-top: 10px;
    color: #155724;
    display: inline-block;
}

/* CHAT */
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

/* Ajuste específico para o selectbox dentro do header para ficar bonito */
.stSelectbox label { 
    font-weight: 600; 
    font-size: 0.9rem;
    color: #444;
}
.stSelectbox > div {
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# Lógica da Sidebar (Apenas API Key e Pasta, sem o Selectbox de matéria)
with st.sidebar:
    st.header("⚙️ Configurações")
    
    pdf_folder = Path("pdfs")
    if not pdf_folder.exists():
        pdf_folder.mkdir(parents=True, exist_ok=True)
    
    # Apenas mostrando status da pasta na sidebar
    st.info(f"📂 Pasta de PDFs: `{pdf_folder.absolute()}`")
    
    if "COHERE_API_KEY" not in st.secrets:
        st.error("❌ COHERE_API_KEY não configurada nos secrets")
        st.stop()
    
    try:
        co = cohere.Client(api_key=st.secrets["COHERE_API_KEY"])
        st.success("✅ API Conectada")
    except Exception as e:
        st.error(f"❌ Erro na API: {e}")
        st.stop()

# Inicialização de Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_pdf" not in st.session_state:
    st.session_state.current_pdf = None
if "pdf_content" not in st.session_state:
    st.session_state.pdf_content = ""
if "materia_nome" not in st.session_state:
    st.session_state.materia_nome = "Nenhuma selecionada"
if "caracteres_count" not in st.session_state:
    st.session_state.caracteres_count = 0
if "pdf_options" not in st.session_state:
    st.session_state.pdf_options = {}

# Carregar lista de PDFs
pdf_folder = Path("pdfs")
pdf_files = []
try:
    for item in pdf_folder.iterdir():
        if item.is_file() and item.suffix.lower() == ".pdf":
            pdf_files.append(item)
except Exception as e:
    st.error(f"Erro ao listar PDFs: {e}")

if len(pdf_files) > 0:
    # Atualizar opções apenas se mudou (para não resetar seleção indevidamente)
    current_options_keys = list(st.session_state.pdf_options.keys())
    new_files_names = [f.name for f in pdf_files]
    
    if set(current_options_keys) != set(new_files_names):
        pdf_options = {}
        for pdf_path in sorted(pdf_files, key=lambda x: x.name.lower()):
            nome_original = pdf_path.name
            nome_exibicao = nome_original.replace(".pdf", "").replace(".PDF", "")
            pdf_options[nome_exibicao] = {'path': pdf_path, 'original_name': nome_original}
        st.session_state.pdf_options = pdf_options

# Lógica de Seleção de Matéria (Agora no corpo principal, mas dentro do header visual)
selected_pdf = None
if len(st.session_state.pdf_options) == 0:
    st.warning("⚠️ Nenhum PDF encontrado na pasta 'pdfs'")
else:
    # O selectbox será renderizado dentro do HTML do header abaixo para ficar fixo
    pass

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

# Detectar mudança de seleção (precisamos de uma variável de estado para o selectbox fixo)
# Como o selectbox estará no HTML, usamos st.session_state para controlar a seleção lógica
if "selected_materia_logic" not in st.session_state:
    if len(st.session_state.pdf_options) > 0:
        st.session_state.selected_materia_logic = list(st.session_state.pdf_options.keys())[0]
    else:
        st.session_state.selected_materia_logic = None

# Se houver opções, criamos o selectbox invisível ou usamos query params? 
# Melhor abordagem para Streamlit puro com header fixo customizado:
# Usar um container no topo que simula o header, mas contém widgets reais do Streamlit?
# Não, o pedido foi específico sobre CSS. 
# Truque: Vamos colocar o st.selectbox DENTRO do st.markdown do header? Não funciona bem.
# Solução: Vamos usar st.columns no topo para simular o header, mas mantendo a funcionalidade.
# PORÉM, o usuário pediu para colocar "abaixo do título" no código fornecido.
# Vou usar um truque: Renderizar o selectbox normal do streamlit, mas usar CSS para posicioná-lo visualmente onde queremos,
# OU, mais simples e robusto: Colocar o selectbox REAL logo após o markdown do header, mas antes do padding do block-container.

# Para cumprir estritamente "colocar o seletor abaixo do título" e manter o header fixo:
# Vamos injetar o selectbox dentro da div fixa via HTML não é possível com widgets Streamlit interativos.
# A melhor solução UX mantendo o código limpo é usar st.container() no topo com CSS para parecer fixo,
# mas o código original usava position: fixed.

# Vamos adaptar: O Selectbox REAL ficará logo abaixo do Markdown do Header Fixo, 
# mas visualmente integrado. 

# --- Lógica de Carregamento do PDF ---
if st.session_state.selected_materia_logic and st.session_state.selected_materia_logic in st.session_state.pdf_options:
    selected_info = st.session_state.pdf_options[st.session_state.selected_materia_logic]
    selected_pdf_path = selected_info['path']
    
    if selected_pdf_path != st.session_state.current_pdf:
        texto, erro = extract_pdf_text(selected_pdf_path)
        if erro:
            st.error(f"❌ {erro}")
            st.session_state.pdf_content = ""
            st.session_state.current_pdf = None
        else:
            st.session_state.pdf_content = texto
            st.session_state.current_pdf = selected_pdf_path
            st.session_state.materia_nome = st.session_state.selected_materia_logic
            st.session_state.caracteres_count = len(texto)
            st.session_state.messages = [] # Limpa chat ao trocar matéria

# ---------- TOPO FIXO (Visual) + SELECTBOX REAL ----------
# Nota: Para ter um widget funcional dentro de um header fixo customizado em Streamlit,
# a abordagem mais estável é ter o widget logo no início do body, mas estilizado para parecer parte do header.

st.markdown(f"""
<div class="top-fixed">
    <div class="main-title">
        📚 Selecione uma matéria e faça perguntas sobre o conteúdo!
    </div>
</div>
""", unsafe_allow_html=True)

# Selectbox Real (Posicionado logo após o header fixo visualmente)
if len(st.session_state.pdf_options) > 0:
    col_sel_1, col_sel_2, col_sel_3 = st.columns([1, 3, 1])
    with col_sel_2:
        # Este selectbox controla a variável de sessão que carrega o PDF
        st.session_state.selected_materia_logic = st.selectbox(
            "Escolha a matéria:", 
            options=list(st.session_state.pdf_options.keys()), 
            index=list(st.session_state.pdf_options.keys()).index(st.session_state.selected_materia_logic) if st.session_state.selected_materia_logic in st.session_state.pdf_options else 0,
            key="top_selectbox"
        )

# Informações da Matéria (Visual)
if st.session_state.materia_nome != "Nenhuma selecionada":
    st.markdown(f"""
    <div style="margin-top: -20px; margin-bottom: 20px; text-align: center;">
        <div class="materia-info">
            <strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome} • 
            <small>{st.session_state.caracteres_count:,} caracteres</small>
        </div>
        <div class="chat-title">💬 Chat de Dúvidas</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# Função de Formatação
def formatar_resposta(texto):
    """Formata a resposta para diferentes tipos de questão"""
    
    texto = texto.replace('</div>', '')
    texto = texto.replace('<div>', '')
    texto = texto.replace('<br>', '\n')
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = texto.strip()
    
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
        texto,
        flags=re.IGNORECASE
    )
    
    texto = re.sub(
        r'(RESPOSTA|Resposta):\s*\*\*(.*?)\*\*',
        r'<span class="correct-answer">✅ Resposta: \2</span>',
        texto,
        flags=re.IGNORECASE
    )
    
    texto = re.sub(r'(\n|^)([A-E])\)\s*', r'\1<strong>\2)</strong> ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'(\n|^)(V|v)\)\s*', r'\1<strong>V)</strong> ', texto)
    texto = re.sub(r'(\n|^)(F|f)\)\s*', r'\1<strong>F)</strong> ', texto)
    
    texto = texto.replace('**', '')
    texto = texto.replace('\n', '<br>')
    
    return texto

# Renderizar Histórico
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

# Input do Usuário
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

# Botão Limpar
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
