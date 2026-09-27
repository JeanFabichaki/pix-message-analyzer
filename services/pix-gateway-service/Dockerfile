FROM python:3.11-slim

WORKDIR /app

# Instala lib comum
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Instala dependências do serviço
COPY services/pix-gateway-service/requirements.txt /app/services/pix-gateway-service/requirements.txt
RUN pip install --no-cache-dir -r /app/services/pix-gateway-service/requirements.txt

# Copia código do serviço
COPY services/pix-gateway-service/src /app/services/pix-gateway-service/src

WORKDIR /app/services/pix-gateway-service
ENV PYTHONPATH="/app/services/pix-gateway-service:/app/libs/common"

EXPOSE 8001

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
