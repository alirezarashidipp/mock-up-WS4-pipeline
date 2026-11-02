import json
import os
from contextlib import contextmanager
from pathlib import Path

import tiktoken
from azure.core.exceptions import AzureError
from azure.identity import EnvironmentCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import AzureOpenAI, OpenAI, OpenAIError


def read_token_limit(name, default):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        print(f"Check {name}: use a positive integer.")
        raise ValueError(f"{name} must be a positive integer.") from None
    if value < 1:
        print(f"Check {name}: use a positive integer.")
        raise ValueError(f"{name} must be a positive integer.")
    return value


def estimate_input_tokens(model, messages, response_format):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Azure deployment names may not identify their underlying tokenizer.
        encoding = tiktoken.get_encoding("o200k_base")
    request_input = {"messages": messages, "response_format": response_format}
    text = json.dumps(request_input, ensure_ascii=False)
    # Provider framing can differ; this is a local estimate, not billed usage.
    return len(encoding.encode(text, disallowed_special=()))


def request_options(model, messages, response_format):
    max_input = read_token_limit("LLM_MAX_INPUT_TOKENS", 32000)
    max_output = read_token_limit("LLM_MAX_OUTPUT_TOKENS", 2000)
    input_tokens = estimate_input_tokens(model, messages, response_format)
    if input_tokens > max_input:
        print(f"Request not sent: estimated input {input_tokens} tokens exceeds LLM_MAX_INPUT_TOKENS={max_input}.")
        raise ValueError(f"Estimated input of {input_tokens} tokens exceeds LLM_MAX_INPUT_TOKENS={max_input}.")
    options = {"max_completion_tokens": max_output}
    temperature = os.getenv("LLM_TEMPERATURE", "").strip()
    if temperature:
        options["temperature"] = float(temperature)
    return options


@contextmanager
def llm_connection():
    """Yield a client and model name, then close the connection resources."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider not in ("openai", "azure"):
        raise ValueError("LLM_PROVIDER must be openai or azure.")

    required = ["OPENAI_API_KEY"]
    if provider == "azure":
        required = [
            "AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
            "AZURE_OPENAI_TOKEN_SCOPE", "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_DEPLOYMENT",
        ]
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise ValueError("Missing settings: " + ", ".join(missing))

    if provider == "openai":
        model = os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        with OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60, max_retries=1) as client:
            yield client, model
        return

    with EnvironmentCredential() as credential:
        token_provider = get_bearer_token_provider(
            credential, os.environ["AZURE_OPENAI_TOKEN_SCOPE"]
        )

        def azure_token():
            # Keep authentication failures compatible with the pipeline's API error handling.
            try:
                return token_provider()
            except AzureError:
                raise OpenAIError("Azure authentication failed. Check credentials and proxy settings.") from None

        with AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            azure_ad_token_provider=azure_token,
            timeout=60,
            max_retries=1,
        ) as client:
            yield client, os.environ["AZURE_OPENAI_DEPLOYMENT"]
