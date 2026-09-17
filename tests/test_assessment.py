import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from will_it_scale.assessment import AssessmentService


class FakeAgent:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, object | None, bool]] = []
        self.session = object()

    def create_session(self) -> object:
        return self.session

    def run(self, message: str, *, session=None, stream: bool = False):
        self.calls.append((message, session, stream))
        if stream:
            return self._stream_response()
        return self._response()

    async def _response(self):
        return SimpleNamespace(text=self.responses.pop(0))

    async def _stream_response(self):
        for response in self.responses:
            yield SimpleNamespace(text=response)


class AssessmentServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_defaults_target_scale_street(self) -> None:
        self.assertEqual(
            AssessmentService().manifest_path,
            Path("samples/scale_street/k8s/constrained/deployment.yaml").resolve(),
        )
        self.assertEqual(
            AssessmentService().application_source_path,
            Path("samples/scale_street/src/scale_street/main.py").resolve(),
        )

    async def test_requirements_drive_investigation_report_and_follow_up(self) -> None:
        kubernetes_agent = FakeAgent(["Investigator findings"])
        application_agent = FakeAgent(["Application findings"])
        architect = FakeAgent(["Short ", "report"])
        statuses: list[str] = []

        def create_kubernetes_agent(_, on_file_read):
            on_file_read("deployment.yaml")
            return kubernetes_agent

        def create_application_agent(_, on_file_read):
            on_file_read("app.py")
            return application_agent

        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "deployment.yaml"
            application_source = Path(directory) / "app.py"
            manifest.write_text("kind: Deployment", encoding="utf-8")
            application_source.write_text("def list_orders(): pass", encoding="utf-8")
            service = AssessmentService(
                manifest_path=manifest,
                application_source_path=application_source,
                kubernetes_agent_factory=create_kubernetes_agent,
                application_performance_agent_factory=create_application_agent,
                architect_agent_factory=lambda: architect,
            )

            report = "".join(
                [
                    chunk
                    async for chunk in service.stream_report(
                        "250 RPS, 99.9% availability", statuses.append
                    )
                ]
            )
            architect.responses = ["First ", "second."]
            follow_up = "".join(
                [chunk async for chunk in service.stream_follow_up("What next?")]
            )

        self.assertEqual(report, "Short report")
        self.assertEqual(follow_up, "First second.")
        self.assertIn("read_manifest_file tool", kubernetes_agent.calls[0][0])
        self.assertIn("read_source_file tool", application_agent.calls[0][0])
        self.assertIn("missing timeouts or retries", application_agent.calls[0][0])
        self.assertIn("250 RPS, 99.9% availability", architect.calls[0][0])
        self.assertIn("Investigator findings", architect.calls[0][0])
        self.assertIn("Application findings", architect.calls[0][0])
        self.assertIn("Read application source: app.py", statuses)
        self.assertIn("Read Kubernetes manifest: deployment.yaml", statuses)
        self.assertEqual(architect.calls[0][1:], (architect.session, True))
        self.assertEqual(architect.calls[1], ("What next?", architect.session, True))


if __name__ == "__main__":
    unittest.main()