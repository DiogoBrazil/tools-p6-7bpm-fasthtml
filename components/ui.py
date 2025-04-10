# components/ui.py

from fasthtml.common import *

def tool_card(id:str, icon: str, title: str, description: str, items: list[str], link: str, link_text: str):
    """
    Componente de card para ferramentas na página inicial.
    
    Args:
        id (str): ID único para o card
        icon (str): Ícone (emoji ou classe) do card
        title (str): Título do card
        description (str): Descrição do card
        items (list[str]): Lista de itens/funcionalidades
        link (str): Link para a ferramenta
        link_text (str): Texto do botão de link
        
    Returns:
        O componente de card
    """
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

def form_group(label_text: str, input_component, error_text: str = None, id_prefix: str = None, required: bool = False):
    """
    Grupo de formulário padronizado com label, input e mensagem de erro opcional.
    
    Args:
        label_text (str): Texto do label
        input_component: Componente de input (Input, Select, Textarea, etc.)
        error_text (str, optional): Texto de erro inicial (normalmente vazio)
        id_prefix (str, optional): Prefixo para IDs (se não informado, usa o ID do input)
        required (bool, optional): Se True, adiciona asterisco ao label
        
    Returns:
        O componente de grupo de formulário
    """
    # Determinar o ID base para o grupo
    input_id = input_component.get('id', '')
    base_id = id_prefix or input_id
    
    # Adicionar asterisco se campo obrigatório
    if required:
        label_text = f"{label_text} *"
    
    # Criar o componente de label
    label = Label(label_text, fr=input_id, cls="form-label")
    
    # Componentes do grupo
    components = [label, input_component]
    
    # Adicionar mensagem de erro se especificada
    if error_text is not None:
        error_id = f"{base_id}-error" if base_id else "input-error"
        components.append(
            Div(error_text, id=error_id, cls="validation-error", style="display: none;")
        )
    
    return Div(*components, cls="form-group")

def select_field(id: str, options: list, selected_value: str = None, required: bool = False, **kwargs):
    """
    Campo de seleção padronizado.
    
    Args:
        id (str): ID do campo
        options (list): Lista de opções - pode ser lista de strings ou lista de tuplas (valor, texto)
        selected_value (str, optional): Valor selecionado inicialmente
        required (bool, optional): Se True, o campo é obrigatório
        **kwargs: Atributos adicionais para o componente Select
        
    Returns:
        O componente Select
    """
    # Processar as opções
    select_options = []
    for option in options:
        if isinstance(option, tuple) and len(option) == 2:
            value, text = option
            is_selected = selected_value == value
            select_options.append(Option(text, value=value, selected=is_selected))
        else:
            is_selected = selected_value == option
            select_options.append(Option(option, value=option, selected=is_selected))
    
    # Definir atributos padrão
    all_attrs = {
        "id": id,
        "name": kwargs.get("name", id),
        "cls": "form-select",
        "required": required
    }
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    return Select(*select_options, **all_attrs)

def upload_field(id: str, accept: str = None, multiple: bool = False, required: bool = False, **kwargs):
    """
    Campo de upload de arquivo padronizado.
    
    Args:
        id (str): ID do campo
        accept (str, optional): Tipos de arquivo aceitos (ex: ".pdf,.doc")
        multiple (bool, optional): Se True, permite múltiplos arquivos
        required (bool, optional): Se True, o campo é obrigatório
        **kwargs: Atributos adicionais para o componente Input
        
    Returns:
        O componente Input do tipo file
    """
    # Definir atributos padrão
    all_attrs = {
        "id": id,
        "name": kwargs.get("name", id),
        "type": "file",
        "cls": "form-input",
        "required": required
    }
    
    # Adicionar atributos condicionais
    if accept:
        all_attrs["accept"] = accept
    if multiple:
        all_attrs["multiple"] = True
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    return Input(**all_attrs)

def text_field(id: str, placeholder: str = None, value: str = None, required: bool = False, **kwargs):
    """
    Campo de texto padronizado.
    
    Args:
        id (str): ID do campo
        placeholder (str, optional): Texto de placeholder
        value (str, optional): Valor inicial
        required (bool, optional): Se True, o campo é obrigatório
        **kwargs: Atributos adicionais para o componente Input
        
    Returns:
        O componente Input do tipo text
    """
    # Definir atributos padrão
    all_attrs = {
        "id": id,
        "name": kwargs.get("name", id),
        "type": "text",
        "cls": "form-input",
        "required": required
    }
    
    # Adicionar atributos condicionais
    if placeholder:
        all_attrs["placeholder"] = placeholder
    if value is not None:
        all_attrs["value"] = value
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    return Input(**all_attrs)

