"""Wrapper de compatibilidade retroativa para Ollaya."""
from src.clients.ollaya_client import OllayaClient


class JevClient(OllayaClient):
    """JevClient agora redireciona as chamadas para o Ollaya Decision Model Server."""
    pass
