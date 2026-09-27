FROM python:3.11-slim

WORKDIR /app

# Instala lib comum
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Instala dependências do serviço
COPY services/threat-intelligence-service/requirements.txt /app/services/threat-intelligence-service/requirements.txt
RUN pip install --no-cache-dir -r /app/services/threat-intelligence-service/requirements.txt

# Copia código do serviço
COPY services/threat-intelligence-service/src /app/services/threat-intelligence-service/src

WORKDIR /app/services/threat-intelligence-service
ENV PYTHONPATH="/app/services/threat-intelligence-service:/app/libs/common"

EXPOSE 8004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004"]
