import asyncio
import logging
import time
from typing import Optional, Any, List, Union
import httpx
from common.config.settings import settings
from common.schemas.threat import OllayaClassificationResult

logger = logging.getLogger("gateway.ollaya-client")


# Critérios equilibrados de meio-termo: concisos o suficiente para preservar a velocidade
# da inferência em borda (<35ms), mas com amplitude semântica para cobrir coação e perseguição.
DEFAULT_INSTRUCTIONS = "A mensagem de Pix contém ameaça, chantagem ou perseguição?"

THREAT_CRITERIA = {
    "threat": "ameaça, chantagem ou perseguição",
    "safe": "conversa normal ou amigável",
}

# Probabilidade mínima de "ameaça" para mascarar a mensagem.
THREAT_THRESHOLD = 0.40

# O servidor do Laya retreinado (laya-serve) exige 'instructions'. DEVE ser idêntica à usada no treino
# (finetune/train_laya_pix.py, QUESTIONS), senão o modelo recebe uma pergunta diferente da que aprendeu.
TUNED_INSTRUCTIONS = "A mensagem de Pix contém ameaça, extorsão ou intimidação?"
TUNED_CRITERIA = {
    "threat": "ameaça",
    "safe": "agradecimento ou conversa normal",
}


class OllayaClient:
    def __init__(
        self,
        base_url: str = settings.OLLAYA_BASE_URL,
        base_urls: Optional[Any] = None,
        model: str = settings.OLLAYA_MODEL,
        timeout: float = settings.OLLAYA_TIMEOUT_SECONDS,
        client: Optional[httpx.AsyncClient] = None,
        instructions: Optional[str] = DEFAULT_INSTRUCTIONS,
        criteria: Optional[dict] = None,
    ):
        self.instructions = instructions
        self.criteria = criteria or THREAT_CRITERIA
        
        # Cluster de instâncias do Ollaya: lista de URLs ou string separada por vírgula
        if base_urls:
            if isinstance(base_urls, str):
                self.base_urls = [u.strip().rstrip("/") for u in base_urls.split(",") if u.strip()]
            else:
                self.base_urls = [str(u).rstrip("/") for u in base_urls if u]
        else:
            self.base_urls = [base_url.rstrip("/")]
            
        self.base_url = self.base_urls[0]
        self._rr_index = 0
        self.model = model
        self.timeout = timeout
        self._client = client
        # Saúde observada: o gateway aprova o Pix quando a IA falha, então a falha precisa ficar visível.
        self.consecutive_failures = 0
        self.last_error: Optional[str] = None
        self.last_ok_at: Optional[float] = None

    def _next_url(self) -> str:
        """Seleciona a próxima réplica do cluster via Round-Robin."""
        if len(self.base_urls) == 1:
            return self.base_urls[0]
        idx = self._rr_index
        self._rr_index = (idx + 1) % len(self.base_urls)
        return self.base_urls[idx]

    def _record_ok(self) -> None:
        self.consecutive_failures = 0
        self.last_error = None
        self.last_ok_at = time.time()

    def _record_failure(self, detail: str) -> None:
        self.consecutive_failures += 1
        self.last_error = detail

    @staticmethod
    def _describe(ex: Exception) -> str:
        """Texto curto e acionável. Inclui o corpo da resposta (ex.: MODEL_NOT_FOUND) quando houver."""
        if isinstance(ex, httpx.HTTPStatusError):
            body = ex.response.text[:200].strip()
            return f"HTTP {ex.response.status_code}: {body}" if body else f"HTTP {ex.response.status_code}"
        return f"{type(ex).__name__}: {ex}"

    def status(self) -> dict:
        age = None if self.last_ok_at is None else round(time.time() - self.last_ok_at, 1)
        if self.consecutive_failures > 0:
            state = "degraded"
        elif self.last_ok_at is None:
            state = "unknown"
        else:
            state = "ok"
        return {
            "status": state,
            "model": self.model,
            "cluster_size": len(self.base_urls),
            "cluster_nodes": self.base_urls,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
            "seconds_since_last_ok": age,
        }

    def _get_client(self) -> httpx.AsyncClient:
        """Cliente HTTP compartilhado (keep-alive), criado sob demanda dentro do event loop."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=4.0),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "pix-gateway-service/1.0 (ollaya-client)",
                },
                limits=httpx.Limits(max_keepalive_connections=40, keepalive_expiry=60.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _payload(self, text: str) -> dict:
        # Contrato TypeSafe /v1/systemone do Ollaya
        # Trava comprimento máximo (max_seq_length = 64): mensagens de Pix têm limite regulatório de 140 chars
        safe_text = (text or "").strip()[:200]
        question = {"type": "choice", "criteria": self.criteria}
        if self.instructions:
            question = {"type": "choice", "instructions": self.instructions, "criteria": self.criteria}
        return {"model": self.model, "state": safe_text, "questions": {"threat": question}}

    async def is_available(self) -> bool:
        """Verifica se o modelo está registrado no Ollaya consultando /v1/models (leve, sem carregar pesos)."""
        client = self._get_client()
        for base_url in self.base_urls:
            try:
                resp = await client.get(f"{base_url}/v1/models", timeout=4.0)
                if resp.status_code == 200:
                    models = [m.get("name") for m in resp.json().get("models", [])]
                    if self.model in models:
                        return True
            except Exception:
                continue
        return False

    async def warmup(self, timeout: float = 60.0) -> float:
        """Aquece todas as réplicas do cluster Ollaya em paralelo."""
        t0 = time.perf_counter()
        client = self._get_client()

        async def _warm_one(base_url: str):
            resp = await client.post(
                f"{base_url}/v1/systemone",
                json=self._payload("oi"),
                timeout=httpx.Timeout(timeout, connect=4.0),
            )
            resp.raise_for_status()

        try:
            await asyncio.gather(*(_warm_one(u) for u in self.base_urls))
        except Exception as ex:
            self._record_failure(self._describe(ex))
            raise
        self._record_ok()
        return round((time.perf_counter() - t0) * 1000, 1)

    async def classify(self, text: str) -> OllayaClassificationResult:
        """Classifica a mensagem síncronamente via API TypeSafe do Ollaya (ollaya.dev) com Round-Robin e Failover."""
        if not text or not text.strip():
            return OllayaClassificationResult(
                is_threat=False,
                score=0.0,
                category=None,
                model=self.model,
                detail="Mensagem vazia ou sem texto",
            )

        attempts = len(self.base_urls)
        data = None
        used_url = None

        for attempt in range(attempts):
            base_url = self._next_url()
            used_url = base_url
            url = f"{base_url}/v1/systemone"
            try:
                resp = await self._get_client().post(url, json=self._payload(text))
                resp.raise_for_status()
                data = resp.json()
                self._record_ok()
                break
            except httpx.TimeoutException as te:
                self._record_failure(self._describe(te))
                logger.warning(f"Timeout ao consultar réplica Ollaya ({url}) na tentativa {attempt + 1}/{attempts}: {te}")
                if attempt == attempts - 1:
                    raise RuntimeError(f"Ollaya API indisponível (Timeout): {te}") from te
            except Exception as ex:
                self._record_failure(self._describe(ex))
                logger.warning(f"Erro ao comunicar com réplica Ollaya ({url}) na tentativa {attempt + 1}/{attempts}: {self._describe(ex)}")
                if attempt == attempts - 1:
                    raise RuntimeError(f"Erro na API do Ollaya: {self._describe(ex)}") from ex

        answers = data.get("answers", {})
        threat_ans = answers.get("threat", {})
        choice = threat_ans.get("choice", "safe")
        confidence = float(threat_ans.get("confidence", 0.0))
        probs = threat_ans.get("probabilities", {})
        threat_prob = float(probs.get("threat", confidence if choice == "threat" else 0.0))

        is_threat = (choice == "threat") or (threat_prob >= THREAT_THRESHOLD)

        return OllayaClassificationResult(
            is_threat=is_threat,
            score=threat_prob,
            category="ameaca_ou_extorsao" if is_threat else "benigno",
            model=data.get("model", self.model),
            detail=f"Decisão Ollaya: choice={choice}, confidence={confidence:.4f}, threat_prob={threat_prob:.4f}",
        )
