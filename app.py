# app.py (Atualizado - Corrigido para usar app.mount com StaticFiles)

import uvicorn
from fasthtml.common import *
from fasthtml.core import FastHTML
from starlette.responses import HTMLResponse
import functools
from starlette.staticfiles import StaticFiles  # <<< Importar StaticFiles
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.requests import Request
from starlette.datastructures import UploadFile, FormData
from contextlib import asynccontextmanager
import os
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Union, Annotated
import io

# --- Configuração de Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# --- Carregar Módulos Backend ---
try:
    from modules.text_corrector import TextCorrector
    from modules.media_converter import (
        load_whisper_model_instance,
        transcribe_audio_file,
        convert_video_to_mp3
    )
    from modules.pdf_transformer import PDFTransformer
    from modules.rdpm_agent import (
        initialize_rdpm_agent,
        query_rdpm
    )
    # from modules.prescription_calculator import calculate_prescription # Exemplo
except ImportError as e:
    log.error(f"Erro ao importar módulos backend: {e}. Verifique se os arquivos existem e não há erros de sintaxe.")
    TextCorrector = None
    load_whisper_model_instance = None
    transcribe_audio_file = None
    convert_video_to_mp3 = None
    PDFTransformer = None
    initialize_rdpm_agent = None
    query_rdpm = None

# --- Constantes e Caminhos ---
MODULES_DIR = Path(__file__).parent / "modules"
FILES_DIR = Path(__file__).parent / "files"
STATIC_DIR = Path(__file__).parent / "static"
UPLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "fasthtml_uploads"
try:
    UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"Diretório temporário para uploads: {UPLOAD_TEMP_DIR}")
except OSError as e:
    log.error(f"Não foi possível criar o diretório temporário {UPLOAD_TEMP_DIR}: {e}")

# --- Globais para Recursos Inicializados ---
whisper_model = None
rdpm_agent_initialized = False
text_corrector: Union[TextCorrector, None] = None
pdf_transformer: Union[PDFTransformer, None] = None

@asynccontextmanager
async def lifespan(app: FastHTML):
    global whisper_model, rdpm_agent_initialized, text_corrector, pdf_transformer
    log.info("Iniciando Lifespan - Carregando modelos e inicializando módulos...")
    startup_success = True

    try:
        # 1. Inicializar TextCorrector
        if TextCorrector:
            try:
                text_corrector = TextCorrector()
                if not text_corrector.is_configured():
                    log.warning("TextCorrector (API LLM) não configurado.")
            except Exception as tc_e:
                log.error(f"Erro ao inicializar TextCorrector: {tc_e}", exc_info=True)
                text_corrector = None
        else:
            log.error("Classe TextCorrector não encontrada/importada.")

        # 2. Inicializar PDFTransformer
        if PDFTransformer:
            try:
                pdf_transformer = PDFTransformer()
                log.info("PDFTransformer inicializado.")
            except Exception as pdf_e:
                log.error(f"Erro ao inicializar PDFTransformer: {pdf_e}", exc_info=True)
                pdf_transformer = None
                startup_success = False
        else:
            log.error("Classe PDFTransformer não encontrada/importada.")
            startup_success = False

        # 3. Tentar carregar Modelo Whisper
        if load_whisper_model_instance:
            log.info("Tentando carregar modelo Whisper...")
            try:
                whisper_model = load_whisper_model_instance()
                if whisper_model is None:
                    log.error("Falha ao carregar modelo Whisper.")
                else:
                    log.info("Modelo Whisper carregado globalmente.")
            except Exception as whisper_e:
                log.error(f"Erro durante chamada a load_whisper_model_instance: {whisper_e}", exc_info=True)
                whisper_model = None
        else:
            log.warning("Função load_whisper_model_instance não encontrada/importada.")

        # 4. Tentar inicializar Agente RDPM
        if initialize_rdpm_agent and text_corrector:
            log.info("Tentando inicializar Agente RDPM...")
            try:
                rdpm_agent_initialized = initialize_rdpm_agent(llm_client=text_corrector.get_llm_client())
                if not rdpm_agent_initialized:
                    log.error("Falha ao inicializar o Agente RDPM.")
                else:
                    log.info("Agente RDPM inicializado globalmente.")
            except Exception as rag_e:
                log.error(f"Erro durante chamada a initialize_rdpm_agent: {rag_e}", exc_info=True)
                rdpm_agent_initialized = False
        elif not text_corrector:
            log.warning("TextCorrector não inicializado, pulando Agente RDPM.")
        else:
            log.warning("Função initialize_rdpm_agent não encontrada/importada.")

        if startup_success:
            log.info("Lifespan iniciado com sucesso (alguns componentes podem estar indisponíveis).")
        else:
            log.error("Lifespan iniciado com erros na inicialização de componentes.")

    except Exception as e:
        log.critical(f"Erro crítico não capturado durante o Lifespan startup: {e}", exc_info=True)

    yield # Aplicação roda aqui

    log.info("Encerrando Lifespan...")
    # Limpeza futura aqui


