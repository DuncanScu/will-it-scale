import asyncio
from pathlib import Path

from will_it_scale.agents.investigation_architect import create_investigation_architect_agent
from will_it_scale.agents.kubernetes_investigator import create_kubernetes_investigator_agent

FIXTURE_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "test_data/sample_service/kubernetes/deployment.yaml"
)


def main() -> None:
    asyncio.run(run_agent())


async def run_agent() -> None:
    kubernetes_investigator = create_kubernetes_investigator_agent()
    manifest = FIXTURE_MANIFEST.read_text(encoding="utf-8")

    investigation = await kubernetes_investigator.run(
        """
        Investigate the Kubernetes configuration below for an order service that must support
        100 requests per second. Return concise, evidence-backed findings for the Investigation
        Architect. Identify scaling, scheduling, and availability risks, cite the relevant
        manifest fields, and call out any unknowns.

        Kubernetes manifest:
        """
        + manifest
    )

    architect = create_investigation_architect_agent()
    review = await architect.run(
        """
        Review the Kubernetes investigator's findings below for the order service assessment.
        The primary concern is whether the service can support 100 requests per second. Identify
        confirmed concerns, handled concerns, new risks, unknowns, contradictions, and the next
        validation steps. Explain which conclusions are supported by the investigator's evidence.

        Kubernetes investigator findings:
        """
        + str(investigation)
    )

    print(f"Investigation Architect: {review}")


if __name__ == "__main__":
    main()