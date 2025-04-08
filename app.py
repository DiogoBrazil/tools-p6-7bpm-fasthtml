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
from starlette.responses import JSONResponse, FileResponse, HTMLResponse, Response
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
    elif operation == "pdf2img":
        return Form(
            Label("Carregar PDF:", fr="pdf_file"), Input(type="file", id="pdf_file", name="pdf_file", accept=".pdf", required=True),
            Label("DPI (quanto maior, melhor a qualidade):", fr="dpi"),
            Select(*[Option(f"{dpi}", value=f"{dpi}", selected=(dpi==150)) for dpi in [75, 100, 150, 200, 300]], id="dpi", name="dpi"),
            Button("Converter para Imagens", type="submit"), hx_post="/pdf-tools/pdf2img", **common_attrs
        )
    elif operation == "doc2pdf":
        return Form(
            Label("Carregar Documento (DOCX, DOC, ODT, TXT):", fr="doc_file"),
            Input(type="file", id="doc_file", name="doc_file", accept=".docx,.doc,.odt,.txt", required=True),
            P("Conversão usando LibreOffice", style="font-style:italic; font-size:0.9em; color:#666;"),
            Button("Converter para PDF", type="submit"), hx_post="/pdf-tools/doc2pdf", **common_attrs
        )
    elif operation == "sheet2pdf":
        return Form(
            Label("Carregar Planilha (XLSX, CSV, ODS):", fr="sheet_file"),
            Input(type="file", id="sheet_file", name="sheet_file", accept=".xlsx,.csv,.ods", required=True),
            P("Conversão usando LibreOffice. Múltiplas abas serão convertidas em múltiplas páginas.", style="font-style:italic; font-size:0.9em; color:#666;"),
            Button("Converter para PDF", type="submit"), hx_post="/pdf-tools/sheet2pdf", **common_attrs
        )
    elif operation == "ocr":
        return Form(
            Label("Carregar PDF para aplicar OCR:", fr="pdf_file"),
            Input(type="file", id="pdf_file", name="pdf_file", accept=".pdf", required=True),
            Label("Idioma:", fr="language"),
            Select(
                Option("Português", value="por", selected=True),
                Option("Inglês", value="eng"),
                Option("Misto (Português+Inglês)", value="por+eng"),
                id="language", name="language"
            ),
            P("OCR torna o texto pesquisável em PDFs escaneados.", style="font-style:italic; font-size:0.9em; color:#666;"),
            Button("Aplicar OCR", type="submit"), hx_post="/pdf-tools/ocr", **common_attrs
        )
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

@app.route("/pdf-tools/pdf2img", methods=["POST"])
async def pdf_to_img_process(request: Request):
    global pdf_transformer
    if not pdf_transformer:
        return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
    try:
        form_data = await request.form()
        uploaded_file = form_data.get("pdf_file")
        dpi = int(form_data.get("dpi", "150"))
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not uploaded_file or not uploaded_file.filename:
        return Div("❌ Nenhum PDF.", cls="error-message")
    
    input_filename = Path(uploaded_file.filename).name
    ts = int(Path().stat().st_mtime)
    input_filepath = UPLOAD_TEMP_DIR / f"pdfin_{ts}_{input_filename}"
    output_dir = UPLOAD_TEMP_DIR / f"pdf_images_{ts}"
    output_dir.mkdir(exist_ok=True)
    zip_filename = f"pdf_images_{ts}.zip"
    zip_filepath = UPLOAD_TEMP_DIR / zip_filename
    
    try:
        with open(input_filepath, "wb") as buffer:
            await uploaded_file.seek(0)
            shutil.copyfileobj(uploaded_file.file, buffer)
        
        image_paths, message = pdf_transformer.pdf_to_image(str(input_filepath), str(output_dir), image_format='png', dpi=dpi)
        
        if image_paths and len(image_paths) > 0:
            success, zip_message = pdf_transformer.create_zip_from_files(image_paths, str(zip_filepath))
            if success and zip_filepath.exists():
                dl_link = f"/download/{zip_filename}"
                return Div(
                    P(f"✅ PDF convertido para {len(image_paths)} imagem(ns)! {message}"),
                    A(f"📦 Baixar Imagens (ZIP)", href=dl_link, target="_blank"),
                    cls="success-message"
                )
            else:
                return Div(f"❌ Falha ao criar arquivo ZIP: {zip_message}", cls="error-message")
        else:
            return Div(f"❌ Falha ao converter PDF para imagens: {message}", cls="error-message")
    except Exception as e:
        log.exception(f"Erro pdf2img: {e}")
        return Div(f"❌ Erro interno na conversão: {str(e)}", cls="error-message")
    finally:
        # Limpar arquivos temporários
        if 'input_filepath' in locals() and input_filepath.exists():
            try:
                input_filepath.unlink()
            except OSError as e_unlink:
                log.warning(f"Erro ao remover temp PDF: {e_unlink}")
        # O diretório de saída e ZIP serão mantidos para download