# --- Inicialização da Aplicação FastHTML ---
# Cria a app primeiro (SEM middlewares aqui)
app = FastHTML(lifespan=lifespan)

# --- Adicionar decorador de componente manualmente ---
# Implementação alternativa do sistema de componentes
def component(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

# Adicionar o método component à instância app
app.component = component

# --- Montar Diretório Estático ---
# Monta o diretório 'static' na URL '/static' usando StaticFiles do Starlette
if STATIC_DIR and STATIC_DIR.exists() and STATIC_DIR.is_dir():
    try:
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
        log.info(f"Diretório estático '{STATIC_DIR}' montado em '/static'")
    except Exception as mount_err:
        log.error(f"Erro ao montar diretório estático '{STATIC_DIR}': {mount_err}")
elif STATIC_DIR:
    log.warning(f"Diretório estático '{STATIC_DIR}' não encontrado ou não é um diretório. Arquivos estáticos (CSS) não serão servidos.")
else:
    log.warning("Variável STATIC_DIR não definida. Arquivos estáticos (CSS) não serão servidos.")


# --- Componente de Layout Base ---
@app.component
def page_layout(title: str, *body_content):
    return Html(
        Head(
            Title(title),
            Meta(charset="UTF-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Link(rel="stylesheet", href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"),
            Link(rel="stylesheet", href="/static/style.css")
        ),
        Body(
            *body_content,
            Footer(
                P("© 2024 - Seção de Justiça e Disciplina - 7º Batalhão de Polícia Militar"),
                P("Desenvolvido pelo 1º SGT QPPM Mat. ******023 DIOGO RIBEIRO"),
                cls="footer"
            ),
            Script(src="https://unpkg.com/htmx.org@1.9.10")
        )
    )


# --- Componente Card (Reutilizável) ---
@app.component
def tool_card(id:str, icon: str, title: str, description: str, items: list[str], link: str, link_text: str):
    return Div(
        Div(
            Span(icon, cls="tool-icon"),
            H2(title),
            P(description),
            Ul(*[Li(item) for item in items])
        ),
        A(link_text, href=link, cls="button-link"),
        id=id,
        cls="tool-card"
    )

# --- Rota Principal (Home) ---
@app.route("/", methods=["GET"])
def home():
    cards = [
        tool_card(id="card-pdf", icon="📄", title="Ferramentas PDF", description="Comprima, OCR, junte, converta PDFs.",
                  items=["Juntar, comprimir, OCR", "Doc/Planilha/Imagem → PDF", "PDF → Docx/Imagem"],
                  link="/pdf-tools", link_text="ABRIR FERRAMENTAS PDF"),
        tool_card(id="card-text", icon="📝", title="Corretor de Texto", description="Revise e corrija textos usando IA.",
                  items=["Correção gramatical", "Ortografia e pontuação", "Português Brasileiro"],
                  link="/text-corrector", link_text="ABRIR CORRETOR"),
        tool_card(id="card-media", icon="🎵", title="Conversor para MP3", description="Converta arquivos de vídeo para áudio MP3.",
                  items=["Suporta MP4, AVI, MOV...", "Extração rápida de áudio", "Saída em MP3 (192k)"],
                  link="/video-converter", link_text="ABRIR CONVERSOR MP3"),
        tool_card(id="card-transcribe", icon="🎤", title="Transcritor de Áudio", description="Converta arquivos de áudio em texto.",
                  items=["Suporta MP3, WAV, M4A...", "Transcrição Whisper", "Refinamento IA opcional"],
                  link="/audio-transcriber", link_text="ABRIR TRANSCRITOR"),
        tool_card(id="card-rdpm", icon="⚖️", title="Consulta RDPM", description="Tire dúvidas sobre o RDPM.",
                  items=["Busca no texto oficial", "Respostas baseadas no RDPM", "Assistente IA especializado"],
                  link="/rdpm-query", link_text="CONSULTAR RDPM"),
        tool_card(id="card-prescricao", icon="⏳", title="Calculadora de Prescrição", description="Calcule prazos prescricionais disciplinares.",
                  items=["Considera natureza da infração", "Trata interrupções", "Adiciona períodos de suspensão"],
                  link="/prescription-calculator", link_text="ABRIR CALCULADORA"),
    ]
    return page_layout(
        "Ferramentas - 7ºBPM/P-6",
        Header(
            H1("🛠️ Ferramentas da Seção de Justiça e Disciplina (P/6)"),
            P("Bem-vindo ao portal de ferramentas digitais para otimizar processos administrativos.")
        ),
        Main(
             Div(*cards, cls="card-grid"),
             cls="wide-container"
        )
    )

# --- Ferramenta: Corretor de Texto ---
@app.route("/text-corrector", methods=["GET"])
def text_corrector_form():
    global text_corrector
    api_warning = Div()
    if not text_corrector or not text_corrector.is_configured():
        api_warning = Div("⚠️ API de correção não configurada. Funcionalidade limitada.", cls="error-message", style="margin-bottom: 1rem;")

    form_content = Form(
        Label("📄 Cole o texto a ser corrigido:", fr="text_input"),
        Textarea(id="text_input", name="text_input", rows=10, required=True),
        Button("Corrigir Texto", type="submit"),
        Div(id="result-area", cls_="result-area"),
        hx_post="/text-corrector", hx_target="#result-area", hx_swap="innerHTML", hx_indicator="#loading-indicator"
    )
    loading_indicator = Div(I(cls="fas fa-spinner fa-spin"), " Corrigindo...", id="loading-indicator", cls_="htmx-indicator", style="margin-top:1rem; display: none;")

    return page_layout(
        "Corretor de Texto - 7ºBPM/P-6",
        Main(
            A("← Voltar", href="/", cls="back-button"), H1("📝 Corretor de Texto"),
            P("Utilize IA para corrigir gramática e ortografia."), api_warning,
            form_content, loading_indicator, cls="container"
        )
    )

@app.route("/text-corrector", methods=["POST"])
async def text_corrector_process(text_input: Annotated[str, Form()] = ""):
    global text_corrector
    if not text_corrector or not text_corrector.is_configured():
        return Div("❌ API de correção não configurada.", cls="error-message")
    if not text_input or not text_input.strip():
        return Div("⚠️ Insira algum texto.", cls="error-message")

    try:
        log.info("Recebido pedido de correção...")
        corrected_text = text_corrector.correct_text(text_input)
        if corrected_text is not None:
            log.info("Correção bem-sucedida.")
            return Div(H3("📝 Texto Corrigido:"), Textarea(corrected_text, readonly=True, rows=10, id="corrected-text-output"), cls="success-message")
        else:
            log.error("Falha na API de correção.")
            return Div("❌ Falha ao corrigir. API indisponível ou erro.", cls="error-message")
    except Exception as e:
        log.error(f"Erro inesperado na correção: {e}", exc_info=True)
        return Div(f"❌ Erro interno: {str(e)}", cls="error-message")


# --- Ferramenta: PDF Tools ---
@app.route("/pdf-tools", methods=["GET"])
def pdf_tools_page():
     return page_layout(
         "Ferramentas PDF",
         Main(
             A("← Voltar", href="/", cls="back-button"), H1("📄 Ferramentas PDF"),
             P("Selecione a operação desejada:"),
             Div(
                 Select(
                     Option("Selecione...", value=""), Option("Comprimir PDF", value="compress"),
                     Option("Juntar PDFs", value="merge"), Option("Imagens para PDF", value="img2pdf"),
                     Option("PDF para DOCX", value="pdf2docx"), Option("PDF para Imagens", value="pdf2img"),
                     Option("Documento para PDF", value="doc2pdf"), Option("Planilha para PDF", value="sheet2pdf"),
                     Option("Tornar PDF Pesquisável (OCR)", value="ocr"),
                     name="pdf_operation", id="pdf_operation_select",
                     hx_get="/pdf-tools/form", hx_target="#pdf-form-container", hx_swap="innerHTML", hx_trigger="change"
                 ),
                 Div(id="pdf-form-container", style="margin-top: 1rem;")
             ),
             Div(id="pdf-result-area", cls_="result-area"),
             P(id="pdf-loading", cls_="htmx-indicator", style="margin-top:1rem; display: none;", content="Processando PDF..."),
             cls="container"
         )
     )

@app.route("/pdf-tools/form", methods=["GET"])
async def get_pdf_form(request: Request):
    operation = request.query_params.get("pdf_operation", "")
    common_attrs = {"hx_target": "#pdf-result-area", "hx_encoding": "multipart/form-data", "hx_swap": "innerHTML", "hx_indicator": "#pdf-loading"}

    if operation == "compress":
        return Form(
            Label("Carregar PDF para Comprimir:", fr="pdf_file"), Input(type="file", id="pdf_file", name="pdf_file", accept=".pdf", required=True),
            Label("Nível (0-4):", fr="level"), Select(*[Option(str(i), value=str(i), selected=(i==3)) for i in range(5)], id="level", name="level"),
            Button("Comprimir PDF", type="submit"), hx_post="/pdf-tools/compress", **common_attrs
        )
    elif operation == "merge":
         return Form(
            Label("Carregar 2+ PDFs:", fr="pdf_files"), Input(type="file", id="pdf_files", name="pdf_files", accept=".pdf", multiple=True, required=True),
            Button("Juntar PDFs", type="submit"), hx_post="/pdf-tools/merge", **common_attrs
        )
    elif operation == "img2pdf":
         return Form(
            Label("Carregar Imagens:", fr="img_files"), Input(type="file", id="img_files", name="img_files", accept="image/jpeg,image/png", multiple=True, required=True),
            Button("Imagens para PDF", type="submit"), hx_post="/pdf-tools/img2pdf", **common_attrs
        )
    elif operation == "pdf2docx":
         return Form(
            Label("Carregar PDF:", fr="pdf_file"), Input(type="file", id="pdf_file", name="pdf_file", accept=".pdf", required=True),
            Div(Input(type="checkbox", id="apply_ocr", name="apply_ocr", value="true"), Label(" Tentar OCR", fr="apply_ocr"), style="margin: 0.5rem 0;"),
            Button("Converter para DOCX", type="submit"), hx_post="/pdf-tools/pdf2docx", **common_attrs
        )
    # Adicionar elif para pdf2img, doc2pdf, sheet2pdf, ocr
    # ...
    else: return P("")


# --- Rotas POST PDF --- (Rotas de processamento como antes, usando pdf_transformer global)
@app.route("/pdf-tools/compress", methods=["POST"])
async def pdf_compress_process(request: Request):
    global pdf_transformer
    if not pdf_transformer:
        return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
    try:
        form_data = await request.form()
        uploaded_file = form_data.get("pdf_file")
        level = int(form_data.get("level", "3"))
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not uploaded_file or not uploaded_file.filename:
        return Div("❌ Nenhum PDF.", cls="error-message")
    
    file_bytes = await uploaded_file.read()
    original_filename = Path(uploaded_file.filename).name
    ts = int(Path().stat().st_mtime)
    processed_filename = f"comp_{ts}_{original_filename}"
    processed_filepath = UPLOAD_TEMP_DIR / processed_filename
    
    try:
        success, result_bytes, message = pdf_transformer.process_compression_ocr(file_bytes, level, False)
        if success and result_bytes:
            with open(processed_filepath, "wb") as f:
                f.write(result_bytes)
            dl_link = f"/download/{processed_filename}"
            return Div(P(f"✅ {message}"), A(f"📄 Baixar", href=dl_link, target="_blank"), cls="success-message")
        else:
            return Div(f"❌ Falha: {message}", cls="error-message")
    except Exception as e:
        log.exception(f"Erro compressão PDF: {e}")
        return Div("❌ Erro interno.", cls="error-message")

@app.route("/pdf-tools/merge", methods=["POST"])
async def pdf_merge_process(request: Request):
    global pdf_transformer
    if not pdf_transformer:
        return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
    try:
        form_data = await request.form()
        uploaded_files = form_data.getlist("pdf_files")
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not uploaded_files or len(uploaded_files) < 2:
        return Div("❌ Selecione 2+ PDFs.", cls="error-message")
    
    pdf_bytes_list = []
    filenames = []
    
    try:
        for f in uploaded_files:
            if f.filename:
                pdf_bytes_list.append(await f.read())
                filenames.append(Path(f.filename).name)
        
        if len(pdf_bytes_list) < 2:
            return Div("❌ 2+ PDFs válidos.", cls="error-message")
        
        success, result_bytes, message = pdf_transformer.merge_pdfs(pdf_bytes_list)
        if success and result_bytes:
            ts = int(Path().stat().st_mtime)
            merged_filename = f"merged_{ts}.pdf"
            merged_filepath = UPLOAD_TEMP_DIR / merged_filename
            with open(merged_filepath, "wb") as f:
                f.write(result_bytes)
            dl_link = f"/download/{merged_filename}"
            return Div(P(f"✅ {message}"), A(f"📄 Baixar", href=dl_link, target="_blank"), cls="success-message")
        else:
            return Div(f"❌ Falha: {message}", cls="error-message")
    except Exception as e:
        log.exception(f"Erro merge PDF: {e}")
        return Div("❌ Erro interno.", cls="error-message")

@app.route("/pdf-tools/img2pdf", methods=["POST"])
async def pdf_img2pdf_process(request: Request):
    global pdf_transformer
    if not pdf_transformer:
        return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
    try:
        form_data = await request.form()
        uploaded_files = form_data.getlist("img_files")
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not uploaded_files:
        return Div("❌ Nenhuma imagem.", cls="error-message")
    
    img_bytes_list = []
    filenames = []
    
    try:
        for f in uploaded_files:
            if f.filename:
                img_bytes_list.append(await f.read())
                filenames.append(Path(f.filename).name)
        
        if not img_bytes_list:
            return Div("❌ Nenhuma imagem válida.", cls="error-message")
        
        ts = int(Path().stat().st_mtime)
        pdf_filename = f"images_{ts}.pdf"
        pdf_filepath = UPLOAD_TEMP_DIR / pdf_filename
        success, message = pdf_transformer.image_to_pdf(img_bytes_list, str(pdf_filepath))
        
        if success:
            dl_link = f"/download/{pdf_filename}"
            return Div(P(f"✅ {message}"), A(f"📄 Baixar", href=dl_link, target="_blank"), cls="success-message")
        else:
            if pdf_filepath.exists():
                pdf_filepath.unlink()
            return Div(f"❌ Falha: {message}", cls="error-message")
    except Exception as e:
        log.exception(f"Erro img2pdf: {e}")
        if 'pdf_filepath' in locals() and pdf_filepath.exists():
            try:
                pdf_filepath.unlink()
            except Exception:
                pass
        return Div("❌ Erro interno.", cls="error-message")

@app.route("/pdf-tools/pdf2docx", methods=["POST"])
async def pdf_pdf2docx_process(request: Request):
    global pdf_transformer
    if not pdf_transformer:
        return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
    try:
        form_data = await request.form()
        uploaded_file = form_data.get("pdf_file")
        apply_ocr = form_data.get("apply_ocr") == "true"
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not uploaded_file or not uploaded_file.filename:
        return Div("❌ Nenhum PDF.", cls="error-message")
    
    input_filename = Path(uploaded_file.filename).name
    ts = int(Path().stat().st_mtime)
    input_filepath = UPLOAD_TEMP_DIR / f"pdfin_{ts}_{input_filename}"
    docx_filename = f"{Path(input_filename).stem}_{ts}.docx"
    docx_filepath = UPLOAD_TEMP_DIR / docx_filename
    
    try:
        with open(input_filepath, "wb") as buffer:
            await uploaded_file.seek(0)
            shutil.copyfileobj(uploaded_file.file, buffer)
        
        success, message = pdf_transformer.pdf_to_docx(str(input_filepath), str(docx_filepath), apply_ocr=apply_ocr)
        if success:
            dl_link = f"/download/{docx_filename}"
            css_class = "success-message" if "sucesso" in message.lower() else "warning-message"
            return Div(P(f"✅ {message}"), A(f"📄 Baixar", href=dl_link, target="_blank"), cls=css_class)
        else:
            if docx_filepath.exists():
                docx_filepath.unlink()
            return Div(f"❌ Falha: {message}", cls="error-message")
    except Exception as e:
        log.exception(f"Erro pdf2docx: {e}")
        if 'docx_filepath' in locals() and docx_filepath.exists():
            try:
                docx_filepath.unlink()
            except Exception:
                pass
        return Div("❌ Erro interno.", cls="error-message")
    finally:
        if 'input_filepath' in locals() and input_filepath.exists():
            try:
                input_filepath.unlink()
            except OSError as e_unlink:
                log.warning(f"Erro ao remover temp PDF: {e_unlink}")


# --- Rota de Download Genérica ---
@app.route("/download/{filename:path}", methods=["GET"])
async def download_file(filename: str):
    try:
        safe_filename = Path(filename).name
        if not safe_filename or ".." in safe_filename:
            raise ValueError("Nome inválido")
        file_path = UPLOAD_TEMP_DIR / safe_filename
        if file_path.is_file():
            log.info(f"Servindo download: {safe_filename}")
            media_type = 'application/octet-stream'
            ext = safe_filename.lower().split('.')[-1]
            if ext == 'pdf':
                media_type = 'application/pdf'
            elif ext == 'zip':
                media_type = 'application/zip'
            elif ext == 'docx':
                media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif ext == 'txt':
                media_type = 'text/plain'
            elif ext == 'mp3':
                media_type = 'audio/mpeg'
            return FileResponse(file_path, filename=safe_filename, media_type=media_type)
        else:
            return HTMLResponse("Arquivo não encontrado.", status_code=404)
    except Exception as e:
        log.error(f"Erro download {filename}: {e}")
        return HTMLResponse("Erro download.", status_code=500)


# --- Conversor Vídeo -> MP3 ---
@app.route("/video-converter", methods=["GET"])
def video_converter_page():
    form = Form(Label("Carregar Vídeo:", fr="vf"), Input(type="file", id="vf", name="video_file", accept="video/*", required=True),
        Button("Converter para MP3", type="submit"), hx_post="/video-converter/process", hx_target="#v-result", hx_encoding="multipart/form-data", hx_indicator="#v-load")
    return page_layout("Conversor Vídeo->MP3", Main(A("← Voltar", href="/", cls="back-button"), H1("🎵 Conversor Vídeo para MP3"), P("Selecione vídeo."), form,
        Div(id="v-result", cls_="result-area"), P(id="v-load", cls_="htmx-indicator", style="display:none;", content="Convertendo..."), cls="container"))

@app.route("/video-converter/process", methods=["POST"])
async def video_converter_process(request: Request):
    if not convert_video_to_mp3:
        return HTMLResponse("Erro: Conversão vídeo indisponível.", status_code=500)
    try:
        form_data = await request.form()
        up_file = form_data.get("video_file")
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not up_file or not up_file.filename:
        return Div("❌ Nenhum vídeo.", cls="error-message")
    
    ts = int(Path().stat().st_mtime)
    in_f = Path(up_file.filename).name
    in_p = UPLOAD_TEMP_DIR / f"vin_{ts}_{in_f}"
    out_f = f"{Path(in_f).stem}_{ts}.mp3"
    out_p = UPLOAD_TEMP_DIR / out_f
    
    try:
        with open(in_p, "wb") as b:
            await up_file.seek(0)
            shutil.copyfileobj(up_file.file, b)
        
        ok, msg = convert_video_to_mp3(str(in_p), str(out_p))
        if ok:
            dl = f"/download/{out_f}"
            return Div(P(f"✅ {msg}"), A(f"🎵 Baixar", href=dl, target="_blank"), cls="success-message")
        else:
            if out_p.exists():
                out_p.unlink()
            return Div(f"❌ Falha: {msg}", cls="error-message")
    except Exception as e:
        log.exception(f"Erro vídeo conv: {e}")
        if 'out_p' in locals() and out_p.exists():
            try:
                out_p.unlink()
            except:
                pass
        return Div("❌ Erro interno.", cls="error-message")
    finally:
        if 'in_p' in locals() and in_p.exists():
            try:
                in_p.unlink()
            except OSError as e:
                log.warning(f"Erro del temp vid: {e}")


# --- Transcritor de Áudio ---
@app.route("/audio-transcriber", methods=["GET"])
def audio_transcriber_page():
    form = Form(Label("Carregar Áudio:", fr="af"), Input(type="file", id="af", name="audio_file", accept="audio/*", required=True),
        Button("Transcrever", type="submit"), hx_post="/audio-transcriber/process", hx_target="#a-result", hx_encoding="multipart/form-data", hx_indicator="#a-load")
    return page_layout("Transcritor de Áudio", Main(A("← Voltar", href="/", cls="back-button"), H1("🎤 Transcritor"), P("Selecione áudio."), form,
        Div(id="a-result", cls_="result-area"), P(id="a-load", cls_="htmx-indicator", style="display:none;", content="Transcrevendo..."), cls="container"))

@app.route("/audio-transcriber/process", methods=["POST"])
async def audio_transcriber_process(request: Request):
    global whisper_model, text_corrector
    if not whisper_model or not transcribe_audio_file:
        return Div("❌ Erro: Transcrição indisponível.", cls="error-message")
    try:
        form_data = await request.form()
        up_file = form_data.get("audio_file")
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not up_file or not up_file.filename:
        return Div("❌ Nenhum áudio.", cls="error-message")
    
    ts = int(Path().stat().st_mtime)
    in_f = Path(up_file.filename).name
    in_p = UPLOAD_TEMP_DIR / f"audin_{ts}_{in_f}"
    
    try:
        with open(in_p, "wb") as b:
            await up_file.seek(0)
            shutil.copyfileobj(up_file.file, b)
        
        ok, msg, raw_txt = transcribe_audio_file(str(in_p), model=whisper_model)
        if not ok:
            return Div(f"❌ Falha Transcr: {msg}", cls="error-message")
        
        corr_txt = None
        corr_msg = P()
        if text_corrector and text_corrector.is_configured():
            corr_txt = text_corrector.correct_transcription(raw_txt)
            if corr_txt is None:
                corr_msg = P("⚠️ Falha ao refinar.", style="font-style:italic; color:orange;")
        else:
            corr_msg = P("ℹ️ Refinamento IA não disponível.", style="font-style:italic;")
        
        res = [H3("Original:"), Textarea(raw_txt or " ", readonly=True, rows=8, style="margin-bottom:1rem;")]
        if corr_txt is not None:
            res.extend([H3("Refinada:"), Textarea(corr_txt, readonly=True, rows=8)])
        res.append(corr_msg)
        return Div(*res, cls="success-message")
    except Exception as e:
        log.exception(f"Erro Transcr Áudio: {e}")
        return Div("❌ Erro interno.", cls="error-message")
    finally:
        if 'in_p' in locals() and in_p.exists():
            try:
                in_p.unlink()
            except OSError as e:
                log.warning(f"Erro del temp aud: {e}")


# --- Consulta RDPM ---
@app.route("/rdpm-query", methods=["GET"])
def rdpm_query_page():
    chat_history_init = Div(Div("Olá! Pergunte sobre o RDPM.", cls="chat-message assistant"), id="chat-history", style="height:450px; overflow-y:auto; border:1px solid #eee; padding:1rem; margin-bottom:1rem; background:white; border-radius:5px;")
    form = Form(Input(type="text", name="question", placeholder="Sua pergunta...", required=True, autocomplete="off", style="flex-grow:1;"), Button("Enviar", type="submit"),
        style="display:flex; gap:0.5rem; margin-top:1rem;", hx_post="/rdpm-query/ask", hx_target="#chat-history", hx_swap="beforeend", hx_indicator="#rdpm-load", **{"_=":"on htmx:afterRequest reset() me"})
    status = Div("⚠️ Agente RDPM não inicializado.", cls="error-message", style="margin-bottom:1rem;") if not rdpm_agent_initialized else Div()
    return page_layout("Consulta RDPM", Main(A("← Voltar", href="/", cls="back-button"), H1("⚖️ Consulta RDPM"), status, chat_history_init, form,
        P(id="rdpm-load", cls_="htmx-indicator", style="display:none;", content="Pensando..."), cls="container"))

@app.route("/rdpm-query/ask", methods=["POST"])
async def rdpm_query_ask(question: Annotated[str, Form()] = ""):
    if not rdpm_agent_initialized or not query_rdpm:
        return Div("Erro: Agente indisponível.", cls="chat-message error-message")
    if not question or not question.strip():
        return Response(status_code=204) # No Content
    user_msg = Div(question, cls="chat-message user", style="margin:0.5rem 0;")
    log.info(f"RDPM Query: {question[:50]}...")
    resp_dict = query_rdpm(question)
    if resp_dict:
        answer = resp_dict.get("answer", "Não consegui processar.")
        ass_msg = Div(answer, cls="chat-message assistant", style="margin:0.5rem 0;")
    else:
        ass_msg = Div("Erro ao buscar resposta.", cls="chat-message error-message")
    return Raw(str(user_msg) + str(ass_msg))


# --- Calculadora de Prescrição (Esqueleto) ---
@app.route("/prescription-calculator", methods=["GET"])
def prescription_calculator_page():
    # Precisa implementar o formulário completo aqui
    return page_layout("Calculadora de Prescrição", Main(A("← Voltar", href="/", cls="back-button"), H1("⏳ Calculadora de Prescrição"), P("Implementação pendente."), cls="container"))


# --- Execução com Uvicorn ---
if __name__ == "__main__":
    # reload=False é geralmente melhor para execução via Docker
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)