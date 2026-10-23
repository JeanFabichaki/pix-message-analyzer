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

# Probabilidade mínima padrão para pergunta única (compatível com modelo retreinado)
THREAT_THRESHOLD = 0.40

# Perguntas decompostas para o forward pass no modelo Laya multilingual (mmBERT-base)
DECOMPOSED_QUESTIONS = {
    "ameaca_violencia": {
        "type": "choice",
        "instructions": "A mensagem de Pix contém ameaça de violência física, morte ou agressão?",
        "criteria": {"threat": "ameaça ou agressão física", "safe": "conversa normal"},
    },
    "extorsao_chantagem": {
        "type": "choice",
        "instructions": "A mensagem de Pix contém extorsão, chantagem ou exigência forçada sob ameaça?",
        "criteria": {"threat": "chantagem ou extorsão", "safe": "conversa normal"},
    },
    "coercao_financeira": {
        "type": "choice",
        "instructions": "A mensagem de Pix contém cobrança hostil abusiva, intimidação a familiares ou coerção?",
        "criteria": {"threat": "coerção ou intimidação", "safe": "conversa normal"},
    },
}

# Limiares de decisão calibrados para modelo encoder em borda (Laya multilingual):
# - Corte padrão para modelos compactos: 0.65 (evita falsos alarmes em linguagem coloquial)
THREAT_CUTOFF_THRESHOLD = 0.65
# - Zona cinzenta para transações suspeitas ou de valor mais alto: 0.45 a 0.65
GRAY_ZONE_MIN = 0.45
GRAY_ZONE_MAX = 0.65

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
        decomposed: bool = False,
        threat_threshold: Optional[float] = None,
    ):
        self.decomposed = decomposed
        self.instructions = instructions
        self.criteria = criteria or THREAT_CRITERIA
        self.threat_threshold = (
            threat_threshold
            if threat_threshold is not None
            else (THREAT_CUTOFF_THRESHOLD if decomposed else THREAT_THRESHOLD)
        )
        
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
        if self.decomposed:
            return {"model": self.model, "state": safe_text, "questions": DECOMPOSED_QUESTIONS}

        question = {"type": "choice", "criteria": self.criteria}
        if self.instructions:
            question = {"type": "choice", "instructions": self.instructions, "criteria": self.criteria}
        return {"model": self.model, "state": safe_text, "questions": {"threat": question}}

    async def is_available(self) -> bool:
        """Verifica se o modelo está registrado no Ollaya ou no laya-serve."""
        client = self._get_client()
        for base_url in self.base_urls:
            # 1. Tenta /v1/models (Ollaya C++)
            try:
                resp = await client.get(f"{base_url}/v1/models", timeout=3.0)
                if resp.status_code == 200:
                    models = [m.get("name") for m in resp.json().get("models", [])]
                    if self.model in models:
                        return True
            except Exception:
                pass
            # 2. Tenta /health (laya-serve nativo com MPS/CUDA/CPU)
            try:
                resp = await client.get(f"{base_url}/health", timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json()
                    loaded = data.get("loaded", [])
                    if self.model in loaded or data.get("status") == "ok":
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
                decomposed_scores={},
                in_gray_zone=False,
            )

        attempts = len(self.base_urls)
        data = None
        used_url = None
        req_elapsed_ms = 0.0
        inference_ms = None
        network_ms = 0.0

        for attempt in range(attempts):
            base_url = self._next_url()
            used_url = base_url
            url = f"{base_url}/v1/systemone"
            t_req_start = time.perf_counter()
            try:
                resp = await self._get_client().post(url, json=self._payload(text))
                resp.raise_for_status()
                req_elapsed_ms = round((time.perf_counter() - t_req_start) * 1000, 2)
                data = resp.json()
                self._record_ok()

                # Extrai tempo puro de inferência do container (se provido nos headers)
                resp_headers = getattr(resp, "headers", None) or {}
                raw_inf_ms = resp_headers.get("x-inference-time-ms") if hasattr(resp_headers, "get") else None
                if raw_inf_ms:
                    try:
                        inference_ms = round(float(raw_inf_ms), 2)
                    except Exception:
                        inference_ms = None
                network_ms = round(max(0.0, req_elapsed_ms - (inference_ms or 0.0)), 2)
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

        # 1. Rota de perguntas decompostas no mesmo forward pass
        if self.decomposed and any(k in answers for k in DECOMPOSED_QUESTIONS):
            decomposed_scores = {}
            for q_key in DECOMPOSED_QUESTIONS:
                q_ans = answers.get(q_key, {})
                q_choice = q_ans.get("choice", "safe")
                q_conf = float(q_ans.get("confidence", 0.0))
                q_probs = q_ans.get("probabilities", {})
                q_prob = float(q_probs.get("threat", q_conf if q_choice == "threat" else 0.0))
                decomposed_scores[q_key] = round(q_prob, 4)

            max_key = max(decomposed_scores, key=decomposed_scores.get)
            max_score = decomposed_scores[max_key]

            # Calibração estrita: corte em 0.65; zona cinzenta entre 0.45 e 0.65
            is_threat = max_score >= self.threat_threshold
            in_gray_zone = (GRAY_ZONE_MIN <= max_score < GRAY_ZONE_MAX)

            category_name = max_key if is_threat else ("zona_cinzenta" if in_gray_zone else "benigno")
            logger.info(
                f"⚡ [OLLAYA INFERENCE - DECOMPOSED] URL={used_url} | Total Round-Trip={req_elapsed_ms:.2f}ms | "
                f"Pure Inference={inference_ms}ms | Network Overhead={network_ms:.2f}ms | "
                f"Model={data.get('model', self.model)} | MaxScore={max_score:.4f} ({max_key}) | IsThreat={is_threat}"
            )
            return OllayaClassificationResult(
                is_threat=is_threat,
                score=max_score,
                category=category_name,
                model=data.get("model", self.model),
                detail=(
                    f"Decisão Decomposta: max={max_key} ({max_score:.4f}), "
                    f"cutoff={self.threat_threshold}, gray_zone={in_gray_zone}"
                ),
                decomposed_scores=decomposed_scores,
                in_gray_zone=in_gray_zone,
                inference_ms=inference_ms,
                network_ms=network_ms,
            )

        # 2. Rota de pergunta única (modelo retreinado ou legado)
        threat_ans = answers.get("threat", {})
        choice = threat_ans.get("choice", "safe")
        confidence = float(threat_ans.get("confidence", 0.0))
        probs = threat_ans.get("probabilities", {})
        threat_prob = float(probs.get("threat", confidence if choice == "threat" else 0.0))

        is_threat = (choice == "threat") or (threat_prob >= self.threat_threshold)
        in_gray_zone = (GRAY_ZONE_MIN <= threat_prob < GRAY_ZONE_MAX)

        logger.info(
            f"⚡ [OLLAYA INFERENCE] URL={used_url} | Total Round-Trip={req_elapsed_ms:.2f}ms | "
            f"Pure Inference={inference_ms}ms | Network Overhead={network_ms:.2f}ms | "
            f"Model={data.get('model', self.model)} | ThreatScore={threat_prob:.4f} | Choice={choice} | IsThreat={is_threat}"
        )

        return OllayaClassificationResult(
            is_threat=is_threat,
            score=threat_prob,
            category="ameaca_ou_extorsao" if is_threat else ("zona_cinzenta" if in_gray_zone else "benigno"),
            model=data.get("model", self.model),
            detail=f"Decisão Ollaya: choice={choice}, confidence={confidence:.4f}, threat_prob={threat_prob:.4f}",
            decomposed_scores={"threat": threat_prob},
            in_gray_zone=in_gray_zone,
            inference_ms=inference_ms,
            network_ms=network_ms,
        )
