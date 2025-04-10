from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse
from datetime import datetime, date, timedelta
import json
import logging

from components.layout import page_layout

# Configuração de logging
log = logging.getLogger(__name__)

# Dicionário de prazos por natureza (em anos)
NATUREZA_PRAZOS = {
    "Leve": 1,
    "Média": 2,
    "Grave": 5
}

def register_routes(app):
    """Registra todas as rotas relacionadas à calculadora de prescrição"""
    
    @app.route("/prescription-calculator", methods=["GET"])
    async def prescription_calculator_page(request: Request):
        """Página da calculadora de prescrição disciplinar"""
        
        # Estilos para a calculadora com ajustes nos estilos do tooltip
        calc_style = Style("""
            .calculator-container {
                background-color: white;
                border-radius: 8px;
                padding: 1.5rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                margin-bottom: 2rem;
            }
            
            .form-group {
                margin-bottom: 1.2rem;
            }
            
            .form-label {
                display: block;
                margin-bottom: 0.5rem;
                font-weight: 500;
                color: #333;
            }
            
            .form-select, .form-input, .form-checkbox {
                width: 100%;
                padding: 0.7rem;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 1rem;
                box-sizing: border-box;
            }
            
            .form-checkbox-label {
                display: flex;
                align-items: center;
                cursor: pointer;
                user-select: none;
                margin-top: 1rem;
                margin-bottom: 0.5rem;
                font-weight: 500;
            }
            
            .form-checkbox-input {
                margin-right: 0.5rem;
                width: 18px;
                height: 18px;
                cursor: pointer;
            }
            
            .form-button {
                width: 100%;
                padding: 0.8rem;
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 1.1rem;
                cursor: pointer;
                margin-top: 1.5rem;
                transition: background-color 0.2s;
            }
            
            .form-button:hover {
                background-color: #218838;
                box-shadow: 0 3px 5px rgba(0,0,0,0.1);
            }
            
            .suspension-section {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 1rem 1.5rem;
                margin-top: 1rem;
                background-color: #f8f9fa;
                display: none; /* Inicialmente oculto */
            }
            
            .suspension-title {
                margin-top: 0;
                margin-bottom: 1rem;
                font-size: 1.1rem;
                color: #495057;
                border-bottom: 1px solid #dee2e6;
                padding-bottom: 0.5rem;
            }
            
            .suspension-dates {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 1rem;
                margin-bottom: 1rem;
            }
            
            .suspension-actions {
                display: flex;
                gap: 0.5rem;
            }
            
            .button-add {
                background-color: #007bff;
                color: white;
                flex: 1;
            }
            
            .button-remove {
                background-color: #dc3545;
                color: white;
                flex: 1;
                display: none; /* Inicialmente oculto */
            }
            
            .suspension-list {
                margin-top: 1rem;
                max-height: 200px;
                overflow-y: auto;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 0.5rem;
                background-color: white;
            }
            
            .suspension-item {
                padding: 0.5rem;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
            }
            
            .suspension-item:last-child {
                border-bottom: none;
            }
            
            .suspension-dates-text {
                font-weight: 500;
            }
            
            .result-container {
                margin-top: 2rem;
                padding: 1.5rem;
                border-radius: 8px;
                text-align: center;
                font-size: 1.1rem;
                font-weight: 500;
                line-height: 1.6;
            }
            
            .result-success {
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
                color: #155724;
            }
            
            .result-error {
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                color: #721c24;
            }
            
            .back-button {
                background-color: #2196F3 !important;
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
            
            /* Tooltip melhorado */
            .label-with-tooltip {
                display: flex;
                align-items: center;
            }
            
            .tooltip-container {
                position: relative;
                display: inline-block;
                margin-left: 8px;
            }
            
            .tooltip-icon {
                display: inline-flex;
                justify-content: center;
                align-items: center;
                width: 20px;
                height: 20px;
                margin-bottom: 2px;        
                border-radius: 50%;
                background-color: #6c757d;
                color: white;
                font-size: 12px;
                font-weight: bold;
                cursor: help;
            }
            
            .tooltip-text {
                visibility: hidden;
                width: 300px;
                background-color: #333;
                color: #fff;
                text-align: justify;
                border-radius: 6px;
                padding: 10px;
                position: absolute;
                z-index: 100;
                bottom: 125%;
                left: 50%;
                margin-left: -150px;
                opacity: 0;
                transition: opacity 0.3s;
                font-size: 0.9rem;
                font-weight: normal;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            }
            
            .tooltip-text::after {
                content: "";
                position: absolute;
                top: 100%;
                left: 50%;
                margin-left: -5px;
                border-width: 5px;
                border-style: solid;
                border-color: #333 transparent transparent transparent;
            }
            
            .tooltip-container:hover .tooltip-text {
                visibility: visible;
                opacity: 1;
            }
            
            /* Mensagens de validação */
            .validation-error {
                color: #dc3545;
                font-size: 0.85rem;
                margin-top: 5px;
                display: none;
            }
        """)
        
        # JavaScript para interatividade com alertas corrigidos
        calc_script = Script("""
        document.addEventListener('DOMContentLoaded', function() {
            // Variáveis globais para armazenar as suspensões
            let suspensionsList = [];
            const suspList = document.getElementById('suspensions-list');
            const suspStartInput = document.getElementById('susp-start');
            const suspEndInput = document.getElementById('susp-end');
            const addSuspButton = document.getElementById('add-suspension');
            const removeSuspButton = document.getElementById('remove-suspension');
            const suspSection = document.getElementById('suspension-section');
            const suspCheckbox = document.getElementById('has-suspension');
            const calculatorForm = document.getElementById('calculator-form');
            
            const natureSelect = document.getElementById('natureza');
            const knowledgeDate = document.getElementById('conhecimento-date');
            const instDate = document.getElementById('instauracao-date');
            
            // Mostrar mensagens de erro de validação
            function showValidationError(element, message) {
                const errorElement = document.querySelector(`#${element.id}-error`);
                if (errorElement) {
                    errorElement.textContent = message;
                    errorElement.style.display = 'block';
                }
            }
            
            // Esconder mensagens de erro de validação
            function hideValidationError(element) {
                const errorElement = document.querySelector(`#${element.id}-error`);
                if (errorElement) {
                    errorElement.style.display = 'none';
                }
            }
            
            // Formatar data para exibição
            function formatDate(dateStr) {
                const date = new Date(dateStr);
                return date.toLocaleDateString('pt-BR');
            }
            
            // Adicionar suspensão à lista
            function addSuspension() {
                const startDate = suspStartInput.value;
                const endDate = suspEndInput.value;
                
                if (!startDate || !endDate) {
                    showValidationError(suspStartInput, 'Por favor, preencha as datas de início e fim da suspensão.');
                    return;
                }
                
                if (new Date(endDate) < new Date(startDate)) {
                    showValidationError(suspEndInput, 'A data de fim da suspensão deve ser igual ou posterior à data de início.');
                    return;
                }
                
                // Verificar relação com a data de instauração
                const instDate = document.getElementById('instauracao-date').value;
                if (instDate && new Date(startDate) < new Date(instDate)) {
                    showValidationError(suspStartInput, 'A suspensão não pode começar antes da Data de Instauração.');
                    return;
                }
                
                // Adicionar à lista
                suspensionsList.push({start: startDate, end: endDate});
                updateSuspensionsList();
                
                // Limpar campos e erros
                suspStartInput.value = '';
                suspEndInput.value = '';
                hideValidationError(suspStartInput);
                hideValidationError(suspEndInput);
            }
            
            // Remover última suspensão
            function removeLastSuspension() {
                if (suspensionsList.length > 0) {
                    suspensionsList.pop();
                    updateSuspensionsList();
                } else {
                    showValidationError(document.getElementById('suspensions-list'), 'Não há períodos de suspensão para remover.');
                }
            }
            
            // Atualizar a lista visual de suspensões
            function updateSuspensionsList() {
                suspList.innerHTML = '';
                
                suspensionsList.forEach(susp => {
                    const suspItem = document.createElement('div');
                    suspItem.className = 'suspension-item';
                    suspItem.innerHTML = `
                        <span class="suspension-dates-text">
                            ${formatDate(susp.start)} até ${formatDate(susp.end)}
                        </span>
                    `;
                    suspList.appendChild(suspItem);
                });
                
                // Atualizar o campo oculto com os dados de suspensão
                document.getElementById('suspensions-data').value = JSON.stringify(suspensionsList);
                
                // Atualizar visibilidade do botão remover
                removeSuspButton.style.display = suspensionsList.length > 0 ? 'block' : 'none';
            }
            
            // Mostrar/ocultar seção de suspensão
            function toggleSuspensionSection() {
                if (suspCheckbox.checked) {
                    suspSection.style.display = 'block';
                } else {
                    suspSection.style.display = 'none';
                    // Limpar suspensões se a seção for ocultada
                    suspensionsList = [];
                    updateSuspensionsList();
                }
            }
            
            // Validação de campos
            function validateField(field, errorMessage) {
                if (!field.value) {
                    showValidationError(field, errorMessage);
                    field.focus();
                    return false;
                }
                hideValidationError(field);
                return true;
            }
            
            // Validar relação entre datas
            function validateDateRelation() {
                if (knowledgeDate.value && instDate.value) {
                    if (new Date(instDate.value) < new Date(knowledgeDate.value)) {
                        showValidationError(instDate, 'A Data de Instauração não pode ser anterior à Data de Conhecimento do fato.');
                        instDate.focus();
                        return false;
                    }
                }
                hideValidationError(instDate);
                return true;
            }
            
            // Inicializar o toggle da seção de suspensão
            if (suspCheckbox) {
                suspCheckbox.addEventListener('change', toggleSuspensionSection);
                toggleSuspensionSection(); // Configuração inicial
            }
            
            // Adicionar listeners de eventos
            if (addSuspButton) {
                addSuspButton.addEventListener('click', function(e) {
                    e.preventDefault();
                    addSuspension();
                });
            }
            
            if (removeSuspButton) {
                removeSuspButton.addEventListener('click', function(e) {
                    e.preventDefault();
                    removeLastSuspension();
                });
            }
            
            // Adicionar validação de foco para cada campo
            natureSelect.addEventListener('blur', function() {
                validateField(natureSelect, 'Por favor, selecione a Natureza da Infração.');
            });
            
            knowledgeDate.addEventListener('blur', function() {
                validateField(knowledgeDate, 'Por favor, informe a Data de Conhecimento do Fato.');
                validateDateRelation();
            });
            
            instDate.addEventListener('blur', function() {
                validateField(instDate, 'Por favor, informe a Data de Instauração.');
                validateDateRelation();
            });
            
            // Validações antes do envio do formulário
            if (calculatorForm) {
                calculatorForm.addEventListener('submit', function(e) {
                    e.preventDefault(); // Previne a submissão para validar primeiro
                    
                    let isValid = true;
                    
                    // Validar campos obrigatórios
                    isValid = validateField(natureSelect, 'Por favor, selecione a Natureza da Infração.') && isValid;
                    isValid = validateField(knowledgeDate, 'Por favor, informe a Data de Conhecimento do Fato.') && isValid;
                    isValid = validateField(instDate, 'Por favor, informe a Data de Instauração.') && isValid;
                    
                    // Validar relação entre datas
                    isValid = validateDateRelation() && isValid;
                    
                    if (isValid) {
                        // Se passou na validação, enviar o formulário
                        this.submit();
                    }
                });
            }
            
            // Se houver um resultado na página, role para ele
            const resultArea = document.getElementById('result-area');
            if (resultArea && resultArea.innerHTML.trim() !== '') {
                setTimeout(() => resultArea.scrollIntoView({ behavior: 'smooth' }), 500);
            }
        });
        """)
        
        # Verificar se há um resultado na sessão
        result_content = Div(id="result-area")
        
        if "prescription_result" in request.session:
            result_html = request.session.pop("prescription_result")  # Remove após usar
            # Escapar as aspas no HTML para evitar problemas no JavaScript
            result_html_escaped = result_html.replace('`', '\\`').replace("'", "\\'").replace('"', '\\"')
            
            # Criar o script como uma string separada
            script_content = f"""
            document.addEventListener('DOMContentLoaded', function() {{
                document.getElementById('result-placeholder').outerHTML = `{result_html_escaped}`;
            }});
            """
            
            # Adicionar o conteúdo do resultado como divs separados
            result_content = Div(
                Div(id="result-placeholder"),  # Placeholder
                Script(script_content),        # Script para substituir o placeholder
                id="result-area"
            )
        
        # Verificar erros
        error = request.query_params.get("error")
        if error:
            error_message = "Erro ao processar o formulário."
            if error == "missing_fields":
                error_message = "Por favor, preencha todos os campos obrigatórios."
            elif error == "invalid_date":
                error_message = "Uma ou mais datas informadas são inválidas."
            elif error == "invalid_nature":
                error_message = "A natureza da infração selecionada é inválida."
            elif error == "date_relation":
                error_message = "A Data de Instauração não pode ser anterior à Data de Conhecimento."
            
            result_content = Div(
                Div(error_message, cls="result-container result-error"),
                id="result-area"
            )
        
        # Formulário da calculadora
        calculator_form = Form(
            # Natureza da Infração
            Div(
                Label("Natureza da Infração:", fr="natureza", cls="form-label"),
                Select(
                    Option("Selecione a natureza...", value="", selected=True),
                    Option("Leve", value="Leve"),
                    Option("Média", value="Média"),
                    Option("Grave", value="Grave"),
                    id="natureza", name="natureza", cls="form-select"
                ),
                Div("Por favor, selecione a natureza da infração.", id="natureza-error", cls="validation-error"),
                cls="form-group"
            ),
            
            # Data de Conhecimento
            Div(
                Label("Data de Conhecimento do Fato:", fr="conhecimento-date", cls="form-label"),
                Input(
                    type="date", id="conhecimento-date", name="conhecimento_date", 
                    cls="form-input", required=True
                ),
                Div("Por favor, informe a Data de Conhecimento do Fato.", id="conhecimento-date-error", cls="validation-error"),
                cls="form-group"
            ),
            
            # Data de Instauração com Tooltip
            Div(
                Div(
                    Label(
                        "Data de Instauração (Sindicância/Processo Disciplinar):",
                        fr="instauracao-date", 
                        cls="form-label"
                    ),
                    Div(
                        Div("?", cls="tooltip-icon"),
                        Div(
                            "Data de abertura da Sindicância Regular ou instauração do Processo Disciplinar. Interrompe e reinicia a contagem.",
                            cls="tooltip-text"
                        ),
                        cls="tooltip-container"
                    ),
                    cls="label-with-tooltip"
                ),
                Input(
                    type="date", id="instauracao-date", name="instauracao_date", 
                    cls="form-input", required=True
                ),
                Div("Por favor, informe a Data de Instauração.", id="instauracao-date-error", cls="validation-error"),
                cls="form-group"
            ),
            
            # Checkbox para suspensão
            Div(
                Label(
                    Input(
                        type="checkbox", id="has-suspension", name="has_suspension", 
                        value="true", cls="form-checkbox-input"
                    ),
                    "Houve suspensão do prazo durante o processo?",
                    cls="form-checkbox-label"
                ),
                cls="form-group"
            ),
            
            # Seção de Suspensões
            Div(
                H3("🗓️ Registrar Períodos de Suspensão", cls="suspension-title"),
                
                # Datas de suspensão
                Div(
                    Div(
                        Label("Data de Início:", fr="susp-start", cls="form-label"),
                        Input(type="date", id="susp-start", name="susp_start", cls="form-input"),
                        Div("", id="susp-start-error", cls="validation-error"),
                        cls="form-group"
                    ),
                    Div(
                        Label("Data de Fim:", fr="susp-end", cls="form-label"),
                        Input(type="date", id="susp-end", name="susp_end", cls="form-input"),
                        Div("", id="susp-end-error", cls="validation-error"),
                        cls="form-group"
                    ),
                    cls="suspension-dates"
                ),
                
                # Botões de ação
                Div(
                    Button("➕ Adicionar Período", id="add-suspension", cls="form-button button-add"),
                    Button("➖ Remover Último Período", id="remove-suspension", cls="form-button button-remove"),
                    cls="suspension-actions"
                ),
                
                # Lista de suspensões
                P("Períodos de Suspensão Registrados:", style="margin-top: 1rem; font-weight: 500;"),
                Div(id="suspensions-list", cls="suspension-list"),
                Div("", id="suspensions-list-error", cls="validation-error"),
                
                # Campo oculto para armazenar os dados de suspensão
                Input(type="hidden", id="suspensions-data", name="suspensions_data", value="[]"),
                
                id="suspension-section",
                cls="suspension-section"
            ),
            
            # Botão de cálculo
            Button("Calcular Prazo Prescricional", type="submit", cls="form-button"),
            
            # Configuração do formulário
            id="calculator-form",
            action="/prescription-calculator", 
            method="post",
            cls="calculator-container"
        )
        
        return page_layout(
            "Calculadora de Prescrição",
            Main(
                A("← Voltar", href="/", cls="back-button", style="background-color: #2196F3 !important; color: white !important; border: none !important;"),
                H1("⏳ Calculadora de Prescrição Disciplinar"),
                P("Calcule a data limite para a prescrição de infrações disciplinares conforme as regras do RDPM."),
                calc_style,
                calculator_form,
                result_content,  # Mostra o resultado (se houver)
                calc_script,
                cls="container"
            )
        )

    @app.route("/prescription-calculator", methods=["POST"])
    async def prescription_calculator_process(request: Request):
        """Processa o cálculo de prescrição disciplinar"""
        
        # Analisar o formulário
        form_data = await request.form()
        
        # Validar campos obrigatórios
        natureza = form_data.get("natureza")
        conhecimento_date_str = form_data.get("conhecimento_date")
        instauracao_date_str = form_data.get("instauracao_date")
        has_suspension = form_data.get("has_suspension") == "true"
        suspensions_data_str = form_data.get("suspensions_data", "[]") if has_suspension else "[]"
        
        if not natureza or not conhecimento_date_str or not instauracao_date_str:
            # Redirecionar com erro se faltarem campos
            return RedirectResponse(url="/prescription-calculator?error=missing_fields", status_code=303)
        
        # Converter datas para objetos date
        try:
            conhecimento_date = datetime.fromisoformat(conhecimento_date_str).date()
            instauracao_date = datetime.fromisoformat(instauracao_date_str).date()
        except ValueError:
            return RedirectResponse(url="/prescription-calculator?error=invalid_date", status_code=303)
        
        # Verificar se a natureza é válida
        if natureza not in NATUREZA_PRAZOS:
            return RedirectResponse(url="/prescription-calculator?error=invalid_nature", status_code=303)
        
        # Verificar relação entre datas
        if instauracao_date < conhecimento_date:
            return RedirectResponse(url="/prescription-calculator?error=date_relation", status_code=303)
        
        # Obter o prazo em anos para a natureza selecionada
        prazo_anos = NATUREZA_PRAZOS[natureza]
        
        # Calcular data de prescrição sem interrupção
        prescricao_sem_interrupcao = conhecimento_date.replace(year=conhecimento_date.year + prazo_anos)
        
        # Log para debug
        log.info(f"Calculando prescrição: Natureza {natureza}, Prazo {prazo_anos} anos")
        log.info(f"Conhecimento: {conhecimento_date}, Instauração: {instauracao_date}")
        log.info(f"Prescrição sem interrupção: {prescricao_sem_interrupcao}")
        
        # Verificar se já prescreveu antes da instauração
        if instauracao_date >= prescricao_sem_interrupcao:
            # Prescrição já ocorreu antes da instauração
            result_html = f"""
            <div class="result-container result-error">
                ⚠️ <strong>PRESCRIÇÃO OCORRIDA (ANTES DA INSTAURAÇÃO)!</strong><br>
                O prazo inicial ({natureza}) era de {prazo_anos} ano(s) a partir de {conhecimento_date.strftime('%d/%m/%Y')}.<br>
                A prescrição teria ocorrido em <strong>{prescricao_sem_interrupcao.strftime('%d/%m/%Y')}</strong>.<br>
                A instauração em {instauracao_date.strftime('%d/%m/%Y')} foi posterior a essa data.
            </div>
            """
        else:
            # Calcular o prazo a partir da instauração
            prescricao_base_interrompida = instauracao_date.replace(year=instauracao_date.year + prazo_anos)
            
            # Processar suspensões
            total_dias_suspensao = 0
            try:
                suspensions_list = json.loads(suspensions_data_str)
                for susp in suspensions_list:
                    inicio = datetime.fromisoformat(susp["start"]).date()
                    fim = datetime.fromisoformat(susp["end"]).date()
                    duracao = (fim - inicio).days + 1  # Inclui o dia final
                    if duracao >= 0:
                        total_dias_suspensao += duracao
                        log.info(f"Suspensão: {inicio} a {fim} = {duracao} dias")
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                log.error(f"Erro ao processar suspensões: {e}")
                total_dias_suspensao = 0
            
            log.info(f"Total dias suspensão: {total_dias_suspensao}")
            
            # Adicionar dias de suspensão
            data_final_prescricao = prescricao_base_interrompida + timedelta(days=total_dias_suspensao)
            log.info(f"Data final prescrição: {data_final_prescricao}")
            
            # Verificar se já prescreveu
            hoje = date.today()
            info_suspensao = f" ({total_dias_suspensao} dia(s) de suspensão adicionados)" if total_dias_suspensao > 0 else ""
            
            if data_final_prescricao < hoje:
                # PRESCRIÇÃO OCORRIDA
                result_html = f"""
                <div class="result-container result-error">
                    🚨 <strong>PRESCRIÇÃO OCORRIDA!</strong><br>
                    Considerando a natureza <strong>{natureza}</strong> ({prazo_anos} ano(s)),
                    a interrupção em <strong>{instauracao_date.strftime('%d/%m/%Y')}</strong>{info_suspensao},
                    o prazo prescricional finalizou em <strong>{data_final_prescricao.strftime('%d/%m/%Y')}</strong>.
                </div>
                """
            else:
                # DENTRO DO PRAZO
                result_html = f"""
                <div class="result-container result-success">
                    ✅ <strong>DENTRO DO PRAZO PRESCRICIONAL</strong><br>
                    Considerando a natureza <strong>{natureza}</strong> ({prazo_anos} ano(s)),
                    a interrupção em <strong>{instauracao_date.strftime('%d/%m/%Y')}</strong>{info_suspensao},
                    o prazo prescricional se encerrará em <strong>{data_final_prescricao.strftime('%d/%m/%Y')}</strong>.
                </div>
                """
        
        # Armazenar o resultado na sessão
        request.session["prescription_result"] = result_html
        log.info(f"Resultado gerado e armazenado na sessão.")
        
        # Redirecionar para a página de resultados
        return RedirectResponse(url="/prescription-calculator", status_code=303)
