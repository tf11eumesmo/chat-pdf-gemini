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
/* Fallback para outras versões ou seletores específicos */
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

def formatar_resposta(texto):
    """Formata a resposta para diferentes tipos de questão"""
    
    # Limpeza inicial
    texto = texto.replace('</div>', '').replace('<div>', '').replace('<br>', '\n')
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = texto.strip()
    
    # Função para processar blocos de questões
    def processar_bloco_questao(bloco):
        # Separar linhas
        linhas = bloco.split('\n')
        linhas_processadas = []
        
        # Primeiro, identificar se é uma questão de múltipla escolha
        alternativas = []
        for linha in linhas:
            # Procurar alternativas (A), B), C), etc)
            match_alt = re.match(r'^\s*([A-E])[\)\.]\s*(.*?)(?:\s*\*\*CORRETA\*\*|\s*CORRETA\s*|\s*✅)?\s*$', linha, re.IGNORECASE)
            if match_alt:
                letra = match_alt.group(1).upper()
                conteudo = match_alt.group(2).strip()
                # Verificar se contém indicação de correta
                if re.search(r'CORRETA|✅', linha, re.IGNORECASE):
                    alternativas.append((letra, conteudo, True))
                else:
                    alternativas.append((letra, conteudo, False))
            else:
                linhas_processadas.append(linha)
        
        # Se encontrou alternativas, processar
        if alternativas:
            resultado = []
            # Adicionar linhas não-alternativas
            resultado.extend(linhas_processadas)
            
            # Adicionar alternativas formatadas
            for letra, conteudo, is_correta in alternativas:
                if is_correta:
                    resultado.append(f'<span class="correct-answer">✅ {letra}) {conteudo}</span>')
                else:
                    resultado.append(f'<strong>{letra})</strong> {conteudo}')
            
            return '\n'.join(resultado)
        
        return bloco
    
    # Dividir o texto em blocos (questões separadas)
    # Procurar padrões como "Questão", números, etc
    blocos = re.split(r'(\n\d+[\.\)]\s+|\nQuestão\s+\d+[\.:]\s+)', texto, flags=re.IGNORECASE)
    
    texto_processado = ""
    for i, bloco in enumerate(blocos):
        if i % 2 == 0:  # Conteúdo normal
            # Processar V/F
            vf_patterns = [
                (r'(✅|VERDADEIRO|V)\s*[-:]?\s*(?:CORRETO|CERTO|CORRETA)?', r'<span class="correct-answer">✅ VERDADEIRO</span>'),
                (r'(❌|FALSO|F)\s*[-:]?\s*(?:INCORRETO|ERRADO|ERRADA)?', r'<span style="color: #d32f2f; font-weight: bold;">❌ FALSO</span>'),
            ]
            
            for padrao, substituicao in vf_patterns:
                bloco = re.sub(padrao, substituicao, bloco, flags=re.IGNORECASE)
            
            # Processar respostas marcadas como corretas
            bloco = re.sub(
                r'(?:✅\s*)?(RESPOSTA|Resposta):?\s*(?:[:\s]*)(.*?)(?:\n|$)',
                r'<span class="correct-answer">✅ Resposta: \2</span>\n',
                bloco,
                flags=re.IGNORECASE
            )
            
            # Procurar padrões de itens numerados corretos
            bloco = re.sub(
                r'(\d+[\.\)]\s*[^\n]*?)\s*\*\*CORRET[OA]\*\*',
                r'<span class="correct-answer">✅ \1</span>',
                bloco,
                flags=re.IGNORECASE
            )
            
            # Processar alternativas que não estão em blocos estruturados
            linhas = bloco.split('\n')
            novas_linhas = []
            
            for linha in linhas:
                # Verificar se é uma alternativa com indicação de correta
                match_alt_correta = re.match(r'^\s*([A-E])[\)\.]\s+(.*?)\s+(?:✅\s*)?(?:CORRETA|correta|✅).*$', linha, re.IGNORECASE)
                if match_alt_correta:
                    letra = match_alt_correta.group(1).upper()
                    conteudo = match_alt_correta.group(2).strip()
                    novas_linhas.append(f'<span class="correct-answer">✅ {letra}) {conteudo}</span>')
                    continue
                
                # Verificar se é alternativa normal
                match_alt = re.match(r'^\s*([A-E])[\)\.]\s+(.*)$', linha)
                if match_alt:
                    letra = match_alt.group(1).upper()
                    conteudo = match_alt.group(2).strip()
                    novas_linhas.append(f'<strong>{letra})</strong> {conteudo}')
                    continue
                
                # Verificar V/F
                match_vf = re.match(r'^\s*([VF])[\)\.]\s+(.*?)(?:\s+✅)?$', linha, re.IGNORECASE)
                if match_vf:
                    letra = match_vf.group(1).upper()
                    conteudo = match_vf.group(2).strip()
                    if letra == 'V':
                        novas_linhas.append(f'<span class="correct-answer">✅ VERDADEIRO</span>')
                    else:
                        novas_linhas.append(f'<span style="color: #d32f2f; font-weight: bold;">❌ FALSO</span>')
                    continue
                
                # Limpar markdown restante
                linha = linha.replace('**', '')
                novas_linhas.append(linha)
            
            texto_processado += '\n'.join(novas_linhas)
        else:  # Título/separador
            texto_processado += f'<br><strong>{bloco}</strong>'
    
    # Substituir quebras de linha por <br> para HTML
    texto_processado = texto_processado.replace('\n', '<br>')
    
    # Remover múltiplas tags de correta duplicadas
    texto_processado = re.sub(r'(<span class="correct-answer">.*?</span>)\s*<span class="correct-answer">', r'\1 ', texto_processado)
    
    return texto_processado

