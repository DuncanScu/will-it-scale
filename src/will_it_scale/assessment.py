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
            requirements below. Produce a polished, user-facing Markdown assessment that is easy to
            scan in a terminal. Identify the most likely first failure point, the most important
            confirmed or handled concerns, unknowns, and next validation steps. Do not claim that
            the service can handle the workload unless the evidence supports it.

            Use this exact report structure:

            # Scalability Assessment
            **Confidence: HIGH|MEDIUM|LOW - NN/100**

            > **Verdict:** one clear sentence answering whether the target workload is plausible.

            ## Likely First Failure
            One or two sentences naming the component or dependency and why.

            ## Concern Ledger
            Use a compact Markdown table with columns: Concern, Status, Evidence, Confidence.
            Status must be one of CONFIRMED, HANDLED, NEW, UNKNOWN, or NEXT VALIDATION.

            ## Evidence Highlights
            Use no more than five concise bullets. Bold the key signal in each bullet and cite the
            relevant manifest field or source when available.

            ## What To Do Next
            Use no more than three prioritized bullets, including concrete measurements or tests.

            Confidence must be an integer from 0 to 100 and must reflect the completeness,
            consistency, and directness of the evidence, not how certain the wording sounds. Use
            HIGH for 80-100, MEDIUM for 50-79, and LOW for 0-49. Keep the overall report concise.
            Clearly distinguish evidence-backed conclusions from assumptions and unknowns. Use
            Markdown headings, bold labels, tables, and blockquotes for visual hierarchy; do not
            use ANSI escape codes or invent evidence.

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