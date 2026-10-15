# Servidor do Laya retreinado: mesmo contrato POST /v1/systemone do Ollaya/Jev, rodando o checkpoint em /models/pix-threats
FROM python:3.11-slim

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir "laya[serve]>=0.4.7"

ENV LAYA_HOST=0.0.0.0 \
    LAYA_PORT=8000 \
    LAYA_DEVICE=cpu \
    LAYA_DEFAULT_MODEL=multilingual \
    USE_TF=0 \
    TOKENIZERS_PARALLELISM=false

EXPOSE 8000
CMD ["laya-serve"]
