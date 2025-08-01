FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p /app/static /app/media

# Executar migrações e collectstatic
RUN python manage.py collectstatic --noinput || true

# Expor porta
EXPOSE 8005

# Comando para iniciar a aplicação
CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8005", "--workers", "3"]
