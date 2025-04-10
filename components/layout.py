# components/layout.py

from fasthtml.common import *

def page_layout(title: str, *body_content):
    """
    Layout padrão da página para todas as rotas.
    
    Args:
        title (str): Título da página
        *body_content: Conteúdo do corpo da página (cabeçalho, main, etc.)
        
    Returns:
        O HTML completo da página
    """
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

def loading_indicator(id: str, message: str, additional_message: str = None, hidden: bool = True):
    """
    Componente de indicador de carregamento reutilizável.
    
    Args:
        id (str): ID único para o elemento
        message (str): Mensagem principal de carregamento
        additional_message (str, optional): Mensagem adicional, geralmente em fonte menor
        hidden (bool, optional): Se True, o componente inicia oculto
        
    Returns:
        O componente de indicador de carregamento
    """
    display_style = "display: none;" if hidden else "display: block;"
    
    content = [
        Div(cls="loader-spinner"), 
        Span(message, id=f"{id}-message")
    ]
    
    if additional_message:
        content.append(P(additional_message, style="font-size: 0.85rem; margin-top: 0.5rem;"))
    
    return Div(
        *content,
        id=id,
        cls="loading-indicator",
        style=display_style
    )

def back_button(link: str = "/", text: str = "← Voltar"):
    """
    Botão de voltar padronizado.
    
    Args:
        link (str, optional): Link de destino, padrão para página inicial
        text (str, optional): Texto do botão
        
    Returns:
        O componente de botão de voltar
    """
    return A(
        text, 
        href=link, 
        cls="back-button",
        style="background-color: #2196F3 !important; color: white !important; border: none !important;"
    )

def success_message(message: str, *additional_content):
    """
    Componente de mensagem de sucesso.
    
    Args:
        message (str): Mensagem principal
        *additional_content: Conteúdo adicional (links, etc.)
        
    Returns:
        O componente de mensagem de sucesso
    """
    return Div(
        P(f"✅ {message}"),
        *additional_content,
        cls="success-message"
    )

def error_message(message: str, *additional_content):
    """
    Componente de mensagem de erro.
    
    Args:
        message (str): Mensagem de erro
        *additional_content: Conteúdo adicional (links, etc.)
        
    Returns:
        O componente de mensagem de erro
    """
    return Div(
        P(f"❌ {message}"),
        *additional_content,
        cls="error-message"
    )

def warning_message(message: str, *additional_content):
    """
    Componente de mensagem de aviso.
    
    Args:
        message (str): Mensagem de aviso
        *additional_content: Conteúdo adicional (links, etc.)
        
    Returns:
        O componente de mensagem de aviso
    """
    return Div(
        P(f"⚠️ {message}"),
        *additional_content,
        cls="warning-message"
    )

def section_header(title: str, description: str = None):
    """
    Cabeçalho de seção padronizado.
    
    Args:
        title (str): Título da seção
        description (str, optional): Descrição opcional da seção
        
    Returns:
        O componente de cabeçalho de seção
    """
    content = [H1(title)]
    
    if description:
        content.append(P(description))
    
    return Header(*content, cls="section-header")

def download_link(file_path: str, text: str = "Baixar", icon: str = "📄", target: str = "_blank"):
    """
    Link de download padronizado.
    
    Args:
        file_path (str): Caminho para o arquivo
        text (str, optional): Texto do link
        icon (str, optional): Ícone do link
        target (str, optional): Alvo do link (_blank, _self, etc.)
        
    Returns:
        O componente de link de download
    """
    return A(
        f"{icon} {text}", 
        href=file_path, 
        target=target, 
        cls="download-link"
    )

def two_column_layout(left_content, right_content, left_width: str = "60%", right_width: str = "40%"):
    """
    Layout de duas colunas.
    
    Args:
        left_content: Lista de conteúdo da coluna esquerda
        right_content: Lista de conteúdo da coluna direita
        left_width (str, optional): Largura da coluna esquerda
        right_width (str, optional): Largura da coluna direita
        
    Returns:
        O componente de layout de duas colunas
    """
    return Div(
        Div(*left_content, cls="left-column", style=f"width: {left_width};"),
        Div(*right_content, cls="right-column", style=f"width: {right_width};"),
        cls="two-column-container"
    )

def content_container(*content, width: str = "1000px", padding: str = "1rem 1.5rem"):
    """
    Container de conteúdo padronizado.
    
    Args:
        *content: Conteúdo do container
        width (str, optional): Largura máxima do container
        padding (str, optional): Padding interno do container
        
    Returns:
        O componente de container de conteúdo
    """
    return Main(
        *content,
        cls="container",
        style=f"max-width: {width}; padding: {padding};"
    )

def tab_layout(tabs: list, tab_contents: list, active_tab: int = 0):
    """
    Layout de abas.
    
    Args:
        tabs (list): Lista de títulos das abas
        tab_contents (list): Lista de conteúdos correspondentes
        active_tab (int, optional): Índice da aba ativa por padrão
        
    Returns:
        O componente de layout de abas
    """
    # Script para gerenciar as abas
    tabs_script = Script("""
    document.addEventListener('DOMContentLoaded', function() {
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = document.querySelectorAll('.tab-content');
        
        function activateTab(index) {
            // Desativar todas as abas
            tabButtons.forEach(button => button.classList.remove('active'));
            tabContents.forEach(content => content.style.display = 'none');
            
            // Ativar a aba selecionada
            tabButtons[index].classList.add('active');
            tabContents[index].style.display = 'block';
        }
        
        // Adicionar listeners de eventos
        tabButtons.forEach((button, index) => {
            button.addEventListener('click', function() {
                activateTab(index);
            });
        });
        
        // Ativar a aba inicial
        activateTab(%d);
    });
    """ % active_tab)
    
    # Criar os botões das abas
    tab_buttons = []
    for i, tab in enumerate(tabs):
        is_active = i == active_tab
        tab_buttons.append(
            Button(
                tab, 
                cls=f"tab-button{'active' if is_active else ''}", 
                type="button", 
                data_tab=str(i)
            )
        )
    
    # Criar os conteúdos das abas
    tab_content_divs = []
    for i, content in enumerate(tab_contents):
        is_active = i == active_tab
        tab_content_divs.append(
            Div(
                content, 
                cls="tab-content", 
                style=f"display: {'block' if is_active else 'none'};"
            )
        )
    
    # Montar o layout completo
    return Div(
        Div(*tab_buttons, cls="tab-buttons"),
        Div(*tab_content_divs, cls="tab-contents"),
        tabs_script,
        cls="tabs-container"
    )