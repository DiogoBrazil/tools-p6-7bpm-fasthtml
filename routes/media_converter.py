from fasthtml.common import *
from starlette.requests import Request
from pathlib import Path
import shutil
import tempfile
import logging
import os

from components.layout import page_layout

# Configuração de logging
log = logging.getLogger(__name__)

# Diretório temporário para arquivos
UPLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "fasthtml_uploads"
UPLOAD_TEMP_DIR.mkdir(exist_ok=True)

# Referência para funções importadas de modules.media_converter
# Serão definidas ao registrar as rotas
convert_video_to_mp3 = None

def register_routes(app):
    """Registra todas as rotas relacionadas à conversão de mídia"""
    # global convert_video_to_mp3
    
    # # Obter referências para as funções necessárias
    # # Estas serão inicializadas no lifespan do app principal
    # if hasattr(app.state, "convert_video_to_mp3"):
    #     convert_video_to_mp3 = app.state.convert_video_to_mp3
    # else:
    #     # Tentar importar diretamente se não estiver no app.state
    #     try:
    #         from modules.media_converter import convert_video_to_mp3 as convert_func
    #         convert_video_to_mp3 = convert_func
    #     except ImportError as e:
    #         log.error(f"Erro ao importar media_converter: {e}")
    #         convert_video_to_mp3 = None

    @app.route("/video-converter", methods=["GET"])
    def video_converter_page(request: Request):
        """Página do conversor de vídeo para MP3"""
        
        # Estilos para o loader
        loader_style = Style("""
            #video-loading {
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
        
        # JavaScript para gerenciar o loader
        loader_script = Script("""
        document.addEventListener('DOMContentLoaded', function() {
            const form = document.getElementById('video-form');
            const loadingIndicator = document.getElementById('video-loading');
            const resultArea = document.getElementById('v-result');
            
            if (form) {
                form.addEventListener('submit', function() {
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'block';
                    }
                    if (resultArea) {
                        resultArea.innerHTML = '';
                    }
                });
            }
            
            // Eventos HTMX para mostrar/esconder o loader (backup)
            document.body.addEventListener('htmx:beforeRequest', function(event) {
                if (event.detail.target && event.detail.target.id === 'v-result') {
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'block';
                    }
                }
            });
            
            document.body.addEventListener('htmx:afterRequest', function(event) {
                if (event.detail.target && event.detail.target.id === 'v-result') {
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'none';
                    }
                }
            });
        });
        """)

        # Mensagem de aviso se o conversor não estiver disponível
        warning_message = Div(
        "⚠️ O módulo de conversão de vídeo não está disponível no momento.",
        cls="error-message") if request.app.state.convert_video_to_mp3 is None else Div()

        # Formulário para upload de vídeo
        form = Form(
            Label("Carregar Vídeo:", fr="vf"), 
            Input(type="file", id="vf", name="video_file", accept="video/*", required=True),
            Button("Converter para MP3", type="submit"), 
            hx_post="/video-converter/process", 
            hx_target="#v-result", 
            hx_encoding="multipart/form-data",
            id="video-form"
        )
        
        return page_layout(
            "Conversor Vídeo->MP3", 
            Main(
                A("← Voltar", href="/", cls="back-button", 
                  style="background-color: #2196F3 !important; color: white !important; border: none !important;"), 
                H1("🎵 Conversor Vídeo para MP3"), 
                P("Selecione um arquivo de vídeo para extrair o áudio em formato MP3."),
                warning_message,
                loader_style,
                loader_script,
                form,
                Div(id="v-result", cls="result-area"),
                # Loader melhorado
                Div(
                    Div(cls="loader-spinner"), 
                    "Convertendo vídeo... Por favor, aguarde.",
                    id="video-loading"
                ),
                cls="container"
            )
        )

    @app.route("/video-converter/process", methods=["POST"])
    async def video_converter_process(request: Request):
        # Acesse a função convert_video_to_mp3 diretamente do estado da aplicação
        convert_video_to_mp3 = request.app.state.convert_video_to_mp3

        if not convert_video_to_mp3:
            return HTMLResponse("Erro: Conversão vídeo indisponível.", status_code=500)

        try:
            form_data = await request.form()
            up_file = form_data.get("video_file")
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")

        if not up_file or not up_file.filename:
            return Div("❌ Nenhum arquivo de vídeo foi selecionado.", cls="error-message")

        # Gerar nomes de arquivos com timestamp para evitar colisões
        ts = int(Path().stat().st_mtime)
        in_filename = Path(up_file.filename).name
        in_filepath = UPLOAD_TEMP_DIR / f"vin_{ts}_{in_filename}"
        out_filename = f"{Path(in_filename).stem}_{ts}.mp3"
        out_filepath = UPLOAD_TEMP_DIR / out_filename

        try:
            # Salvar o arquivo recebido para processamento
            with open(in_filepath, "wb") as buffer:
                await up_file.seek(0)
                shutil.copyfileobj(up_file.file, buffer)

            # Converter o vídeo para MP3 usando a função obtida do estado da aplicação
            success, message = convert_video_to_mp3(str(in_filepath), str(out_filepath))

            if success:
                # Se a conversão foi bem-sucedida, fornecer link para download
                download_link = f"/download/{out_filename}"
                return Div(
                    P(f"✅ {message}"), 
                    A(f"🎵 Baixar MP3", href=download_link, target="_blank"), 
                    cls="success-message"
                )
            else:
                # Se houve erro, remover o arquivo de saída se existir
                if out_filepath.exists():
                    out_filepath.unlink()
                return Div(f"❌ Falha na conversão: {message}", cls="error-message")

        except Exception as e:
            log.exception(f"Erro durante conversão de vídeo: {e}")
            # Limpar arquivos de saída que possam ter sido criados
            if 'out_filepath' in locals() and out_filepath.exists():
                try:
                    out_filepath.unlink()
                except:
                    pass
            return Div("❌ Erro interno durante o processamento do vídeo.", cls="error-message")
        finally:
            # Sempre limpar o arquivo de entrada após o uso
            if 'in_filepath' in locals() and in_filepath.exists():
                try:
                    in_filepath.unlink()
                except OSError as e:
                    log.warning(f"Erro ao remover arquivo temporário: {e}")