@app.route("/pdf-tools/doc2pdf", methods=["POST"])
async def doc_to_pdf_process(request: Request):
    global pdf_transformer
    if not pdf_transformer:
        return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
    
    if not pdf_transformer.libreoffice_path:
        return Div("❌ LibreOffice não encontrado no servidor. Conversão indisponível.", cls="error-message")
    
    try:
        form_data = await request.form()
        uploaded_file = form_data.get("doc_file")
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not uploaded_file or not uploaded_file.filename:
        return Div("❌ Nenhum documento.", cls="error-message")
    
    input_filename = Path(uploaded_file.filename).name
    input_ext = Path(input_filename).suffix.lower()
    allowed_exts = ['.docx', '.doc', '.odt', '.txt']
    
    if input_ext not in allowed_exts:
        return Div(f"❌ Formato não suportado. Use: {', '.join(allowed_exts)}", cls="error-message")
    
    ts = int(Path().stat().st_mtime)
    input_filepath = UPLOAD_TEMP_DIR / f"docin_{ts}_{input_filename}"
    pdf_filename = f"{Path(input_filename).stem}_{ts}.pdf"
    pdf_filepath = UPLOAD_TEMP_DIR / pdf_filename
    
    try:
        with open(input_filepath, "wb") as buffer:
            await uploaded_file.seek(0)
            shutil.copyfileobj(uploaded_file.file, buffer)
        
        success, message = pdf_transformer.document_to_pdf(str(input_filepath), str(pdf_filepath))
        
        if success and pdf_filepath.exists():
            dl_link = f"/download/{pdf_filename}"
            return Div(
                P(f"✅ {message}"),
                A(f"📄 Baixar PDF", href=dl_link, target="_blank"),
                cls="success-message"
            )
        else:
            return Div(f"❌ Falha: {message}", cls="error-message")
    except Exception as e:
        log.exception(f"Erro doc2pdf: {e}")
        return Div("❌ Erro interno.", cls="error-message")
    finally:
        if 'input_filepath' in locals() and input_filepath.exists():
            try:
                input_filepath.unlink()
            except OSError as e:
                log.warning(f"Erro ao remover temp documento: {e}")

