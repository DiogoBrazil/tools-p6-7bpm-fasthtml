# modules/media_converter.py

import os
import tempfile
import subprocess
import logging
import whisper # openai-whisper
import shutil
import json
# REMOVIDO: import streamlit as st

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__) # Logger específico

WHISPER_MODEL_NAME = "small" # Ou o modelo que você preferir

# Variáveis globais para caminhos (ainda podem ser úteis)
ffmpeg_path = None
ffprobe_path = None

# --- Funções _find_ffmpeg e _find_ffprobe mantidas como antes ---
def _find_ffmpeg():
    """Encontra o caminho do ffmpeg."""
    global ffmpeg_path
    if ffmpeg_path: return ffmpeg_path
    # Usar shutil.which que é mais robusto
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        log.info(f"FFmpeg encontrado em: {ffmpeg_path}")
    else:
        # Usar logging.error para erros críticos
        log.error("FFmpeg não encontrado no PATH. Funções de áudio/vídeo não funcionarão.")
    return ffmpeg_path

def _find_ffprobe():
    """Encontra o caminho do ffprobe."""
    global ffprobe_path
    if ffprobe_path: return ffprobe_path
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        log.info(f"ffprobe encontrado em: {ffprobe_path}")
    else:
        # Usar logging.warning para avisos
        log.warning("ffprobe não encontrado no PATH. Verificação de stream de áudio não será possível.")
    return ffprobe_path

# --- NOVA Função para carregar o modelo (será chamada pelo lifespan) ---
# REMOVIDO: @st.cache_resource(...)
def load_whisper_model_instance():
    """
    Carrega a instância do modelo Whisper especificado.
    Esta função deve ser chamada apenas uma vez na inicialização do servidor.
    """
    model = None
    try:
        log.info(f"Carregando modelo Whisper '{WHISPER_MODEL_NAME}'...")
        # Garante que ffmpeg está disponível, pois whisper pode precisar
        if not _find_ffmpeg():
             log.error("FFmpeg não encontrado, necessário para Whisper. Tentando carregar mesmo assim...")
             # Whisper pode funcionar para alguns formatos sem ffmpeg, mas é arriscado.
             # Não vamos impedir o carregamento aqui, mas o erro já foi logado.

        # Carrega o modelo
        model = whisper.load_model(WHISPER_MODEL_NAME)
        log.info(f"Modelo Whisper '{WHISPER_MODEL_NAME}' carregado com sucesso.")
        return model
    except Exception as e:
        log.error(f"Erro CRÍTICO ao carregar modelo Whisper '{WHISPER_MODEL_NAME}': {e}", exc_info=True)
        # Retorna None para indicar falha no carregamento,
        # o lifespan em app.py deve tratar isso.
        return None

