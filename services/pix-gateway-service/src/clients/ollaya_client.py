import logging
import httpx
from common.config.settings import settings
from common.schemas.threat import OllayaClassificationResult

logger = logging.getLogger("gateway.ollaya-client")


class OllayaClient:
    def __init__(
        self,
        base_url: str = settings.OLLAYA_BASE_URL,
        model: str = settings.OLLAYA_MODEL,
        timeout: float = settings.OLLAYA_TIMEOUT_SECONDS,
        **kwargs,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def classify(self, text: str) -> OllayaClassificationResult:
        """Classifica a mensagem síncronamente via API TypeSafe do Ollaya (ollaya.dev) em produção."""
        if not text or not text.strip():
            return OllayaClassificationResult(
                is_threat=False,
                score=0.0,
                category=None,
                model=self.model,
                detail="Mensagem vazia ou sem texto",
            )

        # Contrato TypeSafe /v1/systemone compatível com Ollaya (calibrado para pt-BR)
        payload = {
            "model": self.model,
            "state": text,
            "questions": {
                "threat": {
                    "type": "choice",
                    "instructions": (
                        "Analise em português do Brasil se a mensagem de Pix contém ameaça, agressão física "
                        "iminente, perseguição (stalking), caçada, emboscada, coação, intimidação ou cobrança hostil. "
                        "Atenção: expressões como \"vou te achar\", \"no fim do mundo\", \"vou te pegar\", "
                        "\"esperar na saída\", \"caloteiro\" configuram coação e ameaça grave."
                    ),
                    "criteria": {
                        "threat": "Ameaça física, perseguição, caçada no fim do mundo, emboscada, cobrança violenta, coação ou intimidação",
                        "safe": "Comunicação respeitosa, amigável, romântica consentida, familiar legítima ou comercial normal",
                    },
                }
            },
        }

        url = f"{self.base_url}/v1/systemone"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "pix-gateway-service/1.0 (ollaya-client)",
        }

        try:
            timeout_cfg = httpx.Timeout(self.timeout, connect=4.0)
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException as te:
            logger.error(f"Timeout ao consultar API do Ollaya ({url}): {te}")
            raise RuntimeError(f"Ollaya API indisponível (Timeout): {te}") from te
        except Exception as ex:
            logger.error(f"Erro ao comunicar com API do Ollaya ({url}): {ex}")
            raise RuntimeError(f"Erro na API do Ollaya: {ex}") from ex

        answers = data.get("answers", {})
        threat_ans = answers.get("threat", {})
        choice = threat_ans.get("choice", "safe")
        confidence = float(threat_ans.get("confidence", 0.0))
        probs = threat_ans.get("probabilities", {})
        threat_prob = float(probs.get("threat", confidence if choice == "threat" else 0.0))

        # Ameaça confirmada se o modelo classificar como 'threat' ou probabilidade de risco >= 0.40
        is_threat = (choice == "threat") or (threat_prob >= 0.40)

        return OllayaClassificationResult(
            is_threat=is_threat,
            score=threat_prob,
            category="ameaca_ou_extorsao" if is_threat else "benigno",
            model=data.get("model", self.model),
            detail=f"Decisão Ollaya: choice={choice}, confidence={confidence:.4f}, threat_prob={threat_prob:.4f}",
        )

