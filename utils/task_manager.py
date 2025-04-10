# utils/task_manager.py

import time
import logging
import threading
import asyncio
import uuid
from typing import Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor
from starlette.background import BackgroundTasks

# Configuração de logging
log = logging.getLogger(__name__)

# Dicionário global para armazenar o estado de tarefas em andamento e seus resultados
# task_id -> {status, result, error, progress, start_time, end_time}
TASK_STORE: Dict[str, Dict[str, Any]] = {}

# Executor de threads para processamento em background
# Limite o número máximo de workers para evitar sobrecarga do servidor
MAX_WORKERS = 8  # Ajuste conforme necessário para seu hardware
task_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Bloqueio para acesso seguro ao dicionário de tarefas
task_store_lock = threading.Lock()

def generate_task_id() -> str:
    """
    Gera um ID único para cada tarefa.
    
    Returns:
        str: ID único da tarefa (UUID)
    """
    return str(uuid.uuid4())

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Retorna o status atual de uma tarefa pelo ID.
    
    Args:
        task_id (str): ID da tarefa
        
    Returns:
        Optional[Dict[str, Any]]: Informações sobre a tarefa ou None se não encontrada
    """
    with task_store_lock:
        return TASK_STORE.get(task_id)

def update_task_status(task_id: str, **kwargs) -> None:
    """
    Atualiza o status de uma tarefa no armazenamento.
    
    Args:
        task_id (str): ID da tarefa
        **kwargs: Campos a serem atualizados
    """
    with task_store_lock:
        if task_id in TASK_STORE:
            TASK_STORE[task_id].update(kwargs)
        else:
            log.warning(f"Tentativa de atualizar tarefa inexistente: {task_id}")

def clean_old_tasks(max_age_hours: int = 24) -> None:
    """
    Remove tarefas antigas do armazenamento para evitar vazamento de memória.
    
    Args:
        max_age_hours (int, optional): Idade máxima em horas para manter tarefas
    """
    cutoff_time = time.time() - (max_age_hours * 3600)
    with task_store_lock:
        task_ids_to_remove = [
            task_id for task_id, task_data in TASK_STORE.items()
            if task_data.get('end_time', 0) < cutoff_time
        ]
        for task_id in task_ids_to_remove:
            del TASK_STORE[task_id]
    
    if task_ids_to_remove:
        log.info(f"Limpeza: removidas {len(task_ids_to_remove)} tarefas antigas")

async def task_cleanup_scheduler():
    """
    Agenda limpeza periódica de tarefas antigas. 
    Esta função deve ser iniciada como uma tarefa assíncrona.
    """
    while True:
        await asyncio.sleep(3600)  # Executa a cada hora
        clean_old_tasks()

def execute_task_in_thread(task_id: str, func: Callable, *args, **kwargs) -> None:
    """
    Executa a função na thread do executor e atualiza o status no armazenamento.
    Esta função é executada dentro da ThreadPoolExecutor.
    
    Args:
        task_id (str): ID da tarefa
        func (Callable): Função a ser executada
        *args, **kwargs: Argumentos para a função
    """
    try:
        # Atualiza status como "em progresso"
        update_task_status(
            task_id, 
            status="processing",
            progress=0,
            start_time=time.time()
        )
        
        # Executa a função original
        result = func(*args, **kwargs)
        
        # Atualiza status como "concluído" com o resultado
        update_task_status(
            task_id, 
            status="completed",
            result=result,
            progress=100,
            end_time=time.time()
        )
        
        log.info(f"Tarefa {task_id} concluída com sucesso")
        
    except Exception as e:
        # Em caso de erro, registra no status
        error_msg = str(e)
        log.error(f"Erro na tarefa {task_id}: {error_msg}", exc_info=True)
        update_task_status(
            task_id, 
            status="failed",
            error=error_msg,
            end_time=time.time()
        )

def submit_task(func: Callable, *args, **kwargs) -> str:
    """
    Submete uma função para execução em background.
    
    Args:
        func (Callable): A função a ser executada
        *args, **kwargs: Argumentos para a função
        
    Returns:
        str: O ID da tarefa para consulta posterior
    """
    task_id = generate_task_id()
    
    # Inicializa o registro da tarefa
    with task_store_lock:
        TASK_STORE[task_id] = {
            "status": "pending",
            "submit_time": time.time(),
            "progress": 0,
            "result": None,
            "error": None
        }
    
    # Submete a tarefa para a pool de threads
    task_executor.submit(execute_task_in_thread, task_id, func, *args, **kwargs)
    
    log.info(f"Tarefa {task_id} enviada para processamento em background")
    return task_id

def start_background_task(background_tasks: BackgroundTasks, func: Callable, *args, **kwargs) -> str:
    """
    Inicia uma tarefa em background e retorna seu ID.
    Para uso com o sistema BackgroundTasks do Starlette.
    
    Args:
        background_tasks (BackgroundTasks): Objeto BackgroundTasks do Starlette
        func (Callable): Função a ser executada
        *args, **kwargs: Argumentos para a função
        
    Returns:
        str: ID da tarefa
    """
    task_id = generate_task_id()
    
    # Inicializa o registro da tarefa
    with task_store_lock:
        TASK_STORE[task_id] = {
            "status": "pending",
            "submit_time": time.time(),
            "progress": 0,
            "result": None,
            "error": None
        }
    
    # Define a função wrapper que será executada em background
    def _background_wrapper():
        execute_task_in_thread(task_id, func, *args, **kwargs)
    
    # Adiciona a tarefa à fila de background
    background_tasks.add_task(_background_wrapper)
    
    log.info(f"Tarefa {task_id} agendada em background via BackgroundTasks")
    return task_id

async def initialize_async_processor():
    """
    Inicializa o processador assíncrono.
    Deve ser chamada durante o lifespan da aplicação.
    
    Returns:
        bool: True se a inicialização foi bem-sucedida
    """
    # Inicia o agendador de limpeza em uma tarefa assíncrona
    asyncio.create_task(task_cleanup_scheduler())
    log.info("Processador assíncrono inicializado com sucesso")
    return True

def shutdown_async_processor():
    """
    Finaliza o processador assíncrono de forma limpa.
    Deve ser chamada durante o encerramento da aplicação.
    """
    task_executor.shutdown(wait=False)
    log.info("Processador assíncrono finalizado")

def get_pending_tasks_count() -> int:
    """
    Retorna o número de tarefas pendentes ou em andamento.
    
    Returns:
        int: Número de tarefas pendentes ou em andamento
    """
    with task_store_lock:
        return len([
            task_id for task_id, task_data in TASK_STORE.items()
            if task_data.get('status') in ('pending', 'processing')
        ])

def get_task_progress(task_id: str) -> int:
    """
    Retorna o progresso de uma tarefa específica.
    
    Args:
        task_id (str): ID da tarefa
        
    Returns:
        int: Progresso da tarefa (0-100) ou -1 se a tarefa não existir
    """
    with task_store_lock:
        task_data = TASK_STORE.get(task_id)
        if task_data:
            return task_data.get('progress', 0)
        return -1

def cancel_task(task_id: str) -> bool:
    """
    Tenta cancelar uma tarefa pendente.
    Observe que isso apenas marca a tarefa como cancelada, mas não interrompe
    uma tarefa que já está em execução.
    
    Args:
        task_id (str): ID da tarefa
        
    Returns:
        bool: True se a tarefa foi cancelada com sucesso
    """
    with task_store_lock:
        task_data = TASK_STORE.get(task_id)
        if not task_data:
            return False
        
        if task_data.get('status') == 'pending':
            task_data.update({
                'status': 'cancelled',
                'end_time': time.time()
            })
            log.info(f"Tarefa {task_id} cancelada")
            return True
        
        # Não pode cancelar tarefas já em andamento ou concluídas
        return False