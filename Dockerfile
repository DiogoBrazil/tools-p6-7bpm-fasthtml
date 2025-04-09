# Use uma imagem Python base
FROM python:3.10-slim

WORKDIR /app

# Variáveis de ambiente
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Caches (opcional, mas bom para build)
    PIP_CACHE_DIR=/root/.cache/pip \
    TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers \
    HF_HOME=/root/.cache/huggingface

# Instalar dependências do sistema (MANTENHA AS SUAS ORIGINAIS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    tesseract-ocr tesseract-ocr-por tesseract-ocr-eng \
    ocrmypdf \
    libreoffice \
    ffmpeg \
    build-essential \
    cmake \
    # libpq-dev (Removido - Não parece necessário baseado nos requisitos atuais)
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Criar diretórios necessários
RUN mkdir -p /app/static /app/modules /app/files /app/letsencrypt

# Copiar requirements e instalar dependências Python
COPY requirements.txt .

# Instalar wheel e setuptools antes das dependências principais
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Instalar as dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante da aplicação
COPY . .

# Expor a porta que o Uvicorn usará
EXPOSE 8000

# Comando para rodar a aplicação com Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]