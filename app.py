import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import os

# Configurações da Página
st.set_page_config(page_title="Chat com PDF", page_icon="📚")

# Título
st.title("📚 Chat com PDF usando Gemini")

# Barra lateral para API Key (Segura)
with st.sidebar:
    st.header("Configurações")
    # A chave virá dos "Secrets" do Streamlit, não do input
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        st.success("✅ API Key configurada!")
    else:
        st.error("❌ API Key não encontrada nos Secrets!")
        st.info("Peça ao dono do repo para configurar nos Secrets.")

# Upload do PDF
pdf_file = st.file_uploader("Carregue seu PDF", type=["pdf"])

# Inicializar histórico de chat
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pdf_content" not in st.session_state:
    st.session_state.pdf_content = ""

# Processar PDF
if pdf_file is not None and st.session_state.pdf_content == "":
    with st.spinner("Lendo PDF..."):
        try:
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            st.session_state.pdf_content = text
            st.success(f"✅ PDF carregado ({len(text)} caracteres)")
        except Exception as e:
            st.error(f"Erro ao ler PDF: {e}")

# Mostrar histórico de chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input do usuário
if prompt := st.chat_input("Faça uma pergunta sobre o PDF..."):
    # Adiciona mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Resposta da IA
    if st.session_state.pdf_content:
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    full_prompt = f"""
                    Você é um assistente útil. Responda APENAS com base no texto abaixo.
                    Se não souber, diga que não está no documento.
                    
                    TEXTO DO PDF:
                    {st.session_state.pdf_content[:500000]}
                    
                    PERGUNTA:
                    {prompt}
                    """
                    response = model.generate_content(full_prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Erro na API: {e}")
    else:
        st.warning("Por favor, carregue um PDF primeiro.")
