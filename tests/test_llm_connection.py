import json
import os
import unittest
from unittest.mock import Mock, patch

import httpx
from azure.core.exceptions import AzureError
from openai import AzureOpenAI, OpenAI, OpenAIError
from pydantic import ValidationError

from app.llm import classification_schema, classify_row
from app.llm_connection import llm_connection


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True)
        dotenv = patch("app.llm_connection.load_dotenv")
        environment.start()
        dotenv.start()
        self.addCleanup(environment.stop)
        self.addCleanup(dotenv.stop)
        self.requests = []

    def client_factory(self, client_type):
        def respond(request):
            self.requests.append(request)
            return httpx.Response(200, json={
                "id": "test", "object": "chat.completion", "created": 0, "model": "test",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": "ok"}}],
            })

        def create(**settings):
            return client_type(http_client=httpx.Client(transport=httpx.MockTransport(respond)), **settings)
        return create

    def configure_azure(self):
        os.environ.update({
            "LLM_PROVIDER": "azure",
            "AZURE_TENANT_ID": "test-tenant",
            "AZURE_CLIENT_ID": "test-client",
            "AZURE_CLIENT_SECRET": "test-secret",
            "AZURE_OPENAI_TOKEN_SCOPE": "https://cognitiveservices.azure.com/.default",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_API_VERSION": "2024-10-21",
            "AZURE_OPENAI_DEPLOYMENT": "custom-deployment",
        })

    def test_openai_default_sends_api_key_and_closes_client(self):
        with patch("app.llm_connection.OpenAI", side_effect=self.client_factory(OpenAI)):
            with llm_connection() as (client, model):
                self.assertEqual(model, "gpt-4.1-mini")
                client.chat.completions.create(model=model, messages=[])
            self.assertTrue(client.is_closed())
        self.assertEqual(self.requests[0].url.host, "api.openai.com")
        self.assertEqual(self.requests[0].headers["authorization"], "Bearer test-key")

    def test_azure_uses_deployment_and_token_provider_on_each_request(self):
        self.configure_azure()
        token_provider = Mock(side_effect=["test-token-one", "test-token-two"])
        with patch("app.llm_connection.EnvironmentCredential") as credential_factory:
            with patch("app.llm_connection.get_bearer_token_provider", return_value=token_provider) as provider_factory:
                with patch("app.llm_connection.AzureOpenAI", side_effect=self.client_factory(AzureOpenAI)):
                    with llm_connection() as (client, model):
                        self.assertEqual(model, "custom-deployment")
                        for _ in range(2):
                            client.chat.completions.create(model=model, messages=[])
                    self.assertTrue(client.is_closed())
            credential_factory.return_value.__exit__.assert_called_once()
            provider_factory.assert_called_once_with(
                credential_factory.return_value.__enter__.return_value,
                os.environ["AZURE_OPENAI_TOKEN_SCOPE"],
            )
        self.assertEqual([r.headers["authorization"] for r in self.requests],
                         ["Bearer test-token-one", "Bearer test-token-two"])
        self.assertTrue(all("api-key" not in r.headers for r in self.requests))
        self.assertEqual(self.requests[0].url.path, "/openai/deployments/custom-deployment/chat/completions")
        self.assertEqual(self.requests[0].url.params["api-version"], "2024-10-21")

    def test_incomplete_azure_settings_do_not_fall_back_to_openai(self):
        self.configure_azure()
        del os.environ["AZURE_CLIENT_SECRET"]
        with self.assertRaisesRegex(ValueError, "AZURE_CLIENT_SECRET"):
            with llm_connection():
                self.fail("Incomplete settings should not create a connection.")
        self.assertEqual(self.requests, [])

    def test_unknown_provider_is_rejected(self):
        os.environ["LLM_PROVIDER"] = "wrong-provider"
        with self.assertRaisesRegex(ValueError, "openai or azure"):
            with llm_connection():
                self.fail("Unknown provider should not create a connection.")

    def test_azure_auth_failure_is_sanitized_and_resources_close(self):
        self.configure_azure()
        with patch("app.llm_connection.EnvironmentCredential") as credential_factory:
            with patch("app.llm_connection.get_bearer_token_provider",
                       return_value=Mock(side_effect=AzureError("sensitive-provider-detail"))):
                with patch("app.llm_connection.AzureOpenAI", side_effect=self.client_factory(AzureOpenAI)):
                    with self.assertRaises(OpenAIError) as error:
                        with llm_connection() as (client, model):
                            client.chat.completions.create(model=model, messages=[])
                    self.assertTrue(client.is_closed())
            credential_factory.return_value.__exit__.assert_called_once()
        self.assertNotIn("sensitive-provider-detail", str(error.exception))
        self.assertEqual(self.requests, [])


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.result = {
            "classification": "HSBC",
            "key_root_cause": "An HSBC firewall change blocked traffic.",
            "decision_rationale": "The recorded firewall change caused the incident.",
            "supporting_evidence": [{"column": "PROBLEM_ROOT_CAUSE", "quote": "HSBC firewall change"}],
            "llm_confidence": 90,
            "uncertainty_reason": None,
        }
        self.fields = [{"name": "PROBLEM_ROOT_CAUSE", "description": "Recorded cause.",
                        "value": "An HSBC firewall change blocked traffic."}]

    def client_with_response(self, result, finish_reason="stop"):
        client = Mock()
        message = Mock(content=json.dumps(result), refusal=None)
        client.chat.completions.create.return_value = Mock(
            choices=[Mock(finish_reason=finish_reason, message=message)]
        )
        return client

    def test_shared_chat_call_preserves_structured_output_and_evidence(self):
        client = self.client_with_response(self.result)
        result = classify_row(client, "deployment", self.fields, "Classify this incident.")
        self.assertEqual(result.classification, "HSBC")
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "deployment")
        self.assertTrue(request["response_format"]["json_schema"]["strict"])
        self.assertEqual(json.loads(request["messages"][1]["content"]), self.fields)
        self.assertFalse(request["store"])

    def test_portable_schema_keeps_local_validation(self):
        schema = classification_schema()
        encoded = json.dumps(schema)
        for keyword in ("minLength", "maxItems", "minimum", "maximum"):
            self.assertNotIn('"' + keyword + '"', encoded)
        for update in ({"llm_confidence": 101}, {"decision_rationale": ""},
                       {"supporting_evidence": self.result["supporting_evidence"] * 6}):
            with self.subTest(update=update):
                client = self.client_with_response(self.result | update)
                with self.assertRaises(ValidationError):
                    classify_row(client, "deployment", self.fields, "Classify.")

    def test_temperature_from_environment_including_zero(self):
        for configured, expected in (("0", 0.0), ("0.2", 0.2), ("2", 2.0)):
            with self.subTest(temperature=configured):
                with patch.dict(os.environ, {"LLM_TEMPERATURE": configured}):
                    client = self.client_with_response(self.result)
                    classify_row(client, "deployment", self.fields, "Classify.")
                    self.assertEqual(client.chat.completions.create.call_args.kwargs["temperature"], expected)

    def test_unset_or_blank_temperature_keeps_service_default(self):
        for environment in ({}, {"LLM_TEMPERATURE": "  "}):
            with self.subTest(environment=environment):
                with patch.dict(os.environ, environment, clear=True):
                    client = self.client_with_response(self.result)
                    classify_row(client, "deployment", self.fields, "Classify.")
                    self.assertNotIn("temperature", client.chat.completions.create.call_args.kwargs)

    def test_invalid_temperature_is_rejected_before_request(self):
        for configured in ("wrong", "-0.1", "2.1", "nan", "inf"):
            with self.subTest(temperature=configured):
                with patch.dict(os.environ, {"LLM_TEMPERATURE": configured}):
                    client = self.client_with_response(self.result)
                    with self.assertRaises(ValueError):
                        classify_row(client, "deployment", self.fields, "Classify.")
                    client.chat.completions.create.assert_not_called()

    def test_truncated_output_or_fabricated_evidence_is_rejected(self):
        client = self.client_with_response(self.result, finish_reason="length")
        self.assertIsNone(classify_row(client, "deployment", self.fields, "Classify."))
        self.result["supporting_evidence"][0]["quote"] = "invented cause"
        client = self.client_with_response(self.result)
        self.assertIsNone(classify_row(client, "deployment", self.fields, "Classify."))


if __name__ == "__main__":
    unittest.main()