@app.route("/pdf-tools/sheet2pdf", methods=["POST"])
async def sheet_to_pdf_process(request: Request):
    global pdf_transformer
    if not pdf_transformer:
        return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
    
    if not pdf_transformer.libreoffice_path:
        return Div("❌ LibreOffice não encontrado no servidor. Conversão indisponível.", cls="error-message")
    
    try:
        form_data = await request.form()
        uploaded_file = form_data.get("sheet_file")
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not uploaded_file or not uploaded_file.filename:
        return Div("❌ Nenhuma planilha.", cls="error-message")
    
    input_filename = Path(uploaded_file.filename).name
    input_ext = Path(input_filename).suffix.lower()
    allowed_exts = ['.xlsx', '.csv', '.ods']
    
    if input_ext not in allowed_exts:
        return Div(f"❌ Formato não suportado. Use: {', '.join(allowed_exts)}", cls="error-message")
    
    ts = int(Path().stat().st_mtime)
    input_filepath = UPLOAD_TEMP_DIR / f"sheetin_{ts}_{input_filename}"
    pdf_filename = f"{Path(input_filename).stem}_{ts}.pdf"
    pdf_filepath = UPLOAD_TEMP_DIR / pdf_filename
    
    try:
        with open(input_filepath, "wb") as buffer:
            await uploaded_file.seek(0)
            shutil.copyfileobj(uploaded_file.file, buffer)
        
        # Usa a mesma função do documento para PDF
        success, message = pdf_transformer.document_to_pdf(str(input_filepath), str(pdf_filepath))
        
        if success and pdf_filepath.exists():
            dl_link = f"/download/{pdf_filename}"
            return Div(
                P(f"✅ {message}"),
                A(f"📄 Baixar PDF", href=dl_link, target="_blank"),
                cls="success-message"
            )
        else:
            extra_msg = ""
            if input_ext == '.csv':
                extra_msg = "Dica para CSV: Verifique se o arquivo está formatado corretamente (delimitadores, codificação)."
            return Div(
                P(f"❌ Falha: {message}"),
                P(extra_msg) if extra_msg else None,
                cls="error-message"
            )
    except Exception as e:
        log.exception(f"Erro sheet2pdf: {e}")
        return Div("❌ Erro interno.", cls="error-message")
    finally:
        if 'input_filepath' in locals() and input_filepath.exists():
            try:
                input_filepath.unlink()
            except OSError as e:
                log.warning(f"Erro ao remover temp planilha: {e}")

