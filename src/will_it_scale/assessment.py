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
REQUIREMENTS_PROMPT = """Before I investigate, what should this service support?

Please include:
- Target throughput, such as requests or transactions per second
- Latency and availability objectives
- Expected traffic pattern, including bursts or growth"""


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

    async def stream_report(
        self,
        requirements: str,
        on_status: StatusCallback | None = None,
    ) -> AsyncIterator[str]:
        self._set_status(on_status, "Reading Kubernetes configuration")
        manifest = self.manifest_path.read_text(encoding="utf-8")

        self._set_status(on_status, "Investigating scaling and availability risks")
        investigator = self._kubernetes_agent_factory()
        investigation = await investigator.run(
            """
            Investigate the Kubernetes configuration against the user's workload and reliability
            requirements below. Return concise, evidence-backed findings for the Investigation
            Architect. Identify scaling, scheduling, and availability risks, cite the relevant
            manifest fields, and call out any unknowns. Do not claim that configuration alone
            proves the service can handle the requested workload.

            User requirements:
            """
            + requirements
            + """

            Kubernetes manifest:
            """
            + manifest
        )

        self._set_status(on_status, "Preparing the assessment")
        self._architect = self._architect_agent_factory()
        self._session = self._architect.create_session()
        async for update in self._architect.run(
            """
            Compare the Kubernetes investigator's findings with the user's workload and reliability
            requirements below. Identify only the most important confirmed concerns, unknowns, and
            next validation steps. Return a small user-facing report with no more than eight concise
            bullets. Clearly distinguish evidence-backed conclusions from unknowns.

            User requirements:
            """
            + requirements
            + """

            Kubernetes investigator findings:
            """
            + investigation.text,
            stream=True,
            session=self._session,
        ):
            if update.text:
                yield update.text

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