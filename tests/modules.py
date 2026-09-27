import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Injeta libs/common no sys.path
common_path = str(ROOT / "libs" / "common")
if common_path not in sys.path:
    sys.path.insert(0, common_path)


def _load_service(svc_root: Path):
    """Adiciona a raiz do serviço ao sys.path, permitindo imports relativos de 'src'."""
    svc_str = str(svc_root)
    if svc_str in sys.path:
        sys.path.remove(svc_str)
    sys.path.insert(0, svc_str)
    # Remove qualquer 'src' em cache para evitar colisão
    for k in list(sys.modules.keys()):
        if k == "src" or k.startswith("src."):
            del sys.modules[k]


# 1. Carrega User Service
_load_service(ROOT / "services" / "user-service")
from src.services.user_service import UserService
from src.main import app as user_service_app

# Salva referências do user-service
UserService = UserService
user_service_app = user_service_app

# 2. Carrega Gemini Investigation Agent
_load_service(ROOT / "agents" / "gemini-investigation-agent")
from src.clients.user_client import UserClient
from src.analyzer import GeminiThreatAnalyzer
from src.rules.threshold import record_and_evaluate_limit
from src.main import app as gemini_agent_app

# 3. Carrega Pix Gateway Service
_load_service(ROOT / "services" / "pix-gateway-service")
from src.clients.ollaya_client import OllayaClient
from src.clients.jev_client import JevClient
from src.clients.investigation import InvestigationClient
from src.clients.threat_intel_client import ThreatIntelClient
from src.clients.user_client import GatewayUserClient
from src.services.interceptor import PixInterceptor
from src.main import app as pix_gateway_app

# 4. Carrega Threat Intelligence Service
_load_service(ROOT / "services" / "threat-intelligence-service")
from src.repository import ThreatIntelligenceRepository
from src.main import app as threat_intel_app
