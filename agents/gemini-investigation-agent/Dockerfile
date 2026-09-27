FROM python:3.11-slim

WORKDIR /app

# Instala lib comum
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Instala dependências do agente
COPY agents/gemini-investigation-agent/requirements.txt /app/agents/gemini-investigation-agent/requirements.txt
RUN pip install --no-cache-dir -r /app/agents/gemini-investigation-agent/requirements.txt

# Copia código do agente
COPY agents/gemini-investigation-agent/src /app/agents/gemini-investigation-agent/src

WORKDIR /app/agents/gemini-investigation-agent
ENV PYTHONPATH="/app/agents/gemini-investigation-agent:/app/libs/common"

EXPOSE 8003

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]
