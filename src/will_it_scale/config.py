"""Azure AI Foundry connection settings.

Defaults target the `deploy-assess-foundry` project in the current (personal)
subscription. Override via environment variables when access to another team's
subscription/project becomes available -- no code change needed.
"""

import os
import subprocess

# AI Foundry project endpoint (…/api/projects/<project>).
FOUNDRY_PROJECT_ENDPOINT = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://deploy-assess-foundry.services.ai.azure.com/api/projects/deploy-assess-project",
)

# Deployed model name used by the investigation agents.
FOUNDRY_MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-4.1")


def resolve_subscription_id() -> str:
    """Target subscription: AZURE_SUBSCRIPTION_ID, else the active az CLI account."""
    sub = os.environ.get("AZURE_SUBSCRIPTION_ID", "").strip()
    if sub:
        return sub
    try:
        result = subprocess.run(
            ["az", "account", "show", "--query", "id", "-o", "tsv"],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        sub = result.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        sub = ""
    if not sub:
        raise RuntimeError(
            "No Azure subscription found. Set AZURE_SUBSCRIPTION_ID or run 'az login'."
        )
    return sub
