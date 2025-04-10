import asyncio
from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import JSONResponse
import logging

from components.layout import page_layout

# Configuração de logging
log = logging.getLogger(__name__)

# Referências para funções importadas do módulo rdpm_agent
# Serão definidas ao registrar as rotas
query_rdpm = None
rdpm_agent_initialized = False

# Semáforo para limitar consultas RDPM simultâneas
rdpm_query_semaphore = asyncio.Semaphore(4) 

def register_routes(app):
    """Registra todas as rotas relacionadas à consulta do RDPM"""
    
    @app.route("/rdpm-query", methods=["GET"])
    def rdpm_query_page(request: Request):
        """Página de consulta ao RDPM"""
        
        # Estilo CSS para o chat incluindo os estilos para o contexto
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
        rdpm_initialized = getattr(request.app.state, "rdpm_agent_initialized", False)
        status = Div("⚠️ Agente RDPM não inicializado. As consultas não funcionarão corretamente.", 
                  cls="error-message") if not rdpm_initialized else Div()
        
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
                A("← Voltar", href="/", cls="back-button", 
                  style="background-color: #2196F3 !important; color: white !important; border: none !important;"),
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
    async def rdpm_query_ask(request: Request):
        form = await request.form()
        question = form.get("question", "")
        
        # Verificar se o agente está inicializado
        rdpm_agent_initialized = getattr(request.app.state, 'rdpm_agent_initialized', False)
        query_rdpm = getattr(request.app.state, 'query_rdpm', None)
        
        if not rdpm_agent_initialized or not query_rdpm:
            return JSONResponse({
                "success": False, 
                "error": "Agente RDPM não inicializado"
            })
        
        if not question or not question.strip():
            return JSONResponse({"success": False, "error": "Pergunta vazia"})
        
        log.info(f"RDPM Query: {question[:50]}...")
        
        # Usar o semáforo para limitar consultas simultâneas
        async with rdpm_query_semaphore:
            try:
                # Esta chamada pode ser bloqueante, por isso colocamos dentro do semáforo
                resp_dict = query_rdpm(question)
            except Exception as e:
                log.error(f"Erro ao executar query_rdpm: {e}")
                return JSONResponse({
                    "success": False,
                    "error": f"Erro ao processar consulta: {str(e)}"
                })
        
        # Retornar JSON com a resposta e contexto
        if resp_dict:
            answer = resp_dict.get("answer", "Não consegui processar sua pergunta.")
            
            # Extrair e formatar o contexto
            context_sources = []
            if "context" in resp_dict and resp_dict["context"]:
                for doc in resp_dict["context"]:
                    # Extrair número da página
                    page_num = doc.metadata.get('page', 'N/A')
                    page_display = page_num + 1 if isinstance(page_num, int) else 'N/A'
                    
                    # Extrair conteúdo limitado
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
