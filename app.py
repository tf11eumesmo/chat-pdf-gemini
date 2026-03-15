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

/* Estilo para múltiplas alternativas corretas */
.multiple-correct {
    background-color: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 8px 12px;
    border-radius: 5px;
    margin: 4px 0;
    font-weight: 500;
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
    """Formata a resposta para diferentes tipos de questão com destaque visual melhorado"""
    
    # Limpeza inicial de tags HTML
    texto = texto.replace('</div>', '')
    texto = texto.replace('<div>', '')
    texto = texto.replace('<br>', '\n')
    texto = re.sub(r'<[^>]+>', '', texto)
    texto = texto.strip()
    
    # Dividir em linhas para processar
    linhas = texto.split('\n')
    linhas_formatadas = []
    
    # Padrões para identificar alternativas
    padrao_alternativa = r'^([A-E])\s*[.)]\s*(.+)$'
    padrao_vf = r'^(V|F)\s*[.)]\s*(.+)$'
    padrao_verdadeiro_falso = r'\b(VERDADEIRO|FALSO|V|F)\b'
    
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
            
        linha_original = linha
        
        # Verificar se é uma alternativa com indicação de correta
        correta_match = re.search(r'\*\*CORRETA\*\*|\*Correta\*|CORRETA:|✅\s*CORRETA|\(Correta\)|\(CORRETA\)', linha, re.IGNORECASE)
        
        # Remover marcadores de correta para processamento
        linha_sem_marcador = re.sub(r'\s*\*\*CORRETA\*\*|\s*\*Correta\*|\s*CORRETA:|\s*✅\s*CORRETA|\s*\(Correta\)|\s*\(CORRETA\)', '', linha, flags=re.IGNORECASE)
        
        # Verificar se é uma alternativa (A, B, C, D, E)
        match_alt = re.match(padrao_alternativa, linha_sem_marcador, re.IGNORECASE)
        
        # Verificar se é V/F
        match_vf = re.match(padrao_vf, linha_sem_marcador, re.IGNORECASE)
        
        if correta_match:
            if match_alt:
                # Alternativa múltipla escolha correta
                letra, conteudo = match_alt.groups()
                linhas_formatadas.append(f'<span class="correct-answer">✅ {letra}) {conteudo.strip()}</span>')
            elif match_vf:
                # V/F correta
                letra, conteudo = match_vf.groups()
                if letra.upper() == 'V':
                    linhas_formatadas.append(f'<span class="correct-answer">✅ VERDADEIRO - {conteudo.strip()}</span>')
                else:
                    linhas_formatadas.append(f'<span class="correct-answer">✅ FALSO - {conteudo.strip()}</span>')
            elif re.search(r'VERDADEIRO', linha, re.IGNORECASE):
                linhas_formatadas.append(f'<span class="correct-answer">✅ VERDADEIRO</span>')
            elif re.search(r'FALSO', linha, re.IGNORECASE):
                linhas_formatadas.append(f'<span class="correct-answer">✅ FALSO</span>')
            else:
                # Outro tipo de resposta correta
                linha_limpa = re.sub(r'\s*\*\*CORRETA\*\*|\s*\*Correta\*|\s*CORRETA:|\s*✅\s*CORRETA', '', linha_original, flags=re.IGNORECASE)
                linhas_formatadas.append(f'<span class="correct-answer">✅ {linha_limpa}</span>')
        
        elif re.search(r'INCORRETO|ERRADO', linha, re.IGNORECASE) and not correta_match:
            if match_vf:
                letra, conteudo = match_vf.groups()
                if letra.upper() == 'F':
                    linhas_formatadas.append(f'<span style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 8px 12px; border-radius: 5px; margin: 4px 0; font-weight: 500; color: #721c24; display: block;">❌ FALSO - {conteudo.strip()}</span>')
                else:
                    linhas_formatadas.append(linha_original)
            else:
                linhas_formatadas.append(linha_original)
        
        else:
            # Linha normal (enunciado, etc)
            if match_alt:
                # Alternativa normal (não correta)
                letra, conteudo = match_alt.groups()
                linhas_formatadas.append(f'<strong>{letra})</strong> {conteudo.strip()}')
            elif match_vf:
                # V/F normal
                letra, conteudo = match_vf.groups()
                if letra.upper() == 'V':
                    linhas_formatadas.append(f'<strong>V)</strong> {conteudo.strip()}')
                else:
                    linhas_formatadas.append(f'<strong>F)</strong> {conteudo.strip()}')
            else:
                linhas_formatadas.append(linha_original)
    
    # Juntar tudo com quebras de linha
    texto_formatado = '<br>'.join(linhas_formatadas)
    
    # Substituições adicionais para casos especiais
    texto_formatado = re.sub(r'RESPOSTA:\s*\*\*(.*?)\*\*', r'<span class="correct-answer">✅ RESPOSTA: \1</span>', texto_formatado, flags=re.IGNORECASE)
    texto_formatado = re.sub(r'Resposta:\s*\*\*(.*?)\*\*', r'<span class="correct-answer">✅ Resposta: \1</span>', texto_formatado)
    
    # Remover qualquer ** restante
    texto_formatado = texto_formatado.replace('**', '')
    
    return texto_formatado

# ---------- CHAT COM CONTAINER DE ROLAGEM ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

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

st.markdown('</div>', unsafe_allow_html=True)  # Fecha .chat-container

def processar_multiplas_questoes(pergunta):
    """Detecta se há múltiplas questões e prepara o prompt adequadamente"""
    
    # Padrões para identificar início de questões
    padroes_questao = [
        r'\d+[\.\)]\s+',  # Números seguidos de . ou )
        r'Questão\s+\d+',  # "Questão X"
        r'[A-Z][\)\.]\s+',  # Letras maiúsculas com ) ou .
    ]
    
    linhas = pergunta.split('\n')
    questoes_detectadas = []
    questao_atual = []
    
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
            
        # Verificar se esta linha parece ser início de nova questão
        is_nova_questao = False
        for padrao in padroes_questao:
            if re.match(padrao, linha, re.IGNORECASE):
                is_nova_questao = True
                break
        
        if is_nova_questao and questao_atual:
            questoes_detectadas.append('\n'.join(questao_atual))
            questao_atual = [linha]
        else:
            questao_atual.append(linha)
    
    if questao_atual:
        questoes_detectadas.append('\n'.join(questao_atual))
    
    return questoes_detectadas if len(questoes_detectadas) > 1 else None

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
                
                # Verificar se são múltiplas questões
                multiplas_questoes = processar_multiplas_questoes(prompt)
                
                if multiplas_questoes:
                    # Instrução específica para múltiplas questões
                    instrucao_multiplas = """
INSTRUÇÕES PARA MÚLTIPLAS QUESTÕES:
- Responda CADA questão separadamente
- Para CADA questão, retorne o enunciado completo
- Para CADA questão, retorne TODAS as alternativas
- Identifique a alternativa correta de CADA questão usando "**CORRETA**" após a alternativa
- Mantenha a numeração original das questões
- Separe claramente as questões com uma linha em branco
"""
                else:
                    instrucao_multiplas = ""
                
                full_prompt = f"""
Você é um professor assistente especializado em {st.session_state.materia_nome}.

INSTRUÇÕES OBRIGATÓRIAS:
1. Responda APENAS com base no conteúdo do material fornecido abaixo
2. RETORNE A QUESTÃO COMPLETA (pergunta + TODAS as alternativas)
3. Para identificar a alternativa correta, use EXATAMENTE: "**CORRETA**" após a alternativa correta
4. Exemplo de formatação CORRETA:
   Pergunta: Qual é a capital do Brasil?
   A) São Paulo
   B) Rio de Janeiro
   C) Brasília **CORRETA**
   D) Salvador
   E) Belo Horizonte
5. Para questões de Verdadeiro/Falso:
   V) Afirmação verdadeira **CORRETA**
   F) Afirmação falsa
6. Para questões abertas: "Resposta: **resposta correta**"
7. Se não encontrar a informação: "Não encontrei essa informação no material"
8. NÃO adicione justificativas, explicações extras ou comentários além da resposta
9. NÃO use markdown além do necessário para marcar a resposta correta

{instrucao_multiplas}

MATERIAL DE ESTUDO:
{texto_limitado}

PERGUNTA(S) DO ALUNO:
{prompt}

RESPOSTA (retorne a(s) questão(ões) completa(s) com a(s) alternativa(s) correta(s) marcada(s) com **CORRETA**):
"""
                
                response = co.chat(
                    model="command-a-03-2025",
                    message=full_prompt,
                    temperature=0.2,  # Temperatura mais baixa para respostas mais consistentes
                    max_tokens=4096,  # Aumentado para múltiplas questões
                    preamble="Você é um assistente útil e preciso. Sempre retorne as questões completas com as alternativas corretas marcadas."
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
    
    st.rerun()  # Recarrega para manter a rolagem consistente

col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
