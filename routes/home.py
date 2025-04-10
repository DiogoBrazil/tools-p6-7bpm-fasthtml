from fasthtml.common import *
from components.layout import page_layout
from components.ui import tool_card

def register_routes(app):
    """Registra todas as rotas relacionadas à página inicial"""
    
    @app.route("/", methods=["GET"])
    def home():
        """Renderiza a página inicial com os cards de ferramentas"""
        
        cards = [
            tool_card(
                id="card-pdf", 
                icon="📄", 
                title="Ferramentas PDF", 
                description="Comprima, OCR, junte, converta PDFs.",
                items=["Juntar, comprimir, OCR", "Doc/Planilha/Imagem → PDF", "PDF → Docx/Imagem"],
                link="/pdf-tools", 
                link_text="ABRIR FERRAMENTAS PDF"
            ),
            tool_card(
                id="card-text", 
                icon="📝", 
                title="Corretor de Texto", 
                description="Revise e corrija textos usando IA.",
                items=["Correção gramatical", "Ortografia e pontuação", "Português Brasileiro"],
                link="/text-corrector", 
                link_text="ABRIR CORRETOR"
            ),
            tool_card(
                id="card-media", 
                icon="🎵", 
                title="Conversor para MP3", 
                description="Converta arquivos de vídeo para áudio MP3.",
                items=["Suporta MP4, AVI, MOV...", "Extração rápida de áudio", "Saída em MP3 (192k)"],
                link="/video-converter", 
                link_text="ABRIR CONVERSOR MP3"
            ),
            tool_card(
                id="card-transcribe", 
                icon="🎤", 
                title="Transcritor de Áudio", 
                description="Converta arquivos de áudio em texto.",
                items=["Suporta MP3, WAV, M4A...", "Transcrição Whisper", "Refinamento IA opcional"],
                link="/audio-transcriber", 
                link_text="ABRIR TRANSCRITOR"
            ),
            tool_card(
                id="card-rdpm", 
                icon="⚖️", 
                title="Consulta RDPM", 
                description="Tire dúvidas sobre o RDPM.",
                items=["Busca no texto oficial", "Respostas baseadas no RDPM", "Assistente IA especializado"],
                link="/rdpm-query", 
                link_text="CONSULTAR RDPM"
            ),
            tool_card(
                id="card-prescricao", 
                icon="⏳", 
                title="Calculadora de Prescrição", 
                description="Calcule prazos prescricionais disciplinares.",
                items=["Considera natureza da infração", "Trata interrupções", "Adiciona períodos de suspensão"],
                link="/prescription-calculator", 
                link_text="ABRIR CALCULADORA"
            ),
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