# modules/rdpm_agent.py

import os
import logging
# REMOVED: import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI  # Needs OpenAI client details
from langchain.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from typing import Union
from openai import OpenAI # Import OpenAI client type hint

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# --- Constantes ---
PDF_PATH = "files/rdpm.pdf"
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
CACHE_DIR = os.getenv("HF_HOME", "/app/.cache/huggingface") # Use HF_HOME from env if set

# --- Module-Level Globals (to store initialized resources) ---
RDP_RETRIEVER = None
RDP_RAG_CHAIN = None

# --- Initialization Functions (Called once via lifespan) ---

def initialize_rdpm_retriever():
    """
    Loads PDF, splits, creates embeddings, and returns the Retriever.
    Called once during application startup.
    Returns:
        FAISS retriever instance or None if initialization fails.
    """
    log.info(f"Initializing RDPM Retriever from: {PDF_PATH}")
    if not os.path.exists(PDF_PATH):
        log.error(f"Arquivo PDF do RDPM não encontrado em: {PDF_PATH}")
        return None
    try:
        loader = PyPDFLoader(PDF_PATH)
        # Handle potential errors during load
        try:
             docs = loader.load()
        except Exception as load_err:
             log.error(f"Erro ao carregar o PDF '{PDF_PATH}' com PyPDFLoader: {load_err}", exc_info=True)
             return None

        if not docs:
            log.error(f"Nenhum documento carregado do PDF: {PDF_PATH}")
            return None

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        splits = text_splitter.split_documents(docs)
        if not splits:
            log.error("Falha ao dividir o documento PDF em chunks.")
            return None
        log.info(f"RDPM PDF carregado e dividido em {len(splits)} chunks.")

        # Initialize Embeddings
        log.info(f"Inicializando embeddings: {EMBEDDING_MODEL_NAME} (Cache: {CACHE_DIR})...")
        try:
            # Certifique-se que o diretório de cache existe
            os.makedirs(CACHE_DIR, exist_ok=True)
            embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL_NAME,
                cache_folder=CACHE_DIR, # Use cache_folder
                model_kwargs={'device': 'cpu'} # Forçar CPU se não tiver GPU configurada
            )
            log.info("Embeddings HuggingFace inicializados.")
        except Exception as emb_err:
             log.error(f"Erro ao inicializar embeddings '{EMBEDDING_MODEL_NAME}': {emb_err}", exc_info=True)
             return None

        # Create FAISS index and retriever
        log.info("Criando índice FAISS e retriever...")
        try:
            vector_index = FAISS.from_documents(splits, embeddings)
            retriever = vector_index.as_retriever(search_type="similarity", search_kwargs={'k': 5}) # k=5 para mais contexto
            log.info("Retriever FAISS para RDPM criado com sucesso.")
            return retriever
        except Exception as faiss_err:
            log.error(f"Erro ao criar índice FAISS ou retriever: {faiss_err}", exc_info=True)
            return None

    except Exception as e:
        log.error(f"Erro inesperado em initialize_rdpm_retriever: {e}", exc_info=True)
        return None

