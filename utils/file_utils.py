import os
import tempfile
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Union, Tuple, Optional
from starlette.responses import FileResponse, Response, JSONResponse

# Configuração de logging
log = logging.getLogger(__name__)

# Diretório temporário para uploads
UPLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "fasthtml_uploads"
UPLOAD_TEMP_DIR.mkdir(exist_ok=True)

def safe_filename(filename: str) -> str:
    """
    Gera um nome de arquivo seguro, substituindo caracteres problemáticos.
    
    Args:
        filename (str): Nome de arquivo original
        
    Returns:
        str: Nome de arquivo seguro
    """
    # Remover caracteres potencialmente perigosos
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
    # Substituir espaços por underscores
    safe_name = safe_name.replace(" ", "_")
    return safe_name

def generate_temp_filepath(original_filename: str, prefix: str = None) -> Path:
    """
    Gera um caminho temporário para um arquivo, garantindo que seja único.
    
    Args:
        original_filename (str): Nome do arquivo original
        prefix (str, optional): Prefixo opcional a adicionar ao nome do arquivo
        
    Returns:
        Path: Caminho para o arquivo temporário
    """
    # Obtém extensão e nome seguro
    filename = Path(original_filename).name
    filename = safe_filename(filename)
    
    # Gera timestamp para garantir unicidade
    timestamp = int(datetime.now().timestamp())
    
    # Adiciona prefixo se fornecido
    if prefix:
        prefix = safe_filename(prefix)
        new_filename = f"{prefix}_{timestamp}_{filename}"
    else:
        new_filename = f"{timestamp}_{filename}"
    
    return UPLOAD_TEMP_DIR / new_filename

def save_uploaded_file(file, prefix: str = None) -> Tuple[bool, str, Optional[Path]]:
    """
    Salva um arquivo carregado no diretório temporário.
    
    Args:
        file: Objeto de arquivo carregado (Form)
        prefix (str, optional): Prefixo opcional a adicionar ao nome do arquivo
        
    Returns:
        Tuple[bool, str, Optional[Path]]: (sucesso, mensagem, caminho_do_arquivo)
    """
    if not file or not hasattr(file, "filename") or not file.filename:
        return False, "Nenhum arquivo válido fornecido.", None
    
    try:
        # Gerar caminho temporário
        temp_path = generate_temp_filepath(file.filename, prefix)
        
        # Salvar arquivo
        with open(temp_path, "wb") as f:
            file_content = file.file.read()
            f.write(file_content)
        
        log.info(f"Arquivo salvo com sucesso: {temp_path}")
        return True, "Arquivo salvo com sucesso.", temp_path
    
    except Exception as e:
        log.error(f"Erro ao salvar arquivo: {e}", exc_info=True)
        return False, f"Erro ao salvar arquivo: {str(e)}", None

def delete_temp_file(file_path: Union[str, Path]) -> bool:
    """
    Remove um arquivo temporário de forma segura.
    
    Args:
        file_path (Union[str, Path]): Caminho do arquivo a ser removido
        
    Returns:
        bool: True se o arquivo foi removido com sucesso, False caso contrário
    """
    if not file_path:
        return False
    
    path = Path(file_path)
    
    # Verificar se o caminho está dentro do diretório temporário (medida de segurança)
    if UPLOAD_TEMP_DIR not in path.parents and path != UPLOAD_TEMP_DIR:
        log.warning(f"Tentativa de excluir arquivo fora do diretório temporário: {path}")
        return False
    
    try:
        if path.exists():
            path.unlink()
            log.debug(f"Arquivo temporário removido: {path}")
            return True
        else:
            log.warning(f"Tentativa de excluir arquivo inexistente: {path}")
            return False
    except Exception as e:
        log.error(f"Erro ao excluir arquivo temporário {path}: {e}")
        return False