# --- Função _has_audio_stream mantida como antes ---
# (Revisada para usar logging consistentemente)
def _has_audio_stream(input_path):
    """Verifica se o arquivo de mídia contém pelo menos um stream de áudio usando ffprobe."""
    ffprobe = _find_ffprobe()
    if not ffprobe:
        log.warning("ffprobe não encontrado. Pulando verificação de streams de áudio.")
        # Retornar True aqui é uma suposição; pode levar a erros no ffmpeg depois
        # mas é melhor que impedir a operação sem poder verificar.
        return True, "Verificação de áudio pulada (ffprobe não encontrado)."

    command = [
        ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_streams', '-select_streams', 'a', input_path
    ]
    log.info(f"Verificando streams de áudio com ffprobe para: {os.path.basename(input_path)}")
    try:
        # Timeout aumentado um pouco para arquivos maiores/rede
        process = subprocess.run(command, capture_output=True, check=False, text=True, timeout=90)

        if process.returncode != 0:
            # Log mais detalhado do erro ffprobe
            log.error(f"Erro ao executar ffprobe (código {process.returncode}): {process.stderr.strip()}")
            return True, f"Falha ao analisar streams (erro ffprobe)." # Assume que tem audio para tentar converter

        # Verificar se stdout não está vazio antes de tentar decodificar JSON
        if not process.stdout or not process.stdout.strip():
            log.warning(f"ffprobe não retornou dados de stream de áudio para {os.path.basename(input_path)} (saída vazia).")
            # Pode ser um arquivo sem áudio ou corrompido
            return False, "O arquivo pode não conter áudio ou ffprobe falhou em analisá-lo."

        streams_info = json.loads(process.stdout)
        if streams_info and 'streams' in streams_info and streams_info['streams']:
             log.info("Stream de áudio detectado.")
             return True, "Stream de áudio encontrado."
        else:
             log.info("Nenhum stream de áudio detectado.")
             return False, "O arquivo de vídeo selecionado não contém uma trilha de áudio."

    except json.JSONDecodeError as json_err:
        log.error(f"Erro ao decodificar JSON do ffprobe: {json_err}. Saída recebida: '{process.stdout[:200]}...'")
        return True, "Falha ao ler informações dos streams (erro JSON)." # Assume que tem para tentar
    except subprocess.TimeoutExpired:
        log.error("ffprobe excedeu o tempo limite ao verificar streams de áudio.")
        return True, "Verificação de áudio excedeu o tempo limite." # Assume que tem para tentar
    except Exception as e:
        log.error(f"Erro inesperado ao verificar streams de áudio: {str(e)}", exc_info=True)
        return True, f"Erro inesperado na verificação de áudio." # Assume que tem para tentar