def date_field(id: str, value: str = None, required: bool = False, **kwargs):
    """
    Campo de data padronizado.
    
    Args:
        id (str): ID do campo
        value (str, optional): Valor inicial (formato ISO: YYYY-MM-DD)
        required (bool, optional): Se True, o campo é obrigatório
        **kwargs: Atributos adicionais para o componente Input
        
    Returns:
        O componente Input do tipo date
    """
    # Definir atributos padrão
    all_attrs = {
        "id": id,
        "name": kwargs.get("name", id),
        "type": "date",
        "cls": "form-input",
        "required": required
    }
    
    # Adicionar valor inicial se fornecido
    if value is not None:
        all_attrs["value"] = value
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    return Input(**all_attrs)

def textarea_field(id: str, placeholder: str = None, value: str = None, rows: int = 5, required: bool = False, **kwargs):
    """
    Campo de texto multilinha padronizado.
    
    Args:
        id (str): ID do campo
        placeholder (str, optional): Texto de placeholder
        value (str, optional): Valor inicial
        rows (int, optional): Número de linhas visíveis
        required (bool, optional): Se True, o campo é obrigatório
        **kwargs: Atributos adicionais para o componente Textarea
        
    Returns:
        O componente Textarea
    """
    # Definir atributos padrão
    all_attrs = {
        "id": id,
        "name": kwargs.get("name", id),
        "rows": rows,
        "cls": "form-textarea",
        "required": required
    }
    
    # Adicionar atributos condicionais
    if placeholder:
        all_attrs["placeholder"] = placeholder
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    # Criar o Textarea com ou sem conteúdo
    if value is not None:
        return Textarea(value, **all_attrs)
    else:
        return Textarea(**all_attrs)

def checkbox_field(id: str, label_text: str, checked: bool = False, value: str = "true", **kwargs):
    """
    Campo de checkbox padronizado com label.
    
    Args:
        id (str): ID do campo
        label_text (str): Texto do label
        checked (bool, optional): Se True, o checkbox inicia marcado
        value (str, optional): Valor do checkbox quando marcado
        **kwargs: Atributos adicionais para o componente Input
        
    Returns:
        O componente de checkbox com label
    """
    # Definir atributos padrão
    all_attrs = {
        "id": id,
        "name": kwargs.get("name", id),
        "type": "checkbox",
        "value": value,
        "cls": "form-checkbox-input"
    }
    
    # Adicionar checked se necessário
    if checked:
        all_attrs["checked"] = True
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    # Criar o checkbox dentro de uma label
    checkbox = Input(**all_attrs)
    
    return Label(
        checkbox,
        label_text,
        cls="form-checkbox-label"
    )

def submit_button(text: str, cls: str = "form-button", **kwargs):
    """
    Botão de envio padronizado.
    
    Args:
        text (str): Texto do botão
        cls (str, optional): Classe CSS
        **kwargs: Atributos adicionais para o componente Button
        
    Returns:
        O componente Button
    """
    # Definir atributos padrão
    all_attrs = {
        "type": "submit",
        "cls": cls
    }
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    return Button(text, **all_attrs)

def action_button(text: str, id: str = None, cls: str = "action-button", **kwargs):
    """
    Botão de ação padronizado (não é do tipo submit).
    
    Args:
        text (str): Texto do botão
        id (str, optional): ID do botão
        cls (str, optional): Classe CSS
        **kwargs: Atributos adicionais para o componente Button
        
    Returns:
        O componente Button
    """
    # Definir atributos padrão
    all_attrs = {
        "type": "button",
        "cls": cls
    }
    
    # Adicionar ID se fornecido
    if id:
        all_attrs["id"] = id
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    return Button(text, **all_attrs)

def tooltip(text: str, icon: str = "?", position: str = "top"):
    """
    Componente de tooltip padronizado.
    
    Args:
        text (str): Texto do tooltip
        icon (str, optional): Ícone ou símbolo para o tooltip
        position (str, optional): Posição do tooltip (top, bottom, left, right)
        
    Returns:
        O componente de tooltip
    """
    return Div(
        Div(icon, cls="tooltip-icon"),
        Div(text, cls=f"tooltip-text tooltip-{position}"),
        cls="tooltip-container"
    )

