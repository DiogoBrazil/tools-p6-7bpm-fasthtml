import uvicorn
from fasthtml.common import *
from fasthtml.core import FastHTML
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import secrets
import logging
from pathlib import Path
import tempfile

# Importar componentes
from components.layout import page_layout
from components.ui import tool_card

# Importar rotas
from routes import home, pdf_tools, text_corrector, media_converter, transcriber, rdpm_query, prescription

# Importar utilitários
from utils.task_manager import initialize_async_processor, shutdown_async_processor, submit_task, get_task_status
from utils.file_utils import UPLOAD_TEMP_DIR, download_file_route

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Constantes e Caminhos
MODULES_DIR = Path(__file__).parent / "modules"
FILES_DIR = Path(__file__).parent / "files"
STATIC_DIR = Path(__file__).parent / "static"

# Verificar diretório temporário
UPLOAD_TEMP_DIR.mkdir(exist_ok=True)
log.info(f"Diretório temporário para uploads: {UPLOAD_TEMP_DIR}")

@asynccontextmanager
async def lifespan(app: FastHTML):
    """Gerencia recursos durante o ciclo de vida da aplicação"""
    log.info("Iniciando Lifespan - Carregando modelos e inicializando módulos...")
    startup_success = True

    try:
        # 1. Inicializar o processador assíncrono
        log.info("Inicializando processamento assíncrono...")
        await initialize_async_processor()
        app.state.submit_task = submit_task
        app.state.get_task_status = get_task_status
        
        # 2. Inicializar TextCorrector
        try:
            from modules.text_corrector import TextCorrector
            app.state.text_corrector = TextCorrector()
            if not app.state.text_corrector.is_configured():
                log.warning("TextCorrector (API LLM) não configurado.")
        except Exception as tc_e:
            log.error(f"Erro ao inicializar TextCorrector: {tc_e}", exc_info=True)
            app.state.text_corrector = None

        # 3. Inicializar PDFTransformer
        try:
            from modules.pdf_transformer import PDFTransformer
            app.state.pdf_transformer = PDFTransformer()
            log.info("PDFTransformer inicializado.")
        except Exception as pdf_e:
            log.error(f"Erro ao inicializar PDFTransformer: {pdf_e}", exc_info=True)
            app.state.pdf_transformer = None
            startup_success = False

        # 4. Tentar carregar Modelo Whisper
        # 4. Tentar carregar Modelo Whisper
        try:
            from modules.media_converter import load_whisper_model_instance, transcribe_audio_file, convert_video_to_mp3
            app.state.whisper_model = load_whisper_model_instance()
            if app.state.whisper_model is not None:  # Verificar se o modelo foi carregado
                app.state.transcribe_audio_file = transcribe_audio_file
                app.state.convert_video_to_mp3 = convert_video_to_mp3
                log.info("Modelo Whisper carregado globalmente.")
            else:
                log.error("Falha ao carregar modelo Whisper.")
        except Exception as whisper_e:
            log.error(f"Erro ao carregar recursos de mídia: {whisper_e}", exc_info=True)
            app.state.whisper_model = None

        # 5. Tentar inicializar Agente RDPM
        try:
            from modules.rdpm_agent import initialize_rdpm_agent, query_rdpm
            
            if hasattr(app.state, "text_corrector") and app.state.text_corrector:
                app.state.rdpm_agent_initialized = initialize_rdpm_agent(llm_client=app.state.text_corrector.get_llm_client())
                app.state.query_rdpm = query_rdpm
                
                if not app.state.rdpm_agent_initialized:
                    log.error("Falha ao inicializar o Agente RDPM.")
                else:
                    log.info("Agente RDPM inicializado globalmente.")
            else:
                log.warning("TextCorrector não inicializado, pulando Agente RDPM.")
                app.state.rdpm_agent_initialized = False
        except Exception as rag_e:
            log.error(f"Erro ao inicializar Agente RDPM: {rag_e}", exc_info=True)
            app.state.rdpm_agent_initialized = False

        if startup_success:
            log.info("Lifespan iniciado com sucesso (alguns componentes podem estar indisponíveis).")
        else:
            log.error("Lifespan iniciado com erros na inicialização de componentes.")

    except Exception as e:
        log.critical(f"Erro crítico não capturado durante o Lifespan startup: {e}", exc_info=True)

    yield # Aplicação roda aqui

    log.info("Encerrando Lifespan...")
    # Limpar recursos
    try:
        # Fechar o executor de tarefas assíncronas
        shutdown_async_processor()
    except Exception as cleanup_e:
        log.error(f"Erro durante limpeza de recursos: {cleanup_e}", exc_info=True)


# Inicialização da Aplicação FastHTML
app = FastHTML(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(32))

# Montar Diretório Estático
if STATIC_DIR.exists() and STATIC_DIR.is_dir():
    try:
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
        log.info(f"Diretório estático '{STATIC_DIR}' montado em '/static'")
    except Exception as mount_err:
        log.error(f"Erro ao montar diretório estático '{STATIC_DIR}': {mount_err}")

# Rota de download comum
@app.route("/download/{filename:path}", methods=["GET"])
async def download_file(filename: str):
    """Rota para download de arquivos gerados"""
    return download_file_route(None, filename)

# Rota para verificar estado de tarefas assíncronas
@app.route("/task-status/{task_id}", methods=["GET"])
async def task_status(task_id: str):
    """Retorna o status atual de uma tarefa assíncrona"""
    status = get_task_status(task_id)
    if status:
        # Filtrar dados sensíveis ou grandes do resultado
        if 'result' in status and isinstance(status['result'], str) and len(status['result']) > 100:
            status['result'] = '[Conteúdo disponível]'
        return JSONResponse(status)
    return JSONResponse({"status": "not_found"}, status_code=404)

# Registrar rotas
home.register_routes(app)
pdf_tools.register_routes(app)
text_corrector.register_routes(app)
media_converter.register_routes(app)
transcriber.register_routes(app)
rdpm_query.register_routes(app)
prescription.register_routes(app)

# Execução com Uvicorn
if __name__ == "__main__":
    # Aumente workers e configure limites de concorrência
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=False,
        workers=4,  # Número de processos worker
        limit_concurrency=20,  # Limita quantidade de conexões simultâneas
        timeout_keep_alive=30  # Tempo antes de encerrar conexões idle
    )