# ---------- CHAT COM CONTAINER DE ROLAGEM ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for message in st.session_state.messages:
    if message["role"] == "user":
        pergunta_limpa = message["content"]
        pergunta_limpa = pergunta_limpa.replace('</div>', '').replace('<div>', '')
        pergunta_limpa = pergunta_limpa.replace('<br>', ' ')
        pergunta_limpa = re.sub(r'<[^>]+>', '', pergunta_limpa).strip()
        
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
        
        pergunta_limpa = prompt.replace('</div>', '').replace('<div>', '')
        pergunta_limpa = re.sub(r'<[^>]+>', '', pergunta_limpa).strip()
        
        st.markdown(f"""
        <div class="user-message">
            <strong>👤 Você:</strong><br>{pergunta_limpa}
        </div>
        """, unsafe_allow_html=True)
        
        with st.spinner("Analisando..."):
            try:
                texto_limitado = st.session_state.pdf_content[:150000]
                
                full_prompt = f"""
Você é um professor assistente especializado em {st.session_state.materia_nome}.

INSTRUÇÕES OBRIGATÓRIAS:
1. Responda APENAS com base no conteúdo do material fornecido abaixo
2. Para MÚLTIPLAS QUESTÕES enviadas de uma vez, responda CADA UMA separadamente
3. Para cada questão, RETORNE A QUESTÃO COMPLETA (pergunta + TODAS as alternativas)
4. Indique qual alternativa está correta usando " **CORRETA**" APÓS a alternativa
5. Formate claramente cada questão com numeração (1., 2., etc) ou separador "---"
6. NÃO adicione justificativas, explicações extras ou comentários
7. Formato EXATO para múltipla escolha:
   - Retorne a pergunta completa
   - Retorne TODAS as alternativas (A, B, C, D, E)
   - Após a correta, escreva: " **CORRETA**"
   - Exemplo: "D) 800 metros **CORRETA**"
8. Para V/F: Retorne "V) afirmação" ou "F) afirmação" e após a correta: " **CORRETA**"
9. Para questões abertas: "Resposta: **resposta correta**"
10. Se não encontrar: "Não encontrei essa informação no material"
11. MANTENHA a numeração original das alternativas se existir no material
12. Use "✅" APENAS se já estiver no material original

MATERIAL DE ESTUDO:
{texto_limitado}

PERGUNTA(S) DO ALUNO:
{prompt}

RESPOSTA (questões completas com alternativas, CADA UMA com a alternativa correta marcada com **CORRETA**):
"""
                
                response = co.chat(
                    model="command-a-03-2025",
                    message=full_prompt,
                    temperature=0.2,
                    max_tokens=4096,
                    preamble="Você é um assistente útil e preciso."
                )
                resposta = response.text
                
                # Pós-processamento para garantir que todas as questões tenham marcação
                linhas = resposta.split('\n')
                resposta_processada = []
                
                for linha in linhas:
                    # Verificar se é uma alternativa que deveria estar marcada
                    match_alt = re.match(r'^\s*([A-E])[\)\.]\s+(.*?)(?:\s*\*\*CORRETA\*\*)?$', linha, re.IGNORECASE)
                    if match_alt and 'CORRETA' not in linha.upper():
                        # Se encontrou alternativa sem marcação, verificar se é a correta baseado em contexto
                        # Manter como está - a IA deve marcar corretamente
                        resposta_processada.append(linha)
                    else:
                        resposta_processada.append(linha)
                
                resposta = '\n'.join(resposta_processada)
                
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
    
    st.rerun()  # Recarrega para manter a rolagem consistente

col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