def create_rag_chain(retriever, llm_client: OpenAI):
    """
    Creates the Langchain RAG chain using the provided retriever and LLM client.

    Args:
        retriever: The initialized FAISS retriever instance.
        llm_client: The initialized OpenAI compatible client instance (from TextCorrector).

    Returns:
        Langchain retrieval chain instance or None if creation fails.
    """
    log.info("Criando a RAG chain para RDPM...")
    if not retriever:
        log.error("Falha ao criar RAG chain: Retriever não fornecido.")
        return None
    if not llm_client:
        log.error("Falha ao criar RAG chain: Cliente LLM não fornecido.")
        return None

    try:
        # Define o modelo LLM Langchain usando os detalhes do cliente fornecido
        llm = ChatOpenAI(
            # Passa a chave e base URL diretamente do objeto cliente
            openai_api_key=llm_client.api_key,
            openai_api_base=str(llm_client.base_url),
            # Pega o nome do modelo das variáveis de ambiente (consistente com TextCorrector)
            model_name=os.getenv("OPENAI_MODEL_NAME", "deepseek-chat"),
            temperature=0.1,
            max_tokens=1000 # Ajuste conforme necessário
        )
        log.info(f"Langchain ChatOpenAI configurado com modelo: {llm.model_name}")

        # Define o template do prompt (mantido como antes)
        prompt_template = """Você é um assistente especializado e muito preciso sobre o Regulamento Disciplinar da Polícia Militar de Rondônia (RDPM). Sua tarefa é responder à pergunta do usuário baseando-se SOMENTE nos trechos do RDPM fornecidos abaixo como contexto.

        Contexto do RDPM:
        {context}

        Pergunta: {input}

        Instruções IMPORTANTES:
        1. Responda de forma clara e objetiva, utilizando as informações presentes EXCLUSIVAMENTE no contexto.
        2. NÃO invente informações, artigos ou detalhes que não estejam no contexto.
        3. Se a resposta para a pergunta não puder ser encontrada no contexto fornecido, diga explicitamente: "A informação solicitada não foi encontrada nos trechos fornecidos do RDPM."
        4. Não adicione opiniões pessoais ou informações externas ao RDPM.
        5. Seja direto na resposta.

        Resposta:"""
        prompt = ChatPromptTemplate.from_template(prompt_template)

        # Cria as cadeias Langchain
        document_chain = create_stuff_documents_chain(llm, prompt)
        retrieval_chain = create_retrieval_chain(retriever, document_chain)
        log.info("RAG chain para RDPM criada com sucesso.")
        return retrieval_chain

    except Exception as e:
        log.error(f"Erro ao criar a RAG chain: {e}", exc_info=True)
        return None

# --- Função de Inicialização Principal (Chamada pelo lifespan de app.py) ---

def initialize_rdpm_agent(llm_client: Union[OpenAI, None]):
    """
    Inicializa todos os componentes do agente RDPM (retriever e chain)
    e armazena nas variáveis globais do módulo.

    Args:
        llm_client: O cliente LLM já inicializado.

    Returns:
        bool: True se a inicialização foi bem-sucedida, False caso contrário.
    """
    global RDP_RETRIEVER, RDP_RAG_CHAIN
    log.info("Iniciando inicialização completa do Agente RDPM...")

    # Etapa 1: Inicializar Retriever
    if RDP_RETRIEVER is None: # Evita re-inicializar se já feito
        RDP_RETRIEVER = initialize_rdpm_retriever()

    if RDP_RETRIEVER is None:
        log.error("Falha ao inicializar o Retriever RDPM. Agente RDPM inativo.")
        return False

    # Etapa 2: Criar RAG Chain (requer retriever e llm_client)
    if llm_client is None:
        log.error("Cliente LLM não fornecido. Não é possível criar a RAG Chain.")
        # O retriever pode ter inicializado, mas a chain não. Marcamos como falha.
        return False

    if RDP_RAG_CHAIN is None: # Evita re-criar
        RDP_RAG_CHAIN = create_rag_chain(RDP_RETRIEVER, llm_client)

    if RDP_RAG_CHAIN is None:
        log.error("Falha ao criar a RAG Chain RDPM. Agente RDPM inativo.")
        return False

    log.info("Agente RDPM inicializado com sucesso.")
    return True

# --- Função de Query (Chamada pelas rotas FastHTML) ---

def query_rdpm(question: str) -> dict | None:
    """
    Executa uma consulta no RAG chain pré-inicializado.

    Args:
        question (str): A pergunta do usuário.

    Returns:
        dict: O dicionário de resposta da chain (com 'answer', 'context', etc.)
              ou None se o agente não estiver inicializado ou ocorrer um erro.
    """
    global RDP_RAG_CHAIN
    if RDP_RAG_CHAIN is None:
        log.error("Tentativa de query RDPM, mas a RAG chain não está inicializada.")
        return None

    if not question or not question.strip():
        log.warning("Tentativa de query RDPM com pergunta vazia.")
        return {"answer": "Por favor, faça uma pergunta.", "context": []} # Retorna resposta padrão

    log.info(f"Executando query RDPM: '{question[:50]}...'")
    try:
        response = RDP_RAG_CHAIN.invoke({"input": question})
        # response já é um dicionário se a chamada for bem-sucedida
        log.info("Query RDPM concluída.")
        return response
    except Exception as e:
        log.error(f"Erro durante a invocação da RAG chain RDPM: {e}", exc_info=True)
        return None # Indica erro na consulta