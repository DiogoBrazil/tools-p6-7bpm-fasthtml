# modules/text_corrector.py

import os
import logging
from typing import Union, Optional
from openai import OpenAI # Certifique-se que a versão >= 1.0 está instalada
from dotenv import load_dotenv

# Configuração de Logging (Pode ser configurada centralmente em app.py)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Logger nomeado para este módulo
log = logging.getLogger(__name__)

class TextCorrector:
    """
    Classe responsável por interagir com uma API de LLM (compatível com OpenAI)
    para tarefas de correção de texto e refinamento de transcrições.
    As credenciais e endpoints da API são lidos de variáveis de ambiente.
    """
    def __init__(self):
        """
        Inicializa o TextCorrector carregando as configurações da API
        e instanciando o cliente OpenAI.
        """
        # Carrega variáveis do arquivo .env, se existir, sobrescrevendo as do sistema se presentes no .env
        load_dotenv(override=True)

        # Lê as configurações do ambiente
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com") # Default DeepSeek
        self.model_name = os.getenv("OPENAI_MODEL_NAME", "deepseek-chat") # Default DeepSeek model

        self.client = None # Inicializa o cliente como None

        # Tenta inicializar o cliente OpenAI se a chave API for fornecida
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                log.info(f"Cliente OpenAI inicializado. Base URL: {self.base_url}, Modelo Padrão: {self.model_name}")
            except Exception as e:
                 # Captura e loga erros durante a inicialização do cliente
                 log.error(f"Erro ao inicializar cliente OpenAI com Base URL '{self.base_url}': {e}", exc_info=True)
                 self.client = None # Garante que self.client é None em caso de erro
        else:
            # Loga um aviso se a chave API não for encontrada
            log.warning("OPENAI_API_KEY não encontrada no ambiente ou arquivo .env. Funções de correção via API estarão desabilitadas.")

    def is_configured(self) -> bool:
        """
        Verifica se o cliente da API foi inicializado com sucesso.

        Returns:
            True se o cliente está configurado, False caso contrário.
        """
        return self.client is not None

    def get_llm_client(self) -> Optional[OpenAI]:
        """
        Retorna a instância do cliente OpenAI inicializado.
        Útil para ser usado por outras partes do sistema (como LangChain).

        Returns:
            A instância do cliente OpenAI, ou None se não estiver configurado.
        """
        # Apenas retorna o cliente, a verificação é feita onde ele é usado
        return self.client

    def _call_api(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens_multiplier: float = 1.5, base_tokens: int = 150) -> Optional[str]:
        """Método auxiliar interno para chamar a API de chat completion."""
        if not self.is_configured():
            log.error("Tentativa de chamar API LLM sem cliente configurado.")
            return None

        if not user_prompt or not user_prompt.strip():
             log.debug("_call_api chamado com user_prompt vazio.")
             # Retorna None ou string vazia? String vazia parece mais consistente com os métodos públicos.
             # No entanto, os métodos públicos já tratam input vazio, então None aqui indica falha interna.
             return None # Indica falha interna (não deveria chegar aqui com prompt vazio vindo dos métodos públicos)

        # Estimar max_tokens com base no input
        # Contagem de palavras simples como proxy
        input_words = len(user_prompt.split())
        # Adicionar uma margem e garantir um mínimo
        max_tokens_estimate = max(int(input_words * max_tokens_multiplier) + base_tokens, 200)
        log.info(f"Enviando requisição para LLM (modelo: {self.model_name}, temp: {temperature}, max_tokens ~{max_tokens_estimate})...")

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens_estimate,
                # stream=False # Padrão é False
            )

            # Extrai e limpa a resposta de forma segura
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                result_text = response.choices[0].message.content.strip()
                log.info("Resposta recebida da API LLM.")
                # Remover blocos de código ``` se a API os adicionar por engano
                if result_text.startswith("```") and result_text.endswith("```"):
                     result_text = result_text[3:-3].strip()
                     if result_text.startswith("text"): # Remover 'text' se iniciar com ```text
                          result_text = result_text[4:].strip()
                return result_text
            else:
                log.warning(f"Resposta da API LLM inesperada ou vazia: {response}")
                return None # Retorna None se a resposta não for válida

        except Exception as e:
            # Captura e loga erros durante a chamada da API
            log.error(f"Erro ao chamar API LLM em {self.base_url}: {e}", exc_info=True)
            return None # Retorna None para indicar erro na API

    def correct_text(self, text: str) -> Optional[str]:
        """
        Corrige um texto genérico usando a API configurada.
        Foca em aplicar normas padrão da língua portuguesa.

        Args:
            text: O texto a ser corrigido.

        Returns:
            O texto corrigido como string, ou None se ocorrer um erro ou a API não estiver configurada.
        """
        # Validação de entrada movida para o início
        if not self.is_configured():
             # Log já acontece em _call_api
             return None
        if not text or not text.strip():
            log.debug("correct_text chamado com texto vazio ou apenas espaços.")
            return "" # Retorna string vazia para input vazio

        system_prompt = "Você é um revisor de texto experiente, focado em corrigir erros gramaticais e ortográficos do Português Brasileiro, mantendo o sentido original."
        user_prompt = f'Corrija o seguinte texto aplicando as normas padrões da língua portuguesa. Retorne APENAS o texto corrigido, sem introduções, explicações ou formatação extra (como ```): {text}'

        return self._call_api(system_prompt, user_prompt, temperature=0.3, base_tokens=100)


    def correct_transcription(self, text: str) -> Optional[str]:
        """
        Refina e corrige uma transcrição de áudio usando a API.
        Usa um prompt específico para o contexto de transcrições.

        Args:
            text: A transcrição bruta a ser corrigida/refinada.

        Returns:
            O texto refinado como string, ou None se ocorrer um erro ou a API não estiver configurada.
        """
        # Validação de entrada movida para o início
        if not self.is_configured():
            # Log já acontece em _call_api
            return None
        if not text or not text.strip():
            log.debug("correct_transcription chamado com texto vazio ou apenas espaços.")
            return "" # Retorna string vazia para input vazio

        system_prompt = """Você é um especialista em transcrever e revisar textos de áudios em português brasileiro, especialmente de contextos formais como audiências ou depoimentos. Sua tarefa é pegar a transcrição bruta fornecida e corrigi-la para torná-la clara, gramaticalmente correta e com pontuação adequada. Preste atenção especial a possíveis nomes próprios, patentes militares (Ex: Capitão, Sargento), termos jurídicos ou técnicos, e tente interpretá-los corretamente mesmo que a transcrição inicial esteja confusa. Mantenha o sentido original do que foi dito."""
        user_prompt = f'Corrija e refine a seguinte transcrição de áudio. Retorne APENAS o texto final corrigido e refinado, sem introduções, comentários ou formatação extra (como ```): {text}'

        # Usa temperatura um pouco maior e mais tokens base para permitir reestruturação
        return self._call_api(system_prompt, user_prompt, temperature=0.5, base_tokens=200)