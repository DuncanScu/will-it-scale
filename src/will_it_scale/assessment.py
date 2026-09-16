from collections.abc import AsyncIterator, Callable
from pathlib import Path

from agent_framework import Agent

from will_it_scale.agents.investigation_architect import (
    create_investigation_architect_agent,
)
from will_it_scale.agents.kubernetes_investigator import (
    create_kubernetes_investigator_agent,
)

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "test_data/sample_service/kubernetes/deployment.yaml"
)
StatusCallback = Callable[[str], None]


class AssessmentService:
    def __init__(
        self,
        manifest_path: Path = DEFAULT_MANIFEST,
        kubernetes_agent_factory: Callable[[], Agent] = (
            create_kubernetes_investigator_agent
        ),
        architect_agent_factory: Callable[[], Agent] = (
            create_investigation_architect_agent
        ),
    ) -> None:
        self.manifest_path = manifest_path
        self._kubernetes_agent_factory = kubernetes_agent_factory
        self._architect_agent_factory = architect_agent_factory
        self._architect: Agent | None = None
        self._session = None

    async def investigate(self, on_status: StatusCallback | None = None) -> str:
        self._set_status(on_status, "Reading Kubernetes configuration")
        manifest = self.manifest_path.read_text(encoding="utf-8")

        self._set_status(on_status, "Investigating scaling and availability risks")
        investigator = self._kubernetes_agent_factory()
        investigation = await investigator.run(
            """
            Investigate the Kubernetes configuration below for an order service that must support
            100 requests per second. Return concise, evidence-backed findings for the Investigation
            Architect. Identify scaling, scheduling, and availability risks, cite the relevant
            manifest fields, and call out any unknowns.

            Kubernetes manifest:
            """
            + manifest
        )

        self._set_status(on_status, "Preparing the assessment")
        self._architect = self._architect_agent_factory()
        self._session = self._architect.create_session()
        review = await self._architect.run(
            """
            Review the Kubernetes investigator's findings below for the order service assessment.
            The primary concern is whether the service can support 100 requests per second. Identify
            only the most important confirmed concerns, unknowns, and next validation steps. Return
            a small user-facing report with no more than eight concise bullets. Explain which
            conclusions are supported by the investigator's evidence.

            Kubernetes investigator findings:
            """
            + investigation.text,
            session=self._session,
        )
        return review.text

    async def stream_follow_up(self, message: str) -> AsyncIterator[str]:
        if self._architect is None or self._session is None:
            raise RuntimeError("The initial assessment has not completed")

        async for update in self._architect.run(
            message,
            stream=True,
            session=self._session,
        ):
            if update.text:
                yield update.text

    @staticmethod
    def _set_status(callback: StatusCallback | None, status: str) -> None:
        if callback is not None:
            callback(status)