@app.route("/pdf-tools/ocr", methods=["POST"])
async def pdf_ocr_process(request: Request):
    global pdf_transformer
    if not pdf_transformer:
        return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
    
    if not pdf_transformer.ocrmypdf_installed:
        return Div("❌ OCRmyPDF não encontrado no servidor. OCR indisponível.", cls="error-message")
    
    try:
        form_data = await request.form()
        uploaded_file = form_data.get("pdf_file")
        language = form_data.get("language", "por")
    except Exception as e:
        return Div(f"❌ Erro form: {e}", cls="error-message")
    
    if not uploaded_file or not uploaded_file.filename:
        return Div("❌ Nenhum PDF.", cls="error-message")
    
    pdf_bytes = await uploaded_file.read()
    original_filename = Path(uploaded_file.filename).name
    ts = int(Path().stat().st_mtime)
    ocr_filename = f"ocr_{ts}_{original_filename}"
    
    try:
        success, processed_bytes, message = pdf_transformer.process_compression_ocr(
            pdf_bytes, 
            compression_level=-1,  # -1 significa pular compressão
            apply_ocr=True,
            ocr_language=language
        )
        
        if success and processed_bytes:
            # Salvar o arquivo OCR para download
            ocr_filepath = UPLOAD_TEMP_DIR / ocr_filename
            with open(ocr_filepath, "wb") as f:
                f.write(processed_bytes)
            
            dl_link = f"/download/{ocr_filename}"
            return Div(
                P(f"✅ OCR aplicado com sucesso! O PDF agora é pesquisável."),
                A(f"📄 Baixar PDF com OCR", href=dl_link, target="_blank"),
                cls="success-message"
            )
        else:
            return Div(f"❌ Falha ao aplicar OCR: {message}", cls="error-message")
    except Exception as e:
        log.exception(f"Erro ao aplicar OCR: {e}")
        return Div(f"❌ Erro interno: {str(e)}", cls="error-message")


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
# @app.route("/rdpm-query", methods=["GET"])
# def rdpm_query_page():
#     chat_history_init = Div(Div("Olá! Pergunte sobre o RDPM.", cls="chat-message assistant"), id="chat-history", style="height:450px; overflow-y:auto; border:1px solid #eee; padding:1rem; margin-bottom:1rem; background:white; border-radius:5px;")
#     form = Form(Input(type="text", name="question", placeholder="Sua pergunta...", required=True, autocomplete="off", style="flex-grow:1;"), Button("Enviar", type="submit"),
#         style="display:flex; gap:0.5rem; margin-top:1rem;", hx_post="/rdpm-query/ask", hx_target="#chat-history", hx_swap="beforeend", hx_indicator="#rdpm-load", **{"_=":"on htmx:afterRequest reset() me"})
#     status = Div("⚠️ Agente RDPM não inicializado.", cls="error-message", style="margin-bottom:1rem;") if not rdpm_agent_initialized else Div()
#     return page_layout("Consulta RDPM", Main(A("← Voltar", href="/", cls="back-button"), H1("⚖️ Consulta RDPM"), status, chat_history_init, form,
#         P(id="rdpm-load", cls_="htmx-indicator", style="display:none;", content="Pensando..."), cls="container"))
@app.route("/rdpm-query", methods=["GET"])
def rdpm_query_page():
    # Estilo CSS para o chat incluindo os novos estilos para o contexto
    chat_style = Style("""
        .chat-container {
    height: 450px;
    overflow-y: auto;
    border: 1px solid #e0e0e0;
    padding: 1rem;
    margin-bottom: 1rem;
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.chat-message {
    margin: 0.8rem 0;
    padding: 0.8rem;
    border-radius: 8px;
    position: relative;
    max-width: 85%;
    line-height: 1.5;
}

.user {
    background-color: #e3f2fd;
    color: #0d47a1;
    margin-left: auto;
    text-align: right;
    padding-left: 2.8rem; /* Mais espaço para o ícone */
}

.assistant {
    background-color: #f5f5f5;
    color: #333;
    margin-right: auto;
    padding-left: 2.8rem; /* Mais espaço para o ícone */
}

.chat-icon {
    position: absolute;
    left: 0.7rem; /* Ajustado para dar mais espaço */
    top: 50%;
    transform: translateY(-50%);
    width: 1.8rem;
    height: 1.8rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
    /* Removida a cor de fundo */
}

.thinking {
    padding: 0.8rem;
    border-radius: 8px;
    background-color: #f9f9f9;
    color: #757575;
    display: flex;
    align-items: center;
    margin-right: auto;
    max-width: 85%;
    position: relative;
    padding-left: 2.8rem; /* Consistente com outras mensagens */
    margin: 0.8rem 0;
}

.dot-animation {
    display: inline-block;
}

.dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background-color: #757575;
    margin: 0 2px;
    animation: bounce 1.5s infinite ease-in-out;
}

.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
}

.chat-input-container {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
}

.chat-input {
    flex-grow: 1;
    padding: 0.7rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 1rem;
    height: 40px; /* Altura específica para o input */
    box-sizing: border-box; /* Garante que padding não aumente o tamanho */
}

.send-button {
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0 1.2rem;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.2s;
    height: 40px; /* Mesma altura do input */
    line-height: 40px; /* Centraliza o texto verticalmente */
    display: flex;
    align-items: center;
    justify-content: center;
}

.send-button:hover {
    background-color: #0b7dda;
}

.error-message {
    background-color: #ffebee;
    color: #c62828;
    padding: 0.5rem;
    border-radius: 4px;
    margin-bottom: 1rem;
}

/* Estilo para o botão voltar */
.back-button {
    background-color: #2196F3 !important; /* Azul para o botão voltar */
    color: white !important;
    border: none !important;
    border-radius: 4px;
    padding: 0.5rem 1rem;
    text-decoration: none;
    font-size: 0.9rem;
    transition: background-color 0.2s;
    display: inline-block;
    margin-bottom: 1.5rem;
}

.back-button:hover {
    background-color: #0b7dda !important;
    box-shadow: 0 3px 5px rgba(0,0,0,0.1);
}

/* Estilos para o expander e contexto */
.context-expander {
    margin-top: 0.5rem;
    font-size: 0.85rem;
    color: #666;
    cursor: pointer;
    user-select: none;
}

.context-expander:hover {
    color: #2196F3;
}

.context-content {
    display: none;
    margin-top: 0.5rem;
    padding: 0.8rem;
    background-color: #f9f9f9;
    border-radius: 4px;
    border-left: 3px solid #ccc;
}

.context-item {
    margin-bottom: 0.8rem;
    padding-bottom: 0.8rem;
    border-bottom: 1px solid #eee;
}

.context-item:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
}

.context-page {
    font-weight: bold;
    margin-bottom: 0.3rem;
    color: #555;
}

.context-text {
    font-style: italic;
    color: #666;
    line-height: 1.4;
}
    """)
    
    # JavaScript para o chat
    chat_script = Script("""
    document.addEventListener('DOMContentLoaded', function() {
        const inputField = document.getElementById('question-input');
        const chatForm = document.getElementById('chat-form');
        const chatContainer = document.getElementById('chat-history');
        
        // Função para rolar para o final do chat
        function scrollToBottom() {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        // Função para adicionar a mensagem do usuário e o loader
        function addUserMessageAndLoader(question) {
            // Mostrar a mensagem do usuário imediatamente
            const userMessage = document.createElement('div');
            userMessage.className = 'chat-message user';
            userMessage.innerHTML = `
                <div class="chat-icon">👤</div>
                ${question}
            `;
            chatContainer.appendChild(userMessage);
            
            // Criar e adicionar o indicador de "pensando"
            const thinkingIndicator = document.createElement('div');
            thinkingIndicator.className = 'thinking';
            thinkingIndicator.id = 'thinking-indicator';
            thinkingIndicator.innerHTML = `
                <div class="chat-icon">⚖️</div>
                Processando 
                <div class="dot-animation">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </div>
            `;
            chatContainer.appendChild(thinkingIndicator);
            
            // Rolar para o final
            scrollToBottom();
        }
        
        // Função para adicionar a resposta do assistente com contexto
        function addAssistantResponse(answer, contextSources = [], isError = false) {
            // Remover o indicador de pensamento
            const thinkingIndicator = document.getElementById('thinking-indicator');
            if (thinkingIndicator) {
                thinkingIndicator.remove();
            }
            
            // Adicionar a resposta como uma nova mensagem
            const messageClass = isError ? 'chat-message assistant error-message' : 'chat-message assistant';
            const assistantMessage = document.createElement('div');
            assistantMessage.className = messageClass;
            
            // HTML base da mensagem
            let messageHTML = `
                <div class="chat-icon">⚖️</div>
                ${answer}
            `;
            
            // Adicionar expander e contexto se houver fontes
            if (contextSources && contextSources.length > 0) {
                const contextId = 'context-' + Date.now(); // ID único para o contexto
                
                messageHTML += `
                    <div class="context-expander" onclick="toggleContext('${contextId}')">
                        🔍 Ver trechos do RDPM utilizados (${contextSources.length})
                    </div>
                    <div id="${contextId}" class="context-content">
                `;
                
                // Adicionar cada fonte do contexto
                contextSources.forEach(source => {
                    messageHTML += `
                        <div class="context-item">
                            <div class="context-page">Página: ${source.page}</div>
                            <div class="context-text">${source.content}</div>
                        </div>
                    `;
                });
                
                messageHTML += `</div>`;
            }
            
            assistantMessage.innerHTML = messageHTML;
            chatContainer.appendChild(assistantMessage);
            
            // Rolar para o final
            scrollToBottom();
        }
        
        // Função para processar a pergunta
        function processQuestion(question) {
            // Adicionar mensagem e loader
            addUserMessageAndLoader(question);
            
            // Fazer requisição AJAX ao servidor
            fetch('/rdpm-query/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: 'question=' + encodeURIComponent(question)
            })
            .then(response => response.json())  // Agora esperamos JSON
            .then(data => {
                console.log('Resposta JSON:', data);  // Log para debug
                
                if (data.success) {
                    // Sucesso - mostrar a resposta com o contexto
                    addAssistantResponse(data.answer, data.context_sources || []);
                } else {
                    // Erro - mostrar a mensagem de erro
                    const errorMsg = data.error || "Desculpe, ocorreu um erro ao processar sua pergunta.";
                    addAssistantResponse(errorMsg, [], true);
                }
            })
            .catch(error => {
                console.error('Erro na requisição:', error);
                addAssistantResponse("Desculpe, ocorreu um erro de comunicação. Por favor, tente novamente.", [], true);
            });
        }
        
        // Evento de pressionar Enter no campo de texto
        if (inputField) {
            inputField.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    
                    // Só processar se tiver conteúdo
                    const question = inputField.value.trim();
                    if (question !== '') {
                        processQuestion(question);
                        inputField.value = '';  // Limpar o campo
                    }
                }
            });
        }
        
        // Evento de clicar no botão de enviar
        if (chatForm) {
            chatForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                // Só processar se tiver conteúdo
                const question = inputField.value.trim();
                if (question !== '') {
                    processQuestion(question);
                    inputField.value = '';  // Limpar o campo
                }
            });
        }
    });
    
    // Função global para alternar a visibilidade do contexto
    window.toggleContext = function(contextId) {
        const contextElement = document.getElementById(contextId);
        if (contextElement) {
            const currentDisplay = contextElement.style.display;
            contextElement.style.display = currentDisplay === 'block' ? 'none' : 'block';
        }
    };
    """)
    
    # Status do agente
    status = Div("⚠️ Agente RDPM não inicializado. As consultas não funcionarão corretamente.", 
                cls="error-message") if not rdpm_agent_initialized else Div()
    
    # Mensagem inicial de boas-vindas
    welcome_message = Div(
        Div("⚖️", cls="chat-icon"),
        "Olá! Sou o assistente do RDPM. Como posso ajudar com suas dúvidas sobre o Regulamento Disciplinar?",
        cls="chat-message assistant"
    )
    
    # Container de histórico de chat
    chat_container = Div(
        welcome_message,
        id="chat-history",
        cls="chat-container"
    )
    
    # Formulário de entrada
    chat_form = Form(
        Input(
            type="text", 
            id="question-input",
            name="question", 
            placeholder="Digite sua pergunta sobre o RDPM...", 
            required=True,
            autocomplete="off",
            cls="chat-input"
        ),
        Button("Enviar", type="submit", cls="send-button"),
        id="chat-form",
        cls="chat-input-container"
    )
    
    return page_layout(
        "Consulta RDPM",
        Main(
            A("← Voltar", href="/", cls="back-button"),
            H1("⚖️ Consulta ao RDPM"),
            P("Tire suas dúvidas sobre o Regulamento Disciplinar da Polícia Militar."),
            status,
            chat_style,
            chat_container,
            chat_form,
            chat_script,
            cls="container"
        )
    )

