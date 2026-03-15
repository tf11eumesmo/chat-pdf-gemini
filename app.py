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
    Preserva a ordem e numeração originais das questões.
    Usa ✅ para marcar alternativas corretas.
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
    re_questao = re.compile(r'^(Questão\s+\d+|Q\d+|Q\.\s*\d+)', re.IGNORECASE)

    for linha in linhas:
        s = linha.strip()
        if not s:
            resultado_html.append('<br>')
            continue

        # 1. Detectar ANTES de qualquer limpeza
        eh_correta = bool(re_detectar.search(s))

        # 2. Limpar para exibição
        s_vis = limpar_linha(s)
        if not s_vis and not eh_correta:
            continue

        # 3. Preservar numeração de questões (Questão 1, Questão 2, etc.)
        if re_questao.match(s_vis):
            resultado_html.append(f'<strong style="color: #1976d2; font-size: 1.1em;">{s_vis}</strong>')
            continue

        # 4. Classificar e formatar alternativas
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
            # Linhas de enunciado ou texto livre
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

                full_prompt = f"""Você é um professor assistente especializado em {st.session_state.materia_nome}.

TAREFA: Responder EXATAMENTE às questões enviadas pelo usuário, na ORDEM e com a NUMERAÇÃO originais.

════════════════════════════════════════
🚫 REGRAS OBRIGATÓRIAS (NÃO IGNORE):

1️⃣ PRESERVE A ORDEM: Responda na mesma sequência em que o usuário enviou.
2️⃣ PRESERVE A NUMERAÇÃO: Use "Questão 1", "Questão 2", etc., exatamente como enviado.
3️⃣ NÃO REORGANIZE: Não crie "Quiz 01", "Quiz 02" ou agrupe por tópicos.
4️⃣ NÃO CRIE NOVAS QUESTÕES: Responda apenas o que foi perguntado.
5️⃣ NÃO ALTERE ENUNCIADOS: Mantenha o texto original das questões.
6️⃣ FORMATO DE RESPOSTA:
   - Repita o enunciado completo da questão
   - Liste TODAS as alternativas originais (a, b, c, d)
   - Adicione [CORRETA] apenas ao final da alternativa correta
   - NÃO altere o texto das alternativas
   - NÃO adicione explicações, justificativas ou comentários extras

════════════════════════════════════════
✅ EXEMPLO DE SAÍDA CORRETA (para uma questão do usuário):

Questão 1
(Enunciado não visível completamente no arquivo, baseado nas opções sobre elaboração de laudo)
a) Inventar uma causa provável para não deixar o laudo em branco.
b) Declarar "Causa não apurada".
c) Pedir para a guarnição de combate decidir a causa.
d) Culpar o proprietário por falta de cuidado. [CORRETA]

Questão 2
Quem é o responsável por realizar, de forma ordinária, o acionamento da equipe de investigação?
a) A seguradora interessada no laudo.
b) O Centro Operacional de Bombeiros (COB). [CORRETA]
c) O proprietário do imóvel sinistrado.
d) O oficial de área presente no local.

════════════════════════════════════════
❌ EXEMPLOS PROIBIDOS (NUNCA FAÇA):

- Não use "# Quiz 01", "Quiz 02", etc.
- Não renumere como "1.", "2.", "3." dentro de grupos
- Não altere a ordem das questões
- Não substitua o enunciado por um novo
- Não adicione explicações após as alternativas

════════════════════════════════════════
MATERIAL DE ESTUDO:
{texto_limitado}

════════════════════════════════════════
QUESTÕES DO USUÁRIO (RESPONDA NESTA ORDEM EXATA):
{prompt}

RESPOSTA (mantendo ordem, numeração e texto originais + [CORRETA] na certa):
"""

                response = co.chat(
                    model="command-a-03-2025",
                    message=full_prompt,
                    temperature=0.0,
                    max_tokens=4096,
                    preamble="Siga as instruções de formatação e ordem à risca. Não crie conteúdo novo. Preserve a numeração original das questões."
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
