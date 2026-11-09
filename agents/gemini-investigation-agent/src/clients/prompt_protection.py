from functools import cached_property

from google.api_core import exceptions, retry_async
from google.cloud import dlp_v2, modelarmor_v1

from common.config.settings import settings

DLP_INFO_TYPES = (
    "BRAZIL_CPF_NUMBER",
    "BRAZIL_RG_NUMBER",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD_NUMBER",
    "PERSON_NAME",
    "STREET_ADDRESS",
)
MODEL_ARMOR_TIMEOUT_SECONDS = 5.0
DLP_TIMEOUT_SECONDS = 10.0

TRANSIENT_RETRY = retry_async.AsyncRetry(
    predicate=retry_async.if_exception_type(
        exceptions.ServiceUnavailable, exceptions.InternalServerError
    ),
    initial=0.2,
    maximum=2.0,
    multiplier=2.0,
)


class PromptProtectionError(Exception):
    """Decisão de proteção que impede o envio ao Gemini."""


class PromptProtection:
    @cached_property
    def armor(self) -> modelarmor_v1.ModelArmorAsyncClient:
        return modelarmor_v1.ModelArmorAsyncClient(
            client_options={
                "api_endpoint": f"modelarmor.{settings.MODEL_ARMOR_LOCATION}.rep.googleapis.com",
                "quota_project_id": settings.GOOGLE_CLOUD_PROJECT,
            },
        )

    @cached_property
    def dlp(self) -> dlp_v2.DlpServiceAsyncClient:
        return dlp_v2.DlpServiceAsyncClient(
            client_options={
                "api_endpoint": f"dlp.{settings.DLP_LOCATION}.rep.googleapis.com",
                "quota_project_id": settings.GOOGLE_CLOUD_PROJECT,
            },
        )

    async def screen(self, messages: list[str]) -> None:
        project = settings.GOOGLE_CLOUD_PROJECT
        location = settings.MODEL_ARMOR_LOCATION
        template_id = settings.MODEL_ARMOR_TEMPLATE_ID
        if not (project and location and template_id):
            raise PromptProtectionError("Model Armor sem projeto, região ou template configurado.")

        response = await self.armor.sanitize_user_prompt(
            request={
                "name": f"projects/{project}/locations/{location}/templates/{template_id}",
                "user_prompt_data": {"text": "\n\n".join(messages)},
                "multi_language_detection_metadata": {"enable_multi_language_detection": True},
            },
            retry=TRANSIENT_RETRY,
            timeout=MODEL_ARMOR_TIMEOUT_SECONDS,
        )
        result = response.sanitization_result
        match = modelarmor_v1.FilterMatchState
        injection = result.filter_results.get("pi_and_jailbreak")
        if result.filter_match_state == match.MATCH_FOUND or (
            injection and injection.pi_and_jailbreak_filter_result.match_state == match.MATCH_FOUND
        ):
            raise PromptProtectionError("Model Armor bloqueou o conteúdo da investigação.")

        if (
            result.invocation_result != modelarmor_v1.InvocationResult.SUCCESS
            or result.filter_match_state != match.NO_MATCH_FOUND
            or injection is None
            or injection.pi_and_jailbreak_filter_result.execution_state
            != modelarmor_v1.FilterExecutionState.EXECUTION_SUCCESS
            or injection.pi_and_jailbreak_filter_result.match_state != match.NO_MATCH_FOUND
        ):
            raise PromptProtectionError("Model Armor não concluiu a verificação de prompt injection.")

    async def deidentify(self, messages: list[str]) -> list[str]:
        project = settings.GOOGLE_CLOUD_PROJECT
        location = settings.DLP_LOCATION
        if not (project and location):
            raise PromptProtectionError("Cloud DLP sem projeto ou região configurada.")

        # Uma linha por mensagem mantém a ordem e a separação entre alvo e histórico.
        field = {"name": "message"}
        response = await self.dlp.deidentify_content(
            request={
                "parent": f"projects/{project}/locations/{location}",
                "item": {
                    "table": {
                        "headers": [field],
                        "rows": [{"values": [{"string_value": text}]} for text in messages],
                    },
                },
                "inspect_config": {
                    "info_types": [{"name": name} for name in DLP_INFO_TYPES],
                    "min_likelihood": dlp_v2.Likelihood.POSSIBLE,
                },
                "deidentify_config": {
                    "transformation_error_handling": {"throw_error": {}},
                    "record_transformations": {
                        "field_transformations": [{
                            "fields": [field],
                            "info_type_transformations": {
                                "transformations": [{
                                    "primitive_transformation": {"replace_with_info_type_config": {}},
                                }],
                            },
                        }],
                    },
                },
            },
            retry=TRANSIENT_RETRY,
            timeout=DLP_TIMEOUT_SECONDS,
        )
        table = response.item.table
        if (
            [header.name for header in table.headers] != [field["name"]]
            or len(table.rows) != len(messages)
            or any(len(row.values) != 1 or "string_value" not in row.values[0] for row in table.rows)
        ):
            raise PromptProtectionError("Cloud DLP retornou um resultado incompleto.")
        return [row.values[0].string_value for row in table.rows]

    async def close(self) -> None:
        for name in ("armor", "dlp"):
            client = self.__dict__.pop(name, None)
            if client is not None:
                await client.transport.close()
