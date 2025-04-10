from fasthtml.common import *
from starlette.requests import Request
from starlette.background import BackgroundTasks
import logging

from components.layout import page_layout

# Configuração de logging
log = logging.getLogger(__name__)

# Referência para a instância do TextCorrector
# Será definida ao registrar as rotas
text_corrector = None

def register_routes(app):
    """Registra todas as rotas relacionadas ao corretor de texto"""
    # global text_corrector

    @app.route("/text-corrector", methods=["GET"])
    def text_corrector_form(request: Request):
        """Página do corretor de texto"""
        
        # Estilo para o loader
        loader_style = Style("""
            #text-loading {
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
            
            .text-area-label {
                font-weight: bold;
                margin-bottom: 0.5rem;
                display: block;
            }
            
            textarea {
                width: 100%;
                min-height: 200px;
                padding: 0.75rem;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 1rem;
                resize: vertical;
            }
        """)
        
        # JavaScript para gerenciar o loader
        loader_script = Script("""
        document.addEventListener('DOMContentLoaded', function() {
            const form = document.getElementById('text-form');
            const loadingIndicator = document.getElementById('text-loading');
            const resultArea = document.getElementById('result-area');
            
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
            
            // Eventos HTMX para mostrar/esconder o loader
            document.body.addEventListener('htmx:beforeRequest', function(event) {
                if (event.detail.target && event.detail.target.id === 'result-area') {
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'block';
                    }
                }
            });
            
            document.body.addEventListener('htmx:afterRequest', function(event) {
                if (event.detail.target && event.detail.target.id === 'result-area') {
                    if (loadingIndicator) {
                        loadingIndicator.style.display = 'none';
                    }
                }
            });
        });
        """)
        
        # Mensagem de aviso se a API não estiver configurada
        api_warning = Div()
        text_corrector = request.app.state.text_corrector
        if not text_corrector or not text_corrector.is_configured():
            api_warning = Div("⚠️ API de correção não configurada. Funcionalidade limitada.", 
                         cls="error-message", 
                         style="margin-bottom: 1rem;")

        # Formulário de entrada de texto
        form_content = Form(
            P("📄 Cole o texto a ser corrigido:", cls="text-area-label"),
            Textarea(id="text_input", name="text_input", rows=10, required=True),
            Button("Corrigir Texto", type="submit"),
            Div(id="result-area", cls="result-area"),
            hx_post="/text-corrector", 
            hx_target="#result-area", 
            hx_swap="innerHTML",
            id="text-form"
        )
        
        return page_layout(
            "Corretor de Texto - 7ºBPM/P-6",
            Main(
                A("← Voltar", href="/", cls="back-button",
                  style="background-color: #2196F3 !important; color: white !important; border: none !important;"), 
                H1("📝 Corretor de Texto"),
                P("Utilize inteligência artificial para corrigir gramática e ortografia em português."), 
                api_warning,
                loader_style,
                loader_script,
                form_content, 
                # Loader melhorado
                Div(
                    Div(cls="loader-spinner"), 
                    "Corrigindo o texto... Por favor, aguarde.",
                    id="text-loading"
                ),
                cls="container"
            )
        )

    @app.route("/text-corrector", methods=["POST"])
    async def text_corrector_process(request: Request, background_tasks: BackgroundTasks = None):
        # Acesse o text_corrector e as funções de task management diretamente do estado da aplicação
        text_corrector = request.app.state.text_corrector
        start_task = None

        # Obter a função de criação de tarefas do estado da aplicação
        if hasattr(request.app.state, "start_background_task"):
            start_task = request.app.state.start_background_task
        elif hasattr(request.app.state, "submit_task"):
            start_task = request.app.state.submit_task

        # Validar se o corretor está disponível
        if not text_corrector or not text_corrector.is_configured():
            return Div("❌ API de correção não configurada.", cls="error-message")

        # Obter o texto do formulário
        form_data = await request.form()
        text_input = form_data.get("text_input", "")

        if not text_input or not text_input.strip():
            return Div("⚠️ Insira algum texto para corrigir.", cls="error-message")

        try:
            # Se for um texto curto, processa diretamente
            if len(text_input) < 500:  # Limite arbitrário para processamento direto
                log.info("Recebido pedido de correção (texto curto)...")
                corrected_text = text_corrector.correct_text(text_input)
                if corrected_text is not None:
                    log.info("Correção bem-sucedida.")
                    return Div(
                        H3("📝 Texto Corrigido:"), 
                        Textarea(corrected_text, readonly=True, rows=10, id="corrected-text-output"), 
                        cls="success-message"
                    )
                else:
                    log.error("Falha na API de correção.")
                    return Div("❌ Falha ao corrigir. API indisponível ou erro.", cls="error-message")
            else:
                # Para textos longos, usar processamento assíncrono
                log.info("Recebido pedido de correção (texto longo, processando assíncronamente)...")

                if not start_task:
                    # Tenta importar diretamente se não estiver no app.state
                    try:
                        from utils.task_manager import start_background_task as fallback_start_task
                        start_task = fallback_start_task
                    except ImportError:
                        log.error("Função de processamento assíncrono não encontrada.")
                        # Fallback: tenta processar diretamente
                        corrected_text = text_corrector.correct_text(text_input)
                        if corrected_text:
                            return Div(
                                H3("📝 Texto Corrigido:"), 
                                Textarea(corrected_text, readonly=True, rows=10), 
                                cls="success-message"
                            )
                        else:
                            return Div("❌ Falha ao corrigir texto.", cls="error-message")

                # Iniciar o processamento em background
                task_id = start_task(background_tasks, text_corrector.correct_text, text_input)

                # Script para polling do resultado
                polling_script = """
                <script>
                document.addEventListener('DOMContentLoaded', function() {
                    let taskId = '%s';
                    let checkInterval = setInterval(function() {
                        fetch('/task-status/' + taskId)
                            .then(response => response.json())
                            .then(data => {
                                if (data.status === 'completed') {
                                    clearInterval(checkInterval);
                                    // Buscar o resultado
                                    fetch('/text-result/' + taskId)
                                        .then(response => response.text())
                                        .then(text => {
                                            document.getElementById('processing-message').innerHTML = 
                                                '<div class="success-message">' +
                                                '<h3>📝 Texto Corrigido:</h3>' +
                                                '<textarea readonly rows="10" id="corrected-text-output">' + text + '</textarea>' +
                                                '</div>';
                                        });
                                } else if (data.status === 'failed') {
                                    clearInterval(checkInterval);
                                    document.getElementById('processing-message').innerHTML = 
                                        '<div class="error-message">' +
                                        '<p>❌ Falha ao corrigir texto: ' + (data.error || 'Erro desconhecido') + '</p>' +
                                        '</div>';
                                }
                            })
                            .catch(error => {
                                console.error('Erro ao verificar status:', error);
                            });
                    }, 1000); // Verificar a cada 1 segundo
                });
                </script>
                """ % task_id

                return Div(
                    Div("Corrigindo texto... Por favor, aguarde.", id="processing-message", cls="loading-indicator", style="display:block"),
                    Script(polling_script, type="text/javascript"),
                    id="text-correction-container"
                )

        except Exception as e:
            log.error(f"Erro inesperado na correção: {e}", exc_info=True)
            return Div(f"❌ Erro interno: {str(e)}", cls="error-message")
        

    @app.route("/text-result/{task_id}", methods=["GET"])
    async def get_text_result(task_id: str):
        """Retorna o resultado do texto corrigido para uma tarefa específica"""
        
        # Obter a função de verificação de status do estado da aplicação
        if hasattr(app.state, "get_task_status"):
            get_status = app.state.get_task_status
        else:
            # Tenta importar diretamente
            try:
                from utils.task_manager import get_task_status as get_status
            except ImportError:
                log.error("Função get_task_status não encontrada")
                return HTMLResponse("Função de status não disponível", status_code=500)
        
        status = get_status(task_id)
        
        if not status or status.get("status") != "completed":
            return HTMLResponse("Tarefa não encontrada ou não concluída", status_code=404)
        
        result = status.get("result")
        if not result:
            return HTMLResponse("", status_code=200)  # Retorna texto vazio se não houver resultado
        
        return HTMLResponse(result, status_code=200)