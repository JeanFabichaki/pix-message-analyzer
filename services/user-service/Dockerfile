FROM python:3.11-slim

WORKDIR /app

# Instala lib comum
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Instala dependências do serviço
COPY services/user-service/requirements.txt /app/services/user-service/requirements.txt
RUN pip install --no-cache-dir -r /app/services/user-service/requirements.txt

# Copia código do serviço
COPY services/user-service/src /app/services/user-service/src

WORKDIR /app/services/user-service
ENV PYTHONPATH="/app/services/user-service:/app/libs/common"

EXPOSE 8002

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
