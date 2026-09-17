from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path

from agent_framework import Agent

from will_it_scale.agents.investigation_architect import (
    create_investigation_architect_agent,
)
from will_it_scale.agents.kubernetes_investigator import (
    create_kubernetes_investigator_agent,
)
from will_it_scale.checks import evaluate_workloads
from will_it_scale.collectors.k8s import collect_workloads
from will_it_scale.collectors.manifest import load_workload_facts
from will_it_scale.config import resolve_subscription_id
from will_it_scale.findings_store import (
    latest_previous,
    new_regressions,
    save_findings,
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


@dataclass
class LiveTarget:
    subscription_id: str
    resource_group: str
    cluster: str
    namespace: str


def live_target_from_env() -> LiveTarget | None:
    """A live-cluster target when ASSESS_SOURCE=live, else None (manifest mode)."""
    if os.environ.get("ASSESS_SOURCE", "").lower() != "live":
        return None
    return LiveTarget(
        subscription_id=resolve_subscription_id(),
        resource_group=os.environ.get("TARGET_RG", "deploy-assess-rg"),
        cluster=os.environ.get("TARGET_CLUSTER", "deploy-assess-aks"),
        namespace=os.environ.get("TARGET_NAMESPACE", "default"),
    )


class AssessmentService:
    def __init__(
        self,
        manifest_path: Path = DEFAULT_MANIFEST,
        live_target: LiveTarget | None = None,
        kubernetes_agent_factory: Callable[[], Agent] = (
            create_kubernetes_investigator_agent
        ),
        architect_agent_factory: Callable[[], Agent] = (
            create_investigation_architect_agent
        ),
    ) -> None:
        self.manifest_path = manifest_path
        self.live_target = live_target
        self._kubernetes_agent_factory = kubernetes_agent_factory
        self._architect_agent_factory = architect_agent_factory
        self._architect: Agent | None = None
        self._session = None

    @classmethod
    def from_env(cls) -> "AssessmentService":
        """Build a service, selecting a live-cluster source when ASSESS_SOURCE=live."""
        return cls(live_target=live_target_from_env())

    @classmethod
    def for_live(cls, namespace: str) -> "AssessmentService":
        """Build a service that assesses a live cluster namespace."""
        return cls(
            live_target=LiveTarget(
                subscription_id=resolve_subscription_id(),
                resource_group=os.environ.get("TARGET_RG", "deploy-assess-rg"),
                cluster=os.environ.get("TARGET_CLUSTER", "deploy-assess-aks"),
                namespace=namespace,
            )
        )

    @property
    def source_label(self) -> str:
        """Human-readable description of what this service assesses."""
        if self.live_target is not None:
            t = self.live_target
            return f"live cluster {t.cluster}, namespace {t.namespace}"
        return f"manifest {self.manifest_path.name}"

    async def stream_report(
        self,
        requirements: str,
        on_status: StatusCallback | None = None,
        on_evidence: Callable[[str], None] | None = None,
    ) -> AsyncIterator[str]:
        facts, manifest, source = self._load_evidence(on_status)
        if on_evidence is not None:
            names = ", ".join(d["name"] for d in facts.deployments) or "none found"
            on_evidence(f"{source} - deployments: {names}")

        self._set_status(on_status, "Running deterministic checks")
        findings = evaluate_workloads(facts)
        grounded = json.dumps([f.to_dict() for f in findings], indent=2)
        run_path, regressions = self._persist(findings)

        self._set_status(on_status, "Investigating scaling and availability risks")
        investigator = self._kubernetes_agent_factory()
        manifest_block = (
            "\n\n            Kubernetes manifest:\n            " + manifest
            if manifest is not None
            else ""
        )
        investigation = await investigator.run(
            """
            Investigate the Kubernetes deployment against the user's workload and reliability
            requirements below. Return concise, evidence-backed findings for the Investigation
            Architect. Identify scaling, scheduling, and availability risks, cite the relevant
            fields, and call out any unknowns. Do not claim that configuration alone proves the
            service can handle the requested workload.

            The deterministic findings below come from static analysis of the deployment and are
            authoritative facts (status, evidence, severity, confidence). Treat them as ground
            truth, reconcile them with any manifest, reference their ids, and add reasoning they
            cannot capture -- for example application-level or dependency concerns.

            Evidence source: """
            + source
            + """

            Deterministic findings (JSON):
            """
            + grounded
            + """

            User requirements:
            """
            + requirements
            + manifest_block
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

        yield self._persistence_footer(run_path, regressions)

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

    def _load_evidence(self, on_status: StatusCallback | None):
        """Gather WorkloadFacts from a live cluster or a manifest file.

        Returns (facts, manifest_text_or_None, human_readable_source).
        """
        if self.live_target is not None:
            t = self.live_target
            self._set_status(on_status, f"Collecting live state from {t.cluster}/{t.namespace}")
            facts = collect_workloads(
                t.subscription_id, t.resource_group, t.cluster, t.namespace
            )
            return facts, None, self.source_label

        self._set_status(on_status, "Reading Kubernetes configuration")
        manifest = self.manifest_path.read_text(encoding="utf-8")
        facts = load_workload_facts(self.manifest_path)
        return facts, manifest, self.source_label

    def _persist(self, findings):
        """Save this run's findings and return (path, regressions vs the previous run)."""
        label = self.live_target.cluster if self.live_target else self.manifest_path.stem
        path = save_findings(label, findings)
        previous = latest_previous(label, exclude=path)
        return path, new_regressions(findings, previous)

    @staticmethod
    def _persistence_footer(path, regressions) -> str:
        parts = [f"\n\n---\n_Deterministic findings saved to `{path}`._"]
        if regressions:
            parts.append("\n\n**New regressions since the last run:**\n")
            parts.extend(f"- `{f.id}` - {f.observed}\n" for f in regressions)
        return "".join(parts)