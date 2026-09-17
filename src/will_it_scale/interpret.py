"""LLM interpretation layer (Azure AI Foundry).

The deterministic checks are the source of truth. This layer only *interprets*
them: it prioritizes, groups, and explains. The model is constrained to reference
only the finding ids it is given, so it cannot invent facts about the deployment.
"""

from __future__ import annotations

import json
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from .checks import Finding

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"

SYSTEM_PROMPT = """You are a read-only deployment assessment reviewer.
You receive deterministic findings about a Kubernetes deployment as JSON.

Rules:
- Use ONLY the provided findings as evidence. Never invent resources, metrics, or facts.
- Every statement must reference finding ids from the input.
- You prioritize and explain. You never recommend deploying changes automatically.

Return a JSON object with exactly these keys:
  executive_summary: string (2-4 sentences),
  top_risks: array of objects { finding_ids: string[], theme: string, why_it_matters: string, priority: "high"|"medium"|"low" },
  themes: array of objects { name: string, finding_ids: string[] }
"""


def _client(endpoint: str, api_version: str) -> AzureOpenAI:
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, COGNITIVE_SCOPE)
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )


def interpret_findings(
    findings: list[Finding],
    endpoint: str,
    deployment: str,
    api_version: str = "2024-10-21",
) -> dict[str, Any]:
    """Send findings to the Foundry model and return its parsed interpretation."""
    client = _client(endpoint, api_version)
    payload = {"findings": [f.to_dict() for f in findings]}

    response = client.chat.completions.create(
        model=deployment,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    result = json.loads(content)
    _validate(result, {f.id for f in findings})
    return result


def _validate(result: dict[str, Any], known_ids: set[str]) -> None:
    """Reject interpretations that reference finding ids we did not provide."""
    referenced: set[str] = set()
    for risk in result.get("top_risks", []):
        referenced.update(risk.get("finding_ids", []))
    for theme in result.get("themes", []):
        referenced.update(theme.get("finding_ids", []))

    invented = referenced - known_ids
    if invented:
        raise ValueError(f"Model referenced unknown finding ids: {sorted(invented)}")
