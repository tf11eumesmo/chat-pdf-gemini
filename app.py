import streamlit as st
import cohere
from pypdf import PdfReader
from pathlib import Path
import re
import easyocr
from PIL import Image
import io

st.set_page_config(page_title="Chat com PDF", page_icon="📚", layout="wide")

# ---------- CSS ----------
st.markdown("""
<style>
/* ... (mantenha todo o seu CSS original aqui) ... */

/* Estilo para área de upload de imagem */
.image-upload-container {
    display: flex;
    align-items: center;
    gap: 10px;
}

.preview-image {
    max-width: 100px;
    max-height: 100px;
    border-radius: 8px;
    border: 2px solid #2196f3;
}
</style>
""", unsafe_allow_html=True)

# ---------- Inicialização do OCR ----------
@st.cache_resource
def load_ocr_reader():
    """Carrega o leitor OCR uma única vez (cache)"""
    return easyocr.Reader(['pt', 'en'], gpu=False, verbose=False)

# ---------- Sidebar (mantida igual) ----------
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

# ---------- Session State ----------
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
if "uploaded_image_text" not in st.session_state:
    st.session_state.uploaded_image_text = None  # Armazena texto extraído da imagem

# ---------- Funções ----------
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

def extract_text_from_image(image_file, ocr_reader):
    """Extrai texto de imagem usando EasyOCR"""
    try:
        image = Image.open(image_file)
        # Pré-processamento: converter para RGB se necessário
        if image.mode in ('RGBA', 'P', 'LA'):
            image = image.convert('RGB')
        
        # Extrair texto com OCR
        results = ocr_reader.readtext(image, detail=0)
        extracted_text = " ".join(results).strip()
        
        if not extracted_text:
            return None, "Nenhum texto reconhecido na imagem"
        return extracted_text, None
    except Exception as e:
        return None, f"Erro ao processar imagem: {str(e)}"

def formatar_resposta(texto):
    """Formata a resposta para diferentes tipos de questão"""
    texto = texto.replace('</div>', '').replace('<div>', '').replace('<br>', '\n')
    texto = re.sub(r'<[^>]+>', '', texto).strip()
    
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
    
    texto = texto.replace('**', '').replace('\n', '<br>')
    return texto

# ---------- Carregar PDF quando mudar ----------
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
        st.session_state.uploaded_image_text = None  # Resetar texto da imagem

# ---------- TOPO FIXO ----------
st.markdown(f"""
<div class="top-fixed">
<div class="materia-info">
<strong>📚 Matéria Atual:</strong> {st.session_state.materia_nome} • 
<small>{st.session_state.caracteres_count:,} caracteres</small>
</div>
<div class="chat-title">💬 Chat de Questões</div>
</div>
""", unsafe_allow_html=True)

# ---------- Exibir Histórico de Mensagens ----------
for message in st.session_state.messages:
    if message["role"] == "user":
        pergunta_limpa = re.sub(r'<[^>]+>', '', message["content"].replace('</div>', '').replace('<div>', '').replace('<br>', ' ')).strip()
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

# ---------- Área de Input: Chat + Upload de Foto ----------
st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)  # Espaçamento para o topo fixo

# Colunas para input de texto e botão de foto
input_col, upload_col = st.columns([4, 1])

with input_col:
    prompt = st.chat_input("Envie suas questões sobre a matéria selecionada")

with upload_col:
    uploaded_file = st.file_uploader(
        "📷", 
        type=['png', 'jpg', 'jpeg', 'webp'],
        help="Enviar foto da questão",
        key="image_uploader",
        label_visibility="collapsed"
    )

# Processar imagem enviada
if uploaded_file is not None and uploaded_file != st.session_state.get("last_uploaded_file"):
    st.session_state.last_uploaded_file = uploaded_file
    st.session_state.uploaded_image_text = None  # Resetar para novo processamento
    
    with st.spinner("🔍 Lendo imagem com OCR..."):
        ocr_reader = load_ocr_reader()
        texto_imagem, erro = extract_text_from_image(uploaded_file, ocr_reader)
        
        if erro:
            st.warning(f"⚠️ {erro}")
        else:
            st.session_state.uploaded_image_text = texto_imagem
            st.success("✅ Texto extraído! Clique em 'Enviar' para enviar a pergunta.")
            # Auto-preencher o prompt com o texto extraído (opcional)
            # prompt = texto_imagem  # Não funciona diretamente, veja alternativa abaixo

# Dica: Como o st.chat_input não pode ser preenchido programaticamente,
# mostramos uma mensagem informativa se houver texto extraído
if st.session_state.uploaded_image_text and not prompt:
    st.info(f"📋 **Texto extraído da imagem:**\n\n_{st.session_state.uploaded_image_text[:200]}..._\n\nDigite ou cole no chat acima e envie!")

# ---------- Processar Mensagem do Usuário ----------
if prompt:
    # Usar texto da imagem se disponível e o prompt estiver vazio ou for genérico
    final_prompt = prompt
    if st.session_state.uploaded_image_text and len(prompt.strip()) < 10:
        # Se o usuário digitou pouco e há texto da imagem, usa o texto OCR
        final_prompt = st.session_state.uploaded_image_text
        st.session_state.uploaded_image_text = None  # Consumir para não reutilizar
    
    if not st.session_state.pdf_content:
        st.error("❌ Selecione uma matéria primeiro!")
    else:
        st.session_state.messages.append({"role": "user", "content": final_prompt})
        
        pergunta_limpa = re.sub(r'<[^>]+>', '', final_prompt.replace('</div>', '').replace('<div>', '').replace('<br>', ' ')).strip()
        
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
{final_prompt}

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

# ---------- Botão Limpar Histórico ----------
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        st.session_state.messages = []
        st.session_state.uploaded_image_text = None
        if "last_uploaded_file" in st.session_state:
            del st.session_state.last_uploaded_file
        st.rerun()