@app.route("/rdpm-query/ask", methods=["POST"])
async def rdpm_query_ask(question: Annotated[str, Form()] = ""):
    from starlette.responses import JSONResponse
    
    if not rdpm_agent_initialized or not query_rdpm:
        return JSONResponse({
            "success": False, 
            "error": "Agente RDPM não inicializado"
        })
    
    if not question or not question.strip():
        return JSONResponse({"success": False, "error": "Pergunta vazia"})
    
    log.info(f"RDPM Query: {question[:50]}...")
    resp_dict = query_rdpm(question)
    
    # Retornar JSON com a resposta e contexto
    if resp_dict:
        answer = resp_dict.get("answer", "Não consegui processar sua pergunta.")
        
        # Extrair e formatar o contexto
        context_sources = []
        if "context" in resp_dict and resp_dict["context"]:
            for doc in resp_dict["context"]:
                # Extrair número da página (similar à versão Streamlit)
                page_num = doc.metadata.get('page', 'N/A')
                page_display = page_num + 1 if isinstance(page_num, int) else 'N/A'
                
                # Extrair conteúdo da página (limitado a 300 caracteres por clareza)
                page_content = doc.page_content.strip()
                if len(page_content) > 300:
                    page_content = page_content[:300] + "..."
                
                # Adicionar à lista de fontes
                context_sources.append({
                    "page": page_display,
                    "content": page_content
                })
        
        log.info(f"Resposta gerada para '{question[:30]}...': '{answer[:50]}...' com {len(context_sources)} fontes")
        return JSONResponse({
            "success": True, 
            "answer": answer,
            "context_sources": context_sources
        })
    else:
        log.error(f"Falha ao gerar resposta para '{question[:30]}...'")
        return JSONResponse({
            "success": False, 
            "error": "Erro ao processar a pergunta"
        })


# --- Calculadora de Prescrição (Esqueleto) ---
@app.route("/prescription-calculator", methods=["GET"])
def prescription_calculator_page():
    # Precisa implementar o formulário completo aqui
    return page_layout("Calculadora de Prescrição", Main(A("← Voltar", href="/", cls="back-button"), H1("⏳ Calculadora de Prescrição"), P("Implementação pendente."), cls="container"))


# --- Execução com Uvicorn ---
if __name__ == "__main__":
    # reload=False é geralmente melhor para execução via Docker
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)