def clean_old_temp_files(max_age_hours: int = 24) -> int:
    """
    Remove arquivos temporários antigos para liberar espaço.
    
    Args:
        max_age_hours (int, optional): Idade máxima em horas para manter arquivos
        
    Returns:
        int: Número de arquivos removidos
    """
    if not UPLOAD_TEMP_DIR.exists():
        return 0
    
    now = datetime.now().timestamp()
    max_age_seconds = max_age_hours * 3600
    removed_count = 0
    
    try:
        for item in UPLOAD_TEMP_DIR.iterdir():
            if item.is_file():
                file_age = now - item.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        item.unlink()
                        removed_count += 1
                    except Exception as e:
                        log.warning(f"Erro ao remover arquivo antigo {item}: {e}")
        
        log.info(f"Limpeza de arquivos temporários: {removed_count} arquivo(s) removido(s).")
        return removed_count
    
    except Exception as e:
        log.error(f"Erro durante limpeza de arquivos temporários: {e}")
        return 0

def get_mime_type(filename: str) -> str:
    """
    Determina o tipo MIME com base na extensão do arquivo.
    
    Args:
        filename (str): Nome do arquivo
        
    Returns:
        str: Tipo MIME do arquivo
    """
    extension = Path(filename).suffix.lower()
    
    mime_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.csv': 'text/csv',
        '.txt': 'text/plain',
        '.zip': 'application/zip',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.mp3': 'audio/mpeg',
        '.mp4': 'video/mp4',
        '.wav': 'audio/wav',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.html': 'text/html',
    }
    
    return mime_types.get(extension, 'application/octet-stream')

def serve_file_download(file_path: Union[str, Path], download_filename: str = None) -> FileResponse:
    """
    Cria uma resposta para download de arquivo.
    
    Args:
        file_path (Union[str, Path]): Caminho do arquivo a ser servido
        download_filename (str, optional): Nome a ser usado para download 
            (se None, usa o nome original)
        
    Returns:
        FileResponse: Resposta para download do arquivo
    """
    path = Path(file_path)
    
    if not path.exists():
        log.error(f"Arquivo para download não encontrado: {path}")
        raise FileNotFoundError(f"Arquivo {path} não existe")
    
    # Se o nome de download não for especificado, usa o nome original do arquivo
    filename = download_filename or path.name
    
    # Determinar o tipo MIME
    media_type = get_mime_type(filename)
    
    return FileResponse(
        path=path,
        filename=filename,
        media_type=media_type
    )

def download_file_route(request, filename: str):
    """
    Rota para download de arquivos temporários.
    Esta função pode ser usada diretamente como handler de rota.
    
    Args:
        request: O objeto de requisição Starlette
        filename (str): Nome do arquivo a baixar
        
    Returns:
        Response: Resposta HTTP apropriada (arquivo ou erro)
    """
    try:
        # Verificar segurança do nome do arquivo
        safe_name = Path(filename).name
        if not safe_name or ".." in safe_name:
            log.warning(f"Tentativa de download com nome de arquivo suspeito: {filename}")
            return Response("Nome de arquivo inválido", status_code=400)
        
        file_path = UPLOAD_TEMP_DIR / safe_name
        
        if not file_path.exists():
            log.warning(f"Arquivo solicitado para download não encontrado: {safe_name}")
            return Response("Arquivo não encontrado", status_code=404)
        
        log.info(f"Servindo download: {safe_name}")
        
        return serve_file_download(file_path)
    
    except Exception as e:
        log.error(f"Erro ao servir download para {filename}: {e}", exc_info=True)
        return Response("Erro ao processar download", status_code=500)

def prepare_error_response(message: str, status_code: int = 400) -> JSONResponse:
    """
    Prepara uma resposta de erro JSON padronizada.
    
    Args:
        message (str): Mensagem de erro
        status_code (int, optional): Código de status HTTP
        
    Returns:
        JSONResponse: Resposta de erro formatada
    """
    return JSONResponse(
        content={"success": False, "error": message},
        status_code=status_code
    )

def prepare_success_response(data=None, message: str = "Operação concluída com sucesso") -> JSONResponse:
    """
    Prepara uma resposta de sucesso JSON padronizada.
    
    Args:
        data: Dados a serem retornados (opcional)
        message (str, optional): Mensagem de sucesso
        
    Returns:
        JSONResponse: Resposta de sucesso formatada
    """
    response = {"success": True, "message": message}
    
    if data is not None:
        response["data"] = data
    
    return JSONResponse(content=response)
