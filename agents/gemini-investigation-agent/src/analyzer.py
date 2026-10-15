import json
import logging
import os
from typing import Optional, List, Dict, Any
from common.config.settings import settings
from common.schemas.threat import (
    GeminiThreatAnalysis,
    GeneratedBenchmarkDataset,
    GeneratedBenchmarkMessage,
)

logger = logging.getLogger("gemini-agent.analyzer")


class GeminiThreatAnalyzer:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        use_mock: Optional[bool] = None,
        **kwargs,
    ):
        self.use_mock = settings.MOCK_GEMINI if use_mock is None else use_mock
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self._client = None
        if not self.use_mock:
            self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.warning("GEMINI_API_KEY não configurada. Investigação semântica operará em modo BYPASS.")
            return

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Cliente Google GenAI inicializado com sucesso para o modelo {self.model_name}.")
        except Exception as e:
            logger.warning(f"Não foi possível inicializar google.genai ({e}). Investigação operará em modo BYPASS.")
            self._client = None

    async def analyze(self, message: str) -> GeminiThreatAnalysis:
        """Executa a investigação semântica via API do Google Gemini.
        Se a API falhar, não estiver configurada ou credenciais forem inválidas,
        aciona estritamente o modo BYPASS (sem fallback heurístico).
        """
        if not message or not message.strip():
            return GeminiThreatAnalysis(
                is_valid_threat=False,
                criticidade="BAIXA",
                categoria="outros",
                resumo_analise="Mensagem vazia ou sem conteúdo semântico relevante.",
                acao_imediata_recomendada=False,
                bypassed=False,
            )

        if self.use_mock or not self._client:
            reason = "GEMINI_API_KEY não configurada ou cliente não autenticado."
            logger.info(f"Investigação semântica em BYPASS: {reason}")
            return GeminiThreatAnalysis(
                is_valid_threat=False,
                criticidade="BAIXA",
                categoria="outros",
                resumo_analise=f"Bypass de IA: Investigação profunda do Gemini ignorada ({reason}).",
                acao_imediata_recomendada=False,
                bypassed=True,
                bypass_reason=reason,
            )

        try:
            return await self._analyze_with_gemini(message)
        except Exception as e:
            reason = f"Erro na API do Google Gemini: {type(e).__name__} ({str(e)[:180]})"
            logger.warning(
                f"Falha ao chamar API real do Google Gemini. Modo BYPASS ativado (sem fallback heurístico): {reason}"
            )
            return GeminiThreatAnalysis(
                is_valid_threat=False,
                criticidade="BAIXA",
                categoria="outros",
                resumo_analise=f"Bypass de IA: Chamada à API do Google Gemini indisponível ({type(e).__name__}). Investigação semântica ignorada.",
                acao_imediata_recomendada=False,
                bypassed=True,
                bypass_reason=reason,
            )

    async def _analyze_with_gemini(self, message: str) -> GeminiThreatAnalysis:
        prompt = (
            "Você é um especialista em análise de ameaças e segurança bancária do Pix Guard. "
            "Avalie detalhadamente a mensagem enviada na transferência Pix a seguir quanto à presença de intimidação, "
            "extorsão, assédio, perseguição física ou violência. "
            "Retorne a análise estritamente estruturada conforme o esquema solicitado.\n\n"
            f'Mensagem sob investigação: "{message}"'
        )

        config = {
            "response_mime_type": "application/json",
            "response_schema": GeminiThreatAnalysis,
        }
        logger.info(f"Chamando API real do Google Gemini ({self.model_name}) para análise semântica...")
        if hasattr(self._client, "aio") and hasattr(self._client.aio, "models"):
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
        else:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
        parsed_json = json.loads(response.text)
        logger.info(
            f"Análise estruturada do Gemini ({self.model_name}) concluída: "
            f"is_threat={parsed_json.get('is_valid_threat')}, "
            f"criticidade={parsed_json.get('criticidade')}, "
            f"categoria={parsed_json.get('categoria')}"
        )
        return GeminiThreatAnalysis(**parsed_json)

    async def generate_test_dataset(self, count: int = 50) -> List[Dict[str, Any]]:
        """Gera um conjunto equilibrado de mensagens sintéticas de Pix para benchmark via Gemini."""
        if self.use_mock or not self._client:
            logger.info("Gerando dataset de benchmark sintético mock (modo sem cliente Gemini).")
            return self._mock_test_dataset(count)

        try:
            return await self._generate_dataset_with_gemini(count)
        except Exception as e:
            logger.error(f"Erro ao gerar mensagens com Gemini: {e}. Usando gerador de emergência.")
            return self._mock_test_dataset(count)

    async def _generate_dataset_with_gemini(self, count: int = 50) -> List[Dict[str, Any]]:
        threat_count = count // 2
        safe_count = count - threat_count
        prompt = (
            f"Você é um auditor sênior de segurança bancária e especialista em crimes cibernéticos no ecossistema Pix do Banco Central do Brasil.\n"
            f"Gere EXATAMENTE {count} mensagens de transferência Pix sintéticas e ultrarrealistas em português do Brasil para avaliar e comparar modelos de IA.\n\n"
            f"Distribuição estrita:\n"
            f"- EXATAMENTE {threat_count} mensagens de AMEAÇA REAL (label='threat'):\n"
            f"  * Violência física direta e ameaça à integridade física;\n"
            f"  * Extorsão financeira e chantagem (fotos íntimas, segredos, ameaça de expor para família);\n"
            f"  * Perseguição e Stalking velado (vigiar academia/trabalho, citar modelo de carro ou rotina);\n"
            f"  * Cobrança hostil com intimidação e agiotagem predatória;\n"
            f"  * Tentativas sutis de evasão com números/leetspeak.\n"
            f"- EXATAMENTE {safe_count} mensagens BENIGNAS / NORMAIS (label='safe'):\n"
            f"  * Pagamentos comuns cotidianos (almoço, café, gasolina, racha de conta);\n"
            f"  * Cobranças educadas comerciais legítimas com prazos e datas (aluguel, condomínio);\n"
            f"  * Mensagens com GÍRIAS COLOQUIAIS ou termos que parecem violentos isoladamente mas são amigáveis ('quase morri de rir', 'vou te matar de cócegas', 'vou quebrar seu recorde no jogo');\n"
            f"  * Mensagens normais familiares e de afeto.\n\n"
            f"Regras:\n"
            f"- O campo 'text' deve ter estilo autêntico de mensagem Pix (10 a 140 caracteres).\n"
            f"- 'label' deve ser estritamente 'threat' ou 'safe'.\n"
            f"- 'category' deve ser uma das seguintes: 'violencia', 'chantagem', 'cobranca_agressiva', 'extorsao_violenta', 'stalking', 'pagamento', 'idioma_violento', 'cobranca_educada', 'neutra'.\n"
            f"- Retorne EXATAMENTE {count} itens no array 'messages'."
        )

        config = {
            "response_mime_type": "application/json",
            "response_schema": GeneratedBenchmarkDataset,
        }

        logger.info(f"Chamando API do Google Gemini ({self.model_name}) para gerar {count} mensagens de benchmark...")
        if hasattr(self._client, "aio") and hasattr(self._client.aio, "models"):
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
        else:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

        parsed = json.loads(response.text)
        raw_msgs = parsed.get("messages", [])
        clean_msgs = []
        for i, m in enumerate(raw_msgs):
            label = "threat" if m.get("label") == "threat" else "safe"
            default_cat = "violencia" if label == "threat" else "pagamento"
            clean_msgs.append({
                "id": m.get("id") or f"gemini-{i+1:02d}",
                "text": m.get("text", "").strip(),
                "label": label,
                "category": m.get("category") or default_cat,
                "explanation": m.get("explanation"),
            })
        logger.info(f"Gemini gerou {len(clean_msgs)} mensagens de benchmark com sucesso.")
        return clean_msgs

    def _mock_test_dataset(self, count: int = 50) -> List[Dict[str, Any]]:
        threat_samples = [
            ("Paga os 800 até amanhã ou todo mundo vai ver aquelas fotos suas", "chantagem"),
            ("Se você contar pra polícia eu acabo com a tua família", "violencia"),
            ("Sei que você tem família aqui perto, seria uma pena se acontecesse algo", "extorsao_violenta"),
            ("Me manda 300 que eu apago a conversa, senão vai pro seu marido", "chantagem"),
            ("Fica esperto, a gente sabe o teu horário de saída da empresa", "stalking"),
            ("Ou você transfere o restante até as 18h ou vamos nos encontrar pessoalmente", "cobranca_agressiva"),
            ("Amanhã na porta da sua casa a gente resolve se você não pagar", "violencia"),
            ("Se não cair na conta em 10 minutos você vai se arrepender amargamente", "extorsao_violenta"),
            ("Vi você saindo da academia com o carro prata, vou te achar nem que seja no fim do mundo", "stalking"),
            ("Vou te quebrar no meio se não devolver meu dinheiro hoje", "violencia"),
            ("Último aviso antes de mandar meus cobradores baterem na sua porta", "cobranca_agressiva"),
            ("V0u t3 p3g4r n4 s41d4 d0 tr4b4lh0 s3 n40 m3 p4g4r h0j3", "violencia"),
            ("Se você me bloquear, vou aparecer na frente dos seus filhos", "stalking"),
            ("Transferência ou seus dados vazam no grupo da empresa hoje", "chantagem"),
            ("Te dou até o meio dia caloteiro sem vergonha, depois não reclame", "cobranca_agressiva"),
            ("Conheço seu trajeto diário, não me faça perder a paciência", "stalking"),
            ("Me paga logo antes que aconteça uma desgraça na tua casa", "extorsao_violenta"),
            ("Você acha que a polícia te protege? Amanhã a gente conversa", "violencia"),
            ("Se não pagar os 2 mil que me deve, vai acordar sem carro", "cobranca_agressiva"),
            ("Tô de olho em você todo santo dia, transfere o combinado", "stalking"),
            ("Ou faz o Pix agora ou seu chefe vai receber prints das suas mensagens", "chantagem"),
            ("Vou te dar um corretivo se essa dívida não for quitada até sexta", "violencia"),
            ("Vou passar aí no seu bairro cobrar na marra", "cobranca_agressiva"),
            ("Melhor me pagar antes que eu resolva do meu jeito", "extorsao_violenta"),
            ("Sei a placa do seu carro novo, não me enrola", "stalking"),
        ]
        safe_samples = [
            ("Pagamento do almoço de ontem, valeu amigo!", "pagamento"),
            ("Amigo, quase morri de rir ontem na festa! Segue a vaquinha", "idioma_violento"),
            ("Pode me transferir o valor do aluguel até o dia 10, por favor?", "cobranca_educada"),
            ("Compra de 2 ingressos para o cinema", "pagamento"),
            ("Gasolina da viagem para o litoral", "pagamento"),
            ("Racha da pizza de ontem à noite, ficou ótimo!", "pagamento"),
            ("Segue a mensalidade do curso de inglês", "cobranca_educada"),
            ("Mano quase te matei de susto kkkk valeu pelo churrasco", "idioma_violento"),
            ("Presente de aniversário da mamãe", "neutra"),
            ("Reembolso do Uber compartilhado", "pagamento"),
            ("Pagamento das compras da farmácia", "pagamento"),
            ("Taxa de condomínio referente a outubro", "cobranca_educada"),
            ("Vou te matar de cócegas quando chegar aí amor!", "idioma_violento"),
            ("Pagamento do conserto da torneira da cozinha", "pagamento"),
            ("Mensalidade da academia deste mês", "cobranca_educada"),
            ("Nosso time amassou o rival ontem! Segue a aposta", "idioma_violento"),
            ("Depósito para o lanche da tarde", "pagamento"),
            ("Pagamento referente à diária de faxina", "pagamento"),
            ("Vou quebrar seu recorde no jogo hoje à noite hein haha", "idioma_violento"),
            ("Contribuição para o presente do professor", "neutra"),
            ("Lembrança para o café da manhã de amanhã", "neutra"),
            ("Compra dos livros do semestre", "pagamento"),
            ("Ficou 45 reais da sua parte do rodízio japonês", "cobranca_educada"),
            ("Transferência para a poupança do bebê", "neutra"),
            ("Valeu pela carona até o aeroporto!", "pagamento"),
        ]
        out: List[Dict[str, Any]] = []
        i = 1
        t_idx = 0
        s_idx = 0
        while len(out) < count:
            if len(out) % 2 == 0:
                text, cat = threat_samples[t_idx % len(threat_samples)]
                t_idx += 1
                label = "threat"
            else:
                text, cat = safe_samples[s_idx % len(safe_samples)]
                s_idx += 1
                label = "safe"
            out.append({
                "id": f"gemini-{i:02d}",
                "text": text,
                "label": label,
                "category": cat,
                "explanation": f"Mensagem sintética {label} ({cat}).",
            })
            i += 1
        return out[:count]

