# routes/transcriber.py

import asyncio
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

# Ajuste o valor '2' conforme necessário para seu hardware
audio_transcription_semaphore = asyncio.Semaphore(2)

# Referências para funções e objetos importados dos módulos
# Serão definidas ao registrar as rotas
whisper_model = None
transcribe_audio_file = None
text_corrector = None

def register_routes(app):
    """Registra todas as rotas relacionadas à transcrição de áudio"""

    @app.route("/audio-transcriber", methods=["GET"])
    def audio_transcriber_page(request: Request):
        """Página do transcritor de áudio"""
        
        # Estilo para o loader
        loader_style = Style("""
            #audio-loading {
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
            
            .transcription-step {
                color: #0066cc;
                font-weight: bold;
            }
        """)
        
        # JavaScript para gerenciar o loader
        loader_script = Script("""
        document.addEventListener('DOMContentLoaded', function() {
            const form = document.getElementById('audio-form');
            const loadingIndicator = document.getElementById('audio-loading');
            const resultArea = document.getElementById('a-result');
            let processingStarted = false;
            let processingStepTimer;
            const processingSteps = [
                "Carregando arquivo de áudio...",
                "Preparando para transcrição...",
                "Processando áudio com Whisper...",
                "Transcrevendo áudio <span class='transcription-step'>(Etapa 1/2)</span>...",
                "Refinando transcrição com IA <span class='transcription-step'>(Etapa 2/2)</span>..."
            ];
            let currentStep = 0;
            
            function updateProcessingMessage() {
                const messageElement = document.getElementById('processing-message');
                if (messageElement && processingStarted) {
                    messageElement.innerHTML = processingSteps[currentStep];
                    currentStep = (currentStep + 1) % processingSteps.length;
                }
            }
            
            if (form) {
                form.addEventListener('submit', function() {
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'block';
                        processingStarted = true;
                        currentStep = 0;
                        updateProcessingMessage();
                        processingStepTimer = setInterval(updateProcessingMessage, 5000); // Atualizar a cada 5 segundos
                    }
                    if (resultArea) {
                        resultArea.innerHTML = '';
                    }
                });
            }
            
            // Eventos HTMX para mostrar/esconder o loader
            document.body.addEventListener('htmx:beforeRequest', function(event) {
                if (event.detail.target && event.detail.target.id === 'a-result') {
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'block';
                        processingStarted = true;
                        currentStep = 0;
                        updateProcessingMessage();
                        processingStepTimer = setInterval(updateProcessingMessage, 5000);
                    }
                }
            });
            
            document.body.addEventListener('htmx:afterRequest', function(event) {
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                    processingStarted = false;
                    clearInterval(processingStepTimer);
                }
            });
        });
        """)

        # Verificar status do modelo Whisper
        whisper_model_loaded = request.app.state.whisper_model is not None
        whisper_status = P("✅ Modelo de transcrição está pronto.", style="color: green; font-weight: bold;")
        if not whisper_model_loaded:
            whisper_status = P(
                "⚠️ O modelo Whisper não foi carregado. A transcrição pode não funcionar corretamente.", 
                style="color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 5px; border: 1px solid #ffeeba;"
            )

        # Formulário de upload de áudio
        form = Form(
            Label("Carregar Arquivo de Áudio:", fr="af"), 
            Input(type="file", id="af", name="audio_file", accept="audio/*", required=True),
            P("Os formatos suportados incluem MP3, WAV, M4A, OGG, etc.", 
              style="font-size: 0.85rem; color: #666; margin-top: 0.25rem;"),
            Button("Transcrever Áudio", type="submit"), 
            hx_post="/audio-transcriber/process", 
            hx_target="#a-result", 
            hx_encoding="multipart/form-data",
            id="audio-form"
        )
        
        return page_layout(
            "Transcritor de Áudio", 
            Main(
                A("← Voltar", href="/", cls="back-button", 
                  style="background-color: #2196F3 !important; color: white !important; border: none !important;"), 
                H1("🎤 Transcritor de Áudio"), 
                P("Carregue um arquivo de áudio para transcrevê-lo automaticamente. A transcrição pode levar alguns minutos dependendo do tamanho do arquivo."),
                whisper_status,
                loader_style,
                loader_script,
                form,
                Div(id="a-result", cls="result-area"),
                # Loader melhorado
                Div(
                    Div(cls="loader-spinner"), 
                    Span("Carregando arquivo de áudio...", id="processing-message"),
                    P("Transcrições de áudio podem levar alguns minutos. Por favor, aguarde.", 
                      style="font-size: 0.85rem; margin-top: 0.5rem;"),
                    id="audio-loading"
                ),
                cls="container"
            )
        )

    @app.route("/audio-transcriber/process", methods=["POST"])
    async def audio_transcriber_process(request: Request):
        # Obtenha os recursos do estado da aplicação
        whisper_model = request.app.state.whisper_model
        transcribe_audio_file = request.app.state.transcribe_audio_file
        text_corrector = request.app.state.text_corrector
        
        if not whisper_model or not transcribe_audio_file:
            return Div("❌ Erro: Transcrição indisponível. O modelo Whisper não foi carregado.", cls="error-message")
        
        try:
            form_data = await request.form()
            up_file = form_data.get("audio_file")
        except Exception as e:
            return Div(f"❌ Erro ao processar formulário: {e}", cls="error-message")
        
        if not up_file or not up_file.filename:
            return Div("❌ Nenhum arquivo de áudio selecionado.", cls="error-message")
        
        ts = int(Path().stat().st_mtime)
        in_f = Path(up_file.filename).name
        in_p = UPLOAD_TEMP_DIR / f"audin_{ts}_{in_f}"
        
        # Salvar o arquivo primeiro (fora do semáforo para não bloquear)
        with open(in_p, "wb") as b:
            await up_file.seek(0)
            shutil.copyfileobj(up_file.file, b)
        
        try:
            # Adquirir o semáforo antes de iniciar a transcrição
            # Isso limita o número de transcrições simultâneas
            async with audio_transcription_semaphore:
                log.info(f"Iniciando transcrição do arquivo: {in_f}")
                # Transcrever o áudio usando o modelo Whisper
                ok, msg, raw_txt = transcribe_audio_file(str(in_p), model=whisper_model)
                
                # Tentar refinar a transcrição com o corretor de texto
                corr_txt = None
                corr_msg = P()
                if ok and text_corrector and text_corrector.is_configured():
                    corr_txt = text_corrector.correct_transcription(raw_txt)
                    if corr_txt is None:
                        corr_msg = P("⚠️ Falha ao refinar a transcrição.", style="font-style:italic; color:orange;")
                else:
                    corr_msg = P("ℹ️ Refinamento com IA não disponível.", style="font-style:italic;")
            
            # Este código executa após liberação do semáforo
            if not ok:
                return Div(f"❌ Falha na transcrição: {msg}", cls="error-message")
            
            # Montar o resultado
            res = [
                H3("Transcrição Original:"), 
                Textarea(raw_txt or " ", readonly=True, rows=8, style="margin-bottom:1rem;")
            ]
            
            # Adicionar a versão refinada se disponível
            if corr_txt is not None:
                res.extend([
                    H3("Transcrição Refinada:"), 
                    Textarea(corr_txt, readonly=True, rows=8)
                ])
            
            res.append(corr_msg)
            return Div(*res, cls="success-message")
                
        except Exception as e:
            log.exception(f"Erro durante transcrição de áudio: {e}")
            return Div("❌ Erro interno durante o processamento.", cls="error-message")
        finally:
            # Limpar o arquivo temporário de entrada
            if 'in_p' in locals() and in_p.exists():
                try:
                    in_p.unlink()
                except OSError as e:
                    log.warning(f"Erro ao remover arquivo temporário: {e}")