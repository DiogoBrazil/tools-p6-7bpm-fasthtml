import asyncio
from fasthtml.common import *
from starlette.requests import Request
from pathlib import Path
import shutil
import tempfile
import logging
import os
import io
import json

from components.layout import page_layout

# Configuração de logging
log = logging.getLogger(__name__)

# Diretório temporário para uploads
UPLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "fasthtml_uploads"
UPLOAD_TEMP_DIR.mkdir(exist_ok=True)

# Semáforo para limitar processamentos de PDF simultâneos
pdf_processing_semaphore = asyncio.Semaphore(3)

# Variável para armazenar a instância do PDFTransformer
pdf_transformer = None

def register_routes(app):
    """Registra todas as rotas relacionadas às ferramentas PDF"""

    @app.route("/pdf-tools", methods=["GET"])
    def pdf_tools_page(request: Request):
        """Página principal das ferramentas PDF"""
        
        # JavaScript para gerenciar o loader e limpar mensagens
        custom_script = Script("""
        document.addEventListener('DOMContentLoaded', function() {
            // Referência ao select de operações
            const operationSelect = document.getElementById('pdf_operation_select');
            const resultArea = document.getElementById('pdf-result-area');
            const loadingIndicator = document.getElementById('pdf-loading');
            
            // Função para limpar mensagens anteriores
            function clearResults() {
                if (resultArea) {
                    resultArea.innerHTML = '';
                }
            }
            
            // Limpar resultados quando trocar de operação
            if (operationSelect) {
                operationSelect.addEventListener('change', function() {
                    clearResults();
                });
            }
            
            // Eventos HTMX para mostrar/esconder o loader
            document.body.addEventListener('htmx:beforeRequest', function(event) {
                // Se a requisição for de algum formulário PDF, mostra o loader
                if (event.detail.target && event.detail.target.id === 'pdf-result-area') {
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'block';
                    }
                    clearResults();
                }
            });
            
            document.body.addEventListener('htmx:afterRequest', function(event) {
                // Esconde o loader após qualquer requisição
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                }
            });
        });
        """)
        
        # Estilo do loader
        loader_style = Style("""
            #pdf-loading {
                display: none;
                margin-top: 1rem;
                padding: 1rem;
                background-color: #e9f5ff;
                border-radius: 5px;
                text-align: center;
                border: 1px solid #b8daff;
            }
            
            .loader-spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid rgba(0, 123, 255, 0.3);
                border-radius: 50%;
                border-top-color: #007bff;
                animation: spin 1s ease-in-out infinite;
                margin-right: 10px;
                vertical-align: middle;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
        """)
        
        # Mensagem de aviso se o módulo PDF não estiver disponível
        warning_message = Div(
        "⚠️ O módulo de processamento de PDF não está disponível no momento.",
        cls="error-message") if request.app.state.pdf_transformer is None else Div()
        
        return page_layout(
            "Ferramentas PDF",
            Main(
                A("← Voltar", href="/", cls="back-button", 
                  style="background-color: #2196F3 !important; color: white !important; border: none !important;"), 
                H1("📄 Ferramentas PDF"),
                P("Selecione a operação desejada:"),
                
                warning_message,
                
                # CSS e JavaScript personalizados
                loader_style,
                custom_script,
                
                Div(
                    Select(
                        Option("Selecione...", value=""), 
                        Option("Comprimir PDF", value="compress"),
                        Option("Juntar PDFs", value="merge"), 
                        Option("Imagens para PDF", value="img2pdf"),
                        Option("PDF para DOCX", value="pdf2docx"), 
                        Option("PDF para Imagens", value="pdf2img"),
                        Option("Documento para PDF", value="doc2pdf"), 
                        Option("Planilha para PDF", value="sheet2pdf"),
                        Option("Tornar PDF Pesquisável (OCR)", value="ocr"),
                        name="pdf_operation", 
                        id="pdf_operation_select",
                        hx_get="/pdf-tools/form", 
                        hx_target="#pdf-form-container", 
                        hx_swap="innerHTML", 
                        hx_trigger="change"
                    ),
                    Div(id="pdf-form-container", style="margin-top: 1rem;")
                ),
                
                # Área de resultado
                Div(id="pdf-result-area", cls="result-area"),
                
                # Loader melhorado
                Div(
                    Div(cls="loader-spinner"), 
                    "Processando... Por favor, aguarde.",
                    id="pdf-loading"
                ),
                
                cls="container"
            )
        )

    @app.route("/pdf-tools/form", methods=["GET"])
    async def get_pdf_form(request: Request):
        """Retorna o formulário para a operação PDF selecionada"""
        operation = request.query_params.get("pdf_operation", "")
        
        # Atributos comuns para todos os formulários
        common_attrs = {
            "hx_target": "#pdf-result-area", 
            "hx_encoding": "multipart/form-data", 
            "hx_swap": "innerHTML"
        }

        if operation == "compress":
            return Form(
                Label("Carregar PDF para Comprimir:", fr="pdf_file"), 
                Input(type="file", id="pdf_file", name="pdf_file", accept=".pdf", required=True),
                Label("Nível (0-4):", fr="level"), 
                Select(*[Option(str(i), value=str(i), selected=(i==3)) for i in range(5)], id="level", name="level"),
                Button("Comprimir PDF", type="submit"), 
                hx_post="/pdf-tools/compress", 
                **common_attrs
            )
        elif operation == "merge":
            return Form(
                Label("Carregar 2+ PDFs:", fr="pdf_files"), 
                Input(type="file", id="pdf_files", name="pdf_files", accept=".pdf", multiple=True, required=True),
                Button("Juntar PDFs", type="submit"), 
                hx_post="/pdf-tools/merge", 
                **common_attrs
            )
        elif operation == "img2pdf":
            return Form(
                Label("Carregar Imagens:", fr="img_files"), 
                Input(type="file", id="img_files", name="img_files", accept="image/jpeg,image/png", multiple=True, required=True),
                Button("Imagens para PDF", type="submit"), 
                hx_post="/pdf-tools/img2pdf", 
                **common_attrs
            )
        elif operation == "pdf2docx":
            return Form(
                Label("Carregar PDF:", fr="pdf_file"), 
                Input(type="file", id="pdf_file", name="pdf_file", accept=".pdf", required=True),
                Div(
                    Input(type="checkbox", id="apply_ocr", name="apply_ocr", value="true"), 
                    Label(" Tentar OCR", fr="apply_ocr"), 
                    style="margin: 0.5rem 0;"
                ),
                Button("Converter para DOCX", type="submit"), 
                hx_post="/pdf-tools/pdf2docx", 
                **common_attrs
            )
        elif operation == "pdf2img":
            return Form(
                Label("Carregar PDF:", fr="pdf_file"), 
                Input(type="file", id="pdf_file", name="pdf_file", accept=".pdf", required=True),
                Label("DPI (quanto maior, melhor a qualidade):", fr="dpi"),
                Select(
                    *[Option(f"{dpi}", value=f"{dpi}", selected=(dpi==150)) for dpi in [75, 100, 150, 200, 300]],
                    id="dpi", 
                    name="dpi"
                ),
                Button("Converter para Imagens", type="submit"), 
                hx_post="/pdf-tools/pdf2img", 
                **common_attrs
            )
        elif operation == "doc2pdf":
            return Form(
                Label("Carregar Documento (DOCX, DOC, ODT, TXT):", fr="doc_file"),
                Input(type="file", id="doc_file", name="doc_file", accept=".docx,.doc,.odt,.txt", required=True),
                P("Conversão usando LibreOffice", style="font-style:italic; font-size:0.9em; color:#666;"),
                Button("Converter para PDF", type="submit"), 
                hx_post="/pdf-tools/doc2pdf", 
                **common_attrs
            )
        elif operation == "sheet2pdf":
            return Form(
                Label("Carregar Planilha (XLSX, CSV, ODS):", fr="sheet_file"),
                Input(type="file", id="sheet_file", name="sheet_file", accept=".xlsx,.csv,.ods", required=True),
                P("Conversão usando LibreOffice. Múltiplas abas serão convertidas em múltiplas páginas.", 
                  style="font-style:italic; font-size:0.9em; color:#666;"),
                Button("Converter para PDF", type="submit"), 
                hx_post="/pdf-tools/sheet2pdf", 
                **common_attrs
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
                    id="language", 
                    name="language"
                ),
                P("OCR torna o texto pesquisável em PDFs escaneados.", 
                  style="font-style:italic; font-size:0.9em; color:#666;"),
                Button("Aplicar OCR", type="submit"), 
                hx_post="/pdf-tools/ocr", 
                **common_attrs
            )
        else: 
            return P("")

    @app.route("/pdf-tools/compress", methods=["POST"])
    async def pdf_compress_process(request: Request):
        # Acesse o pdf_transformer diretamente do estado da aplicação
        pdf_transformer = request.app.state.pdf_transformer

        if not pdf_transformer:
            return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)

        try:
            form_data = await request.form()
            uploaded_file = form_data.get("pdf_file")
            level = int(form_data.get("level", "3"))
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")

        if not uploaded_file or not uploaded_file.filename:
            return Div("❌ Nenhum arquivo PDF fornecido.", cls="error-message")

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
                return Div(P(f"✅ {message}"), A(f"📄 Baixar PDF Comprimido", href=dl_link, target="_blank"), cls="success-message")
            else:
                return Div(f"❌ Falha na compressão: {message}", cls="error-message")
        except Exception as e:
            log.exception(f"Erro durante compressão de PDF: {e}")
            return Div("❌ Erro interno durante o processamento.", cls="error-message")
        
        

    @app.route("/pdf-tools/merge", methods=["POST"])
    async def pdf_merge_process(request: Request):
        """Processa a solicitação de junção de PDFs"""

        pdf_transformer = request.app.state.pdf_transformer

        if not pdf_transformer:
            return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
        
        try:
            form_data = await request.form()
            uploaded_files = form_data.getlist("pdf_files")
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")
        
        if not uploaded_files or len(uploaded_files) < 2:
            return Div("❌ Selecione pelo menos dois arquivos PDF.", cls="error-message")
        
        pdf_bytes_list = []
        filenames = []
        
        try:
            for f in uploaded_files:
                if f.filename:
                    pdf_bytes_list.append(await f.read())
                    filenames.append(Path(f.filename).name)
            
            if len(pdf_bytes_list) < 2:
                return Div("❌ Pelo menos dois PDFs válidos são necessários.", cls="error-message")
            
            success, result_bytes, message = pdf_transformer.merge_pdfs(pdf_bytes_list)
            if success and result_bytes:
                ts = int(Path().stat().st_mtime)
                merged_filename = f"merged_{ts}.pdf"
                merged_filepath = UPLOAD_TEMP_DIR / merged_filename
                with open(merged_filepath, "wb") as f:
                    f.write(result_bytes)
                dl_link = f"/download/{merged_filename}"
                return Div(P(f"✅ {message}"), A(f"📄 Baixar PDF Unificado", href=dl_link, target="_blank"), cls="success-message")
            else:
                return Div(f"❌ Falha na junção: {message}", cls="error-message")
        except Exception as e:
            log.exception(f"Erro durante junção de PDFs: {e}")
            return Div("❌ Erro interno durante o processamento.", cls="error-message")

    @app.route("/pdf-tools/img2pdf", methods=["POST"])
    async def pdf_img2pdf_process(request: Request):
        """Processa a solicitação de conversão de imagens para PDF"""

        pdf_transformer = request.app.state.pdf_transformer

        if not pdf_transformer:
            return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
        
        try:
            form_data = await request.form()
            uploaded_files = form_data.getlist("img_files")
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")
        
        if not uploaded_files:
            return Div("❌ Nenhuma imagem fornecida.", cls="error-message")
        
        img_bytes_list = []
        filenames = []
        
        try:
            for f in uploaded_files:
                if f.filename:
                    img_bytes_list.append(await f.read())
                    filenames.append(Path(f.filename).name)
            
            if not img_bytes_list:
                return Div("❌ Nenhuma imagem válida fornecida.", cls="error-message")
            
            ts = int(Path().stat().st_mtime)
            pdf_filename = f"images_{ts}.pdf"
            pdf_filepath = UPLOAD_TEMP_DIR / pdf_filename
            success, message = pdf_transformer.image_to_pdf(img_bytes_list, str(pdf_filepath))
            
            if success:
                dl_link = f"/download/{pdf_filename}"
                return Div(P(f"✅ {message}"), A(f"📄 Baixar PDF", href=dl_link, target="_blank"), cls="success-message")
            else:
                if pdf_filepath.exists():
                    pdf_filepath.unlink()
                return Div(f"❌ Falha na conversão: {message}", cls="error-message")
        except Exception as e:
            log.exception(f"Erro durante conversão de imagem para PDF: {e}")
            if 'pdf_filepath' in locals() and pdf_filepath.exists():
                try:
                    pdf_filepath.unlink()
                except Exception:
                    pass
            return Div("❌ Erro interno durante o processamento.", cls="error-message")

    @app.route("/pdf-tools/pdf2docx", methods=["POST"])
    async def pdf_pdf2docx_process(request: Request):
        """Processa a solicitação de conversão de PDF para DOCX"""

        pdf_transformer = request.app.state.pdf_transformer

        if not pdf_transformer:
            return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
        
        try:
            form_data = await request.form()
            uploaded_file = form_data.get("pdf_file")
            apply_ocr = form_data.get("apply_ocr") == "true"
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")
        
        if not uploaded_file or not uploaded_file.filename:
            return Div("❌ Nenhum arquivo PDF fornecido.", cls="error-message")
        
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
                return Div(P(f"✅ {message}"), A(f"📄 Baixar DOCX", href=dl_link, target="_blank"), cls=css_class)
            else:
                if docx_filepath.exists():
                    docx_filepath.unlink()
                return Div(f"❌ Falha na conversão: {message}", cls="error-message")
        except Exception as e:
            log.exception(f"Erro durante conversão de PDF para DOCX: {e}")
            if 'docx_filepath' in locals() and docx_filepath.exists():
                try:
                    docx_filepath.unlink()
                except Exception:
                    pass
            return Div("❌ Erro interno durante o processamento.", cls="error-message")
        finally:
            if 'input_filepath' in locals() and input_filepath.exists():
                try:
                    input_filepath.unlink()
                except OSError as e_unlink:
                    log.warning(f"Erro ao remover arquivo temporário: {e_unlink}")

    @app.route("/pdf-tools/pdf2img", methods=["POST"])
    async def pdf_to_img_process(request: Request):
        """Processa a solicitação de conversão de PDF para imagens"""

        pdf_transformer = request.app.state.pdf_transformer

        if not pdf_transformer:
            return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
        
        try:
            form_data = await request.form()
            uploaded_file = form_data.get("pdf_file")
            dpi = int(form_data.get("dpi", "150"))
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")
        
        if not uploaded_file or not uploaded_file.filename:
            return Div("❌ Nenhum arquivo PDF fornecido.", cls="error-message")
        
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
            
            image_paths, message = pdf_transformer.pdf_to_image(
                str(input_filepath), str(output_dir), image_format='png', dpi=dpi
            )
            
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
            log.exception(f"Erro durante conversão de PDF para imagens: {e}")
            return Div(f"❌ Erro interno durante a conversão: {str(e)}", cls="error-message")
        finally:
            # Limpar arquivos temporários
            if 'input_filepath' in locals() and input_filepath.exists():
                try:
                    input_filepath.unlink()
                except OSError as e_unlink:
                    log.warning(f"Erro ao remover arquivo temporário: {e_unlink}")

    @app.route("/pdf-tools/doc2pdf", methods=["POST"])
    async def doc_to_pdf_process(request: Request):
        """Processa a solicitação de conversão de documento para PDF"""

        pdf_transformer = request.app.state.pdf_transformer

        if not pdf_transformer:
            return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
        
        if not pdf_transformer.libreoffice_path:
            return Div("❌ LibreOffice não encontrado no servidor. Conversão indisponível.", cls="error-message")
        
        try:
            form_data = await request.form()
            uploaded_file = form_data.get("doc_file")
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")
        
        if not uploaded_file or not uploaded_file.filename:
            return Div("❌ Nenhum documento fornecido.", cls="error-message")
        
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
                return Div(f"❌ Falha na conversão: {message}", cls="error-message")
        except Exception as e:
            log.exception(f"Erro durante conversão de documento para PDF: {e}")
            return Div("❌ Erro interno durante o processamento.", cls="error-message")
        finally:
            if 'input_filepath' in locals() and input_filepath.exists():
                try:
                    input_filepath.unlink()
                except OSError as e:
                    log.warning(f"Erro ao remover arquivo temporário: {e}")

    @app.route("/pdf-tools/sheet2pdf", methods=["POST"])
    async def sheet_to_pdf_process(request: Request):
        """Processa a solicitação de conversão de planilha para PDF"""

        pdf_transformer = request.app.state.pdf_transformer

        if not pdf_transformer:
            return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
        
        if not pdf_transformer.libreoffice_path:
            return Div("❌ LibreOffice não encontrado no servidor. Conversão indisponível.", cls="error-message")
        
        try:
            form_data = await request.form()
            uploaded_file = form_data.get("sheet_file")
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")
        
        if not uploaded_file or not uploaded_file.filename:
            return Div("❌ Nenhuma planilha fornecida.", cls="error-message")
        
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
                    P(f"❌ Falha na conversão: {message}"),
                    P(extra_msg) if extra_msg else None,
                    cls="error-message"
                )
        except Exception as e:
            log.exception(f"Erro durante conversão de planilha para PDF: {e}")
            return Div("❌ Erro interno durante o processamento.", cls="error-message")
        finally:
            if 'input_filepath' in locals() and input_filepath.exists():
                try:
                    input_filepath.unlink()
                except OSError as e:
                    log.warning(f"Erro ao remover arquivo temporário: {e}")

    @app.route("/pdf-tools/ocr", methods=["POST"])
    async def pdf_ocr_process(request: Request):
        # Obter o pdf_transformer do estado da aplicação
        pdf_transformer = request.app.state.pdf_transformer
        
        if not pdf_transformer:
            return HTMLResponse("Erro: Módulo PDF não inicializado.", status_code=500)
        
        if not pdf_transformer.ocrmypdf_installed:
            return Div("❌ OCRmyPDF não encontrado no servidor. OCR indisponível.", cls="error-message")
        
        try:
            form_data = await request.form()
            uploaded_file = form_data.get("pdf_file")
            language = form_data.get("language", "por")
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")
        
        if not uploaded_file or not uploaded_file.filename:
            return Div("❌ Nenhum arquivo PDF fornecido.", cls="error-message")
        
        # Ler os bytes do arquivo fora do semáforo
        pdf_bytes = await uploaded_file.read()
        original_filename = Path(uploaded_file.filename).name
        ts = int(Path().stat().st_mtime)
        ocr_filename = f"ocr_{ts}_{original_filename}"
        
        try:
            # Usar o semáforo para limitar processamentos simultâneos
            async with pdf_processing_semaphore:
                log.info(f"Iniciando OCR para {original_filename}")
                success, processed_bytes, message = pdf_transformer.process_compression_ocr(
                    pdf_bytes, 
                    compression_level=-1,  # -1 significa pular compressão
                    apply_ocr=True,
                    ocr_language=language
                )
            
            # Código após a liberação do semáforo
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
        
    
    # A rota de download pode ficar neste arquivo ou ser movida para um utils/file_utils.py
    @app.route("/download/{filename:path}", methods=["GET"])
    async def download_file(filename: str):
        """Processa solicitações de download para arquivos processados"""
        try:
            safe_filename = Path(filename).name
            if not safe_filename or ".." in safe_filename:
                raise ValueError("Nome de arquivo inválido")
            
            file_path = UPLOAD_TEMP_DIR / safe_filename
            if file_path.is_file():
                log.info(f"Servindo download: {safe_filename}")
                
                # Determinar o tipo de mídia apropriado
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
            log.error(f"Erro ao processar download de {filename}: {e}")
            return HTMLResponse("Erro ao processar download.", status_code=500)