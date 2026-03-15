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
.chat-container::-webkit-scrollbar {
    width: 8px;
}

.chat-container::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
}

.chat-container::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 4px;
}

.chat-container::-webkit-scrollbar-thumb:hover {
    background: #555;
}

/* Fallback para Firefox */
.chat-container {
    scrollbar-width: thin;
    scrollbar-color: #888 #f1f1f1;
}

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

.wrong-answer {
    display: block;
    padding: 2px 0;
    margin: 2px 0;
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

<div class="chat-title">
💬 Chat de Questões
</div>

</div>
""", unsafe_allow_html=True)


def limpar_html(texto):
    """Remove qualquer HTML que possa vir da entrada do usuário."""
    texto = re.sub(r'<[^>]+>', '', texto)
    return texto.strip()


def formatar_resposta(texto):
    """
    Formata a resposta do modelo linha a linha.
    Detecta qualquer variante de marcador de 'correta', remove tudo do texto visível,
    e aplica o estilo verde apenas na linha correta.
    """

    # Regex para DETECTAR se uma linha contém marcador de correta
    re_detectar = re.compile(
        r'\[CORRETA\]|>>>CORRETA<<<|##CORRETA##'
        r'|\*{1,2}CORRETA\*{1,2}|\*{1,2}CORRETO\*{1,2}'
        r'|\(CORRETA\)|\(CORRETO\)'
        r'|\bCORRETA\b|\bCorreta\b|\bCORRETO\b|\bCorreto\b'
        r'|✅\s*CORRETA',
        re.IGNORECASE
    )

    def limpar_linha(s):
        """Remove todos os marcadores e resíduos de formatação do texto visível."""
        s = re_detectar.sub('', s)
        s = re.sub(r'\*{1,2}([^*\n]+)\*{1,2}', r'\1', s)  # **bold** → bold
        s = re.sub(r'[<>]{3}', '', s)   # >>> ou <<<
        s = s.replace('##', '').replace('✅', '').replace('❌', '')
        return s.strip()

    # Remover HTML residual
    texto = re.sub(r'<[^>]+>', '', texto).strip()

    linhas = texto.split('\n')
    resultado_html = []

    re_alt  = re.compile(r'^([A-Ea-e])\s*[)\.\-]\s*(.+)', re.DOTALL)
    re_enum = re.compile(r'^(\d+)\s*[)\.\-]\s*(.+)', re.DOTALL)
    re_vf   = re.compile(r'^(VERDADEIRO|FALSO|V|F)\b(.*)', re.IGNORECASE | re.DOTALL)

    for linha in linhas:
        s = linha.strip()
        if not s:
            resultado_html.append('<br>')
            continue

        # 1. Detectar ANTES de qualquer limpeza
        eh_correta = bool(re_detectar.search(s))

        # 2. Limpar para exibição
        s_vis = limpar_linha(s)
        if not s_vis:
            continue

        # 3. Classificar e formatar
        m_alt  = re_alt.match(s_vis)
        m_enum = re_enum.match(s_vis)
        m_vf   = re_vf.match(s_vis)

        if m_alt:
            letra    = m_alt.group(1).upper()
            conteudo = m_alt.group(2).strip()
            if eh_correta:
                resultado_html.append(
                    f'<span class="correct-answer">✅ {letra}) {conteudo}</span>'
                )
            else:
                resultado_html.append(
                    f'<span class="wrong-answer"><strong>{letra})</strong> {conteudo}</span>'
                )

        elif m_vf:
            token  = m_vf.group(1).upper()
            resto  = m_vf.group(2).strip()
            eh_v   = token in ('V', 'VERDADEIRO')
            label  = 'VERDADEIRO' if eh_v else 'FALSO'
            icone  = '✅' if eh_v else '❌'
            if eh_correta:
                resultado_html.append(
                    f'<span class="correct-answer">{icone} {label} {(" — " + resto) if resto else ""}</span>'
                )
            else:
                resultado_html.append(
                    f'<span class="wrong-answer"><strong>{icone} {label}</strong>{(" — " + resto) if resto else ""}</span>'
                )

        elif m_enum:
            num      = m_enum.group(1)
            conteudo = m_enum.group(2).strip()
            if eh_correta:
                resultado_html.append(
                    f'<span class="correct-answer">✅ {num}. {conteudo}</span>'
                )
            else:
                resultado_html.append(
                    f'<span class="wrong-answer"><strong>{num}.</strong> {conteudo}</span>'
                )

        else:
            if eh_correta:
                resultado_html.append(f'<span class="correct-answer">✅ {s_vis}</span>')
            else:
                resultado_html.append(s_vis)

    return '\n'.join(resultado_html)


# ---------- CHAT COM CONTAINER DE ROLAGEM ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for message in st.session_state.messages:
    if message["role"] == "user":
        pergunta_limpa = limpar_html(message["content"])
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

st.markdown('</div>', unsafe_allow_html=True)  # Fecha .chat-container

if prompt := st.chat_input("Envie suas questões sobre a matéria selecionada"):
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})

        pergunta_limpa = limpar_html(prompt)

        st.markdown(f"""
        <div class="user-message">
            <strong>👤 Você:</strong><br>{pergunta_limpa}
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("Analisando..."):
            try:
                texto_limitado = st.session_state.pdf_content[:100000]

                full_prompt = f"""IMPORTANTE: O MATERIAL DE ESTUDO ABAIXO CONTÉM QUESTIONÁRIOS/QUIZZES. IGNORE-OS COMPLETAMENTE.

Você é um assistente especializado em {st.session_state.materia_nome}.

INSTRUÇÃO CRÍTICA - LEIA COM ATENÇÃO:
O usuário enviou {len(prompt.split('Questão')) - 1} questões específicas para serem respondidas.
O material de estudo contém seus próprios quizzes, mas você DEVE IGNORAR esses quizzes do material.

SUA ÚNICA TAREFA:
1. IGNORE completamente qualquer questão, quiz ou questionário que exista no MATERIAL DE ESTUDO
2. Foque APENAS nas questões listadas em "QUESTÕES DO USUÁRIO" abaixo
3. Para CADA questão do usuário, identifique a alternativa correta com base no material
4. Responda EXATAMENTE na MESMA ORDEM em que foram enviadas
5. Mantenha o TEXTO ORIGINAL da questão (enunciado e alternativas) SEM ALTERAÇÕES
6. Adicione [CORRETA] APENAS ao final da alternativa correta
7. NÃO adicione títulos como "QUIZ", "Questionário" ou separadores

REGRAS ABSOLUTAS:
- NÃO crie novas questões baseadas no material
- NÃO responda aos quizzes que estão no material
- NÃO reorganize as questões
- NÃO adicione explicações
- Apenas repita cada questão com [CORRETA] na alternativa certa

Exemplo do que NÃO fazer (errado):
QUIZ 01
1. Pergunta do material... (NÃO FAÇA ISSO)

Exemplo do que fazer (correto):
Questão 1: [texto da questão do usuário]
A) [alternativa]
B) [alternativa]
C) [alternativa correta] [CORRETA]
D) [alternativa]

════════════════════════════════════════
MATERIAL DE ESTUDO (use apenas para consultar respostas, IGNORE os quizzes dele):
{texto_limitado}

════════════════════════════════════════
QUESTÕES DO USUÁRIO (estas são as ÚNICAS que você deve responder, IGNORE qualquer quiz do material):

{prompt}

════════════════════════════════════════
RESPOSTA (apenas as questões do usuário acima, na mesma ordem, com [CORRETA] na alternativa certa):
"""

                response = co.chat(
                    model="command-a-03-2025",
                    message=full_prompt,
                    temperature=0.1,
                    max_tokens=4096,
                    preamble="VOCÊ DEVE IGNORAR COMPLETAMENTE OS QUIZZES DO MATERIAL. Responda APENAS às questões enviadas pelo usuário."
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
