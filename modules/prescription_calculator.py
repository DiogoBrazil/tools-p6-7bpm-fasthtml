# modules/prescription_calculator.py

import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Tuple, Optional
import logging

log = logging.getLogger(__name__)

NATUREZA_PRAZOS = {
    "Leve": relativedelta(years=1),
    "Média": relativedelta(years=2),
    "Grave": relativedelta(years=5)
}

def calculate_prescription(
    natureza: str,
    data_conhecimento: datetime.date,
    data_instauracao: datetime.date,
    suspensions: Optional[List[Dict[str, datetime.date]]] = None
) -> Tuple[bool, str, Optional[datetime.date]]:
    """
    Calcula a data de prescrição disciplinar.

    Args:
        natureza (str): "Leve", "Média" ou "Grave".
        data_conhecimento (date): Data de conhecimento do fato.
        data_instauracao (date): Data de instauração (interrupção).
        suspensions (list, optional): Lista de dicionários [{'inicio': date, 'fim': date}]. Defaults to None.

    Returns:
        tuple: (bool: is_prescribed_already, str: message, date|None: final_prescription_date)
               Retorna (True, msg, None) se já prescreveu.
               Retorna (False, msg, data_final) se ainda não prescreveu.
    """
    if natureza not in NATUREZA_PRAZOS:
        return True, f"Natureza de infração inválida: {natureza}", None
    if not isinstance(data_conhecimento, datetime.date) or not isinstance(data_instauracao, datetime.date):
         return True, "Datas inválidas fornecidas.", None
    if data_conhecimento > data_instauracao:
        return True, "Data de instauração não pode ser anterior à data de conhecimento.", None

    prazo_base = NATUREZA_PRAZOS[natureza]
    today = datetime.date.today()
    suspensions = suspensions or [] # Garante que seja uma lista

    # 1. Verificar prescrição ANTES da instauração
    prescricao_sem_interrupcao = data_conhecimento + prazo_base
    if data_instauracao >= prescricao_sem_interrupcao:
        msg = (f"PRESCRIÇÃO OCORRIDA (ANTES DA INSTAURAÇÃO)! "
               f"Prazo inicial ({natureza} - {prazo_base.years} ano(s)) a partir de {data_conhecimento.strftime('%d/%m/%Y')} "
               f"encerrou em {prescricao_sem_interrupcao.strftime('%d/%m/%Y')}. "
               f"Instauração ({data_instauracao.strftime('%d/%m/%Y')}) foi posterior.")
        log.warning(msg)
        return True, msg, None

    # 2. Calcular prazo a partir da data de instauração (interrupção)
    prescricao_base_interrompida = data_instauracao + prazo_base

    # 3. Calcular dias totais de suspensão válidos
    total_dias_suspensao = datetime.timedelta(days=0)
    dias_susp_str_parts = []
    for i, susp in enumerate(suspensions):
        inicio = susp.get('inicio')
        fim = susp.get('fim')
        if isinstance(inicio, datetime.date) and isinstance(fim, datetime.date) and fim >= inicio:
            # Considera apenas suspensões que ocorrem *após ou no mesmo dia* da instauração
            # e *antes* da data base de prescrição pós-interrupção (suspensão não "revive" prazo já extinto)
            if inicio >= data_instauracao and inicio < prescricao_base_interrompida:
                # Calcula a duração. Adiciona 1 dia pois o período inclui ambos os limites (ex: 01 a 01 = 1 dia)
                # Mas a interpretação comum de prazo é que ele volta a correr *no dia seguinte* ao fim.
                # Se suspende de 01 a 03, o prazo não corre nos dias 01, 02, 03 (3 dias). fim-inicio = 2. Adicionar 1.
                duracao_susp = (fim - inicio) + datetime.timedelta(days=1)
                if duracao_susp.days >= 0:
                    total_dias_suspensao += duracao_susp
                    dias_susp_str_parts.append(f"{duracao_susp.days}d ({inicio.strftime('%d/%m/%y')}-{fim.strftime('%d/%m/%y')})")
                else:
                     log.warning(f"Período de suspensão {i+1} inválido (fim < inicio): {susp}")
            else:
                 log.warning(f"Período de suspensão {i+1} ignorado (fora do prazo relevante): {susp}")
        else:
            log.warning(f"Período de suspensão {i+1} inválido ou incompleto: {susp}")

    # 4. Calcular data final com suspensões
    data_final_prescricao = prescricao_base_interrompida + total_dias_suspensao

    # 5. Montar mensagem final
    data_final_str = data_final_prescricao.strftime('%d/%m/%Y')
    total_dias_susp_str = total_dias_suspensao.days
    info_suspensao = f", com {total_dias_susp_str} dia(s) de suspensão ({', '.join(dias_susp_str_parts)})" if total_dias_susp_str > 0 else ""

    if data_final_prescricao < today:
        msg = (f"PRESCRIÇÃO OCORRIDA! Prazo finalizou em {data_final_str}. "
               f"(Base: {natureza}, Interrupção: {data_instauracao.strftime('%d/%m/%Y')}{info_suspensao})")
        log.info(msg)
        return True, msg, data_final_prescricao
    else:
        msg = (f"DENTRO DO PRAZO. Prescrição ocorrerá em {data_final_str}. "
               f"(Base: {natureza}, Interrupção: {data_instauracao.strftime('%d/%m/%Y')}{info_suspensao})")
        log.info(msg)
        return False, msg, data_final_prescricao