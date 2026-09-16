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
    async def test_follow_up_reuses_architect_session(self) -> None:
        kubernetes_agent = FakeAgent(["Investigator findings"])
        architect = FakeAgent(["Short report"])

        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "deployment.yaml"
            manifest.write_text("kind: Deployment", encoding="utf-8")
            service = AssessmentService(
                manifest_path=manifest,
                kubernetes_agent_factory=lambda: kubernetes_agent,
                architect_agent_factory=lambda: architect,
            )

            report = await service.investigate()
            architect.responses = ["First ", "second."]
            follow_up = "".join(
                [chunk async for chunk in service.stream_follow_up("What next?")]
            )

        self.assertEqual(report, "Short report")
        self.assertEqual(follow_up, "First second.")
        self.assertEqual(architect.calls[0][1], architect.session)
        self.assertEqual(architect.calls[1], ("What next?", architect.session, True))


if __name__ == "__main__":
    unittest.main()