def label_with_tooltip(label_text: str, tooltip_text: str, for_id: str = None, icon: str = "?", required: bool = False):
    """
    Label com tooltip integrado.
    
    Args:
        label_text (str): Texto do label
        tooltip_text (str): Texto do tooltip
        for_id (str, optional): Valor do atributo 'for' do label
        icon (str, optional): Ícone ou símbolo para o tooltip
        required (bool, optional): Se True, adiciona asterisco ao label
        
    Returns:
        O componente de label com tooltip
    """
    # Adicionar asterisco se campo obrigatório
    if required:
        label_text = f"{label_text} *"
    
    # Atributos do label
    label_attrs = {"cls": "form-label"}
    if for_id:
        label_attrs["fr"] = for_id
    
    return Div(
        Label(label_text, **label_attrs),
        tooltip(tooltip_text, icon),
        cls="label-with-tooltip"
    )

def badge(text: str, type: str = "default", size: str = "default"):
    """
    Badge padronizado.
    
    Args:
        text (str): Texto do badge
        type (str, optional): Tipo do badge (default, success, warning, error, info)
        size (str, optional): Tamanho do badge (default, small, large)
        
    Returns:
        O componente de badge
    """
    classes = ["badge", f"badge-{type}"]
    
    if size != "default":
        classes.append(f"badge-{size}")
    
    return Span(text, cls=" ".join(classes))

def alert(message: str, type: str = "info", dismissible: bool = False):
    """
    Alerta padronizado.
    
    Args:
        message (str): Mensagem do alerta
        type (str, optional): Tipo do alerta (info, success, warning, error)
        dismissible (bool, optional): Se True, adiciona botão para fechar o alerta
        
    Returns:
        O componente de alerta
    """
    components = [P(message)]
    
    # Adicionar botão de fechar se dismissible
    if dismissible:
        close_button = Button(
            "×", 
            cls="alert-close", 
            type="button",
            aria_label="Close",
            onclick="this.parentElement.style.display='none';"
        )
        components.append(close_button)
    
    return Div(*components, cls=f"alert alert-{type}")

def card(title: str = None, content: list = None, footer: list = None, **kwargs):
    """
    Card padronizado.
    
    Args:
        title (str, optional): Título do card
        content (list, optional): Conteúdo do card
        footer (list, optional): Rodapé do card
        **kwargs: Atributos adicionais para o componente Card
        
    Returns:
        O componente Card
    """
    components = []
    
    # Adicionar header se título for fornecido
    if title:
        components.append(Header(H3(title), cls="card-header"))
    
    # Adicionar conteúdo
    if content:
        components.append(Div(*content, cls="card-content"))
    
    # Adicionar footer
    if footer:
        components.append(Footer(*footer, cls="card-footer"))
    
    # Definir atributos padrão
    all_attrs = {"cls": "card"}
    
    # Adicionar atributos extras
    all_attrs.update(kwargs)
    
    # Criar o card como um Article
    return Article(*components, **all_attrs)

def pagination(current_page: int, total_pages: int, base_url: str, page_param: str = "page"):
    """
    Componente de paginação.
    
    Args:
        current_page (int): Página atual
        total_pages (int): Total de páginas
        base_url (str): URL base para links
        page_param (str, optional): Nome do parâmetro de página
        
    Returns:
        O componente de paginação
    """
    if total_pages <= 1:
        return Div()  # Retorna div vazio se não houver paginação
    
    # Função auxiliar para criar URL de página
    def page_url(page):
        # Adiciona ? ou & conforme necessário
        separator = "?" if "?" not in base_url else "&"
        return f"{base_url}{separator}{page_param}={page}"
    
    items = []
    
    # Adicionar link para primeira página
    if current_page > 1:
        items.append(A("Primeira", href=page_url(1), cls="pagination-link"))
    else:
        items.append(Span("Primeira", cls="pagination-link disabled"))
    
    # Adicionar link para página anterior
    if current_page > 1:
        items.append(A("Anterior", href=page_url(current_page - 1), cls="pagination-link"))
    else:
        items.append(Span("Anterior", cls="pagination-link disabled"))
    
    # Adicionar páginas numeradas (max 5)
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, start_page + 4)
    
    for page in range(start_page, end_page + 1):
        if page == current_page:
            items.append(Span(str(page), cls="pagination-link current"))
        else:
            items.append(A(str(page), href=page_url(page), cls="pagination-link"))
    
    # Adicionar link para próxima página
    if current_page < total_pages:
        items.append(A("Próxima", href=page_url(current_page + 1), cls="pagination-link"))
    else:
        items.append(Span("Próxima", cls="pagination-link disabled"))
    
    # Adicionar link para última página
    if current_page < total_pages:
        items.append(A("Última", href=page_url(total_pages), cls="pagination-link"))
    else:
        items.append(Span("Última", cls="pagination-link disabled"))
    
    return Nav(*items, cls="pagination")