# --- Função convert_video_to_mp3 mantida como antes ---
# (Revisada para usar logging consistentemente)
def convert_video_to_mp3(input_video_path, output_mp3_path):
    """Converte um arquivo de vídeo para MP3 usando ffmpeg, verificando antes se há áudio."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        # Log já foi feito em _find_ffmpeg
        return False, "FFmpeg não encontrado no sistema."

    # 1. Verificar se o arquivo de entrada existe
    if not os.path.exists(input_video_path):
        log.error(f"Arquivo de entrada não encontrado: {input_video_path}")
        return False, "Arquivo de vídeo de entrada não encontrado."

    # 2. Verificar stream de áudio
    has_audio, check_msg = _has_audio_stream(input_video_path)
    if not has_audio:
        log.warning(f"Conversão cancelada: {check_msg} para o arquivo {os.path.basename(input_video_path)}")
        return False, check_msg # Retorna a mensagem do _has_audio_stream

    log.info(f"Iniciando conversão para MP3: {os.path.basename(input_video_path)}")

    # Comando FFmpeg (mantido) - '-y' para sobrescrever saída se existir
    command = [
        ffmpeg, '-i', input_video_path,
        '-vn',             # Desabilitar vídeo
        '-acodec', 'libmp3lame', # Codec MP3
        '-ab', '192k',     # Bitrate de áudio
        '-ar', '44100',    # Sample rate
        '-y',              # Sobrescrever arquivo de saída
        output_mp3_path
    ]
    log.info(f"Executando comando FFmpeg: {' '.join(command)}")

    try:
        # Timeout para conversão (pode precisar ser maior para vídeos longos)
        process = subprocess.run(command, capture_output=True, check=False, text=True, timeout=600) # 10 minutos

        # Verificar código de retorno do ffmpeg
        if process.returncode != 0:
            error_msg_detail = process.stderr.strip()
            log.error(f"Erro no FFmpeg (código {process.returncode}) ao converter {os.path.basename(input_video_path)}:\n{error_msg_detail}")

            # Mensagem de erro mais amigável
            error_msg_user = "Ocorreu um erro durante a conversão com FFmpeg."
            if "Output file #0 does not contain any stream" in error_msg_detail:
                 error_msg_user = "Erro na conversão: O arquivo pode não ter áudio válido ou estar corrompido."
            # Tentar remover saída parcial se existir
            if os.path.exists(output_mp3_path):
                try: os.unlink(output_mp3_path)
                except OSError as e: log.warning(f"Não foi possível remover arquivo de saída parcial {output_mp3_path}: {e}")
            return False, error_msg_user

        # Verificar se o arquivo de saída foi criado e não está vazio
        if not os.path.exists(output_mp3_path) or os.path.getsize(output_mp3_path) == 0:
             error_msg = f"FFmpeg terminou sem erro aparente, mas o arquivo MP3 '{os.path.basename(output_mp3_path)}' não foi criado ou está vazio."
             log.error(error_msg)
             # Tentar remover saída vazia se existir
             if os.path.exists(output_mp3_path):
                try: os.unlink(output_mp3_path)
                except OSError as e: log.warning(f"Não foi possível remover arquivo de saída vazio {output_mp3_path}: {e}")
             return False, "Falha na criação do arquivo MP3 após conversão."

        log.info(f"Conversão vídeo->MP3 concluída com sucesso: {os.path.basename(output_mp3_path)}")
        return True, "Conversão concluída com sucesso."

    except subprocess.TimeoutExpired:
        log.error(f"Conversão vídeo->MP3 excedeu o tempo limite de 600s para {os.path.basename(input_video_path)}.")
        # Tentar remover saída parcial
        if os.path.exists(output_mp3_path):
             try: os.unlink(output_mp3_path)
             except OSError as e: log.warning(f"Não foi possível remover arquivo de saída parcial (timeout) {output_mp3_path}: {e}")
        return False, "Conversão excedeu o tempo limite."
    except Exception as e:
        error_msg = f"Erro inesperado na conversão vídeo->MP3: {str(e)}"
        log.exception(error_msg) # Loga o traceback completo
        # Tentar remover saída parcial
        if os.path.exists(output_mp3_path):
            try: os.unlink(output_mp3_path)
            except OSError as os_err: log.warning(f"Não foi possível remover arquivo de saída parcial (exceção) {output_mp3_path}: {os_err}")
        return False, "Ocorreu um erro inesperado durante o processamento."


# --- Função transcribe_audio_file MANTIDA - Recebe o modelo como argumento ---
def transcribe_audio_file(input_audio_path, model):
    """
    Transcreve um arquivo de áudio usando um modelo Whisper pré-carregado.

    Args:
        input_audio_path (str): Caminho para o arquivo de áudio.
        model: A instância carregada do modelo Whisper.

    Returns:
        tuple: (bool: success, str: message, str: transcribed_text)
    """
    # A verificação se o modelo foi carregado deve ser feita ANTES de chamar esta função
    if not model:
        log.error("Tentativa de transcrever áudio sem um modelo Whisper válido.")
        # Esta verificação é uma salvaguarda, o erro principal deve ser pego no app.py
        return False, "Modelo de transcrição não disponível.", ""

    # Garante que ferramentas ffmpeg/ffprobe foram checadas (necessário para whisper)
    _find_ffmpeg()
    _find_ffprobe()

    # Verificar se o arquivo de entrada existe
    if not os.path.exists(input_audio_path):
        log.error(f"Arquivo de áudio para transcrição não encontrado: {input_audio_path}")
        return False, "Arquivo de áudio de entrada não encontrado.", ""

    log.info(f"Iniciando transcrição com Whisper ({WHISPER_MODEL_NAME}): {os.path.basename(input_audio_path)}")
    try:
        # Realiza a transcrição
        # fp16=False é mais seguro para CPU, True pode ser mais rápido em GPU compatível
        result = model.transcribe(input_audio_path, language='pt', fp16=False)
        transcribed_text = result.get("text", "") # Usar .get para evitar KeyError
        log.info(f"Transcrição Whisper concluída para {os.path.basename(input_audio_path)}.")
        return True, "Transcrição concluída com sucesso.", transcribed_text

    except Exception as e:
        error_msg = f"Erro durante a transcrição com Whisper: {str(e)}"
        # Verificar se pode ser falta do ffmpeg
        if not ffmpeg_path and isinstance(e, RuntimeError) and "ffmpeg" in str(e).lower():
             error_msg += " (Verifique se FFmpeg está instalado e no PATH do sistema, pois é necessário para Whisper processar muitos formatos de áudio)"
        log.exception(error_msg) # Loga o traceback
        return False, "Ocorreu um erro durante a transcrição.", ""