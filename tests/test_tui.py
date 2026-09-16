import asyncio
import unittest
from unittest.mock import AsyncMock, PropertyMock, patch

from textual.drivers.headless_driver import HeadlessDriver

from will_it_scale.tui import ConversationMessage, WillItScaleApp


class FakeAssessmentService:
    def __init__(self) -> None:
        self.follow_ups: list[str] = []

    async def investigate(self, on_status=None) -> str:
        if on_status is not None:
            on_status("Preparing the assessment")
        return "- Initial finding"

    async def stream_follow_up(self, message: str):
        self.follow_ups.append(message)
        yield "First "
        await asyncio.sleep(0)
        yield "second."


class WillItScaleAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_inline_investigation_has_visible_layout(self) -> None:
        for size in ((60, 20), (120, 40)):
            with self.subTest(size=size):
                service = AsyncMock()
                service.investigate.return_value = "- Initial finding"
                app = WillItScaleApp(service=service)
                with patch.object(
                    HeadlessDriver, "is_inline", new_callable=PropertyMock,
                    return_value=True,
                ):
                    async with app.run_test(size=size) as pilot:
                        await pilot.pause()
                        await self.wait_until_ready(app)
                        self.assertTrue(app.is_inline)
                        for selector in ("#brand", "#prompt", "#status", "#hint"):
                            region = app.query_one(selector).region
                            self.assertGreater(region.width, 0, selector)
                            self.assertGreater(region.height, 0, selector)
                            self.assertTrue(
                                app.screen.region.contains_region(region), selector
                            )
                        service.investigate.assert_awaited_once()

    async def test_initial_investigation_starts_after_first_render(self) -> None:
        events: list[str] = []
        started = asyncio.Event()

        class RenderCheckingService(FakeAssessmentService):
            async def investigate(self, on_status=None) -> str:
                events.append("investigate")
                started.set()
                return await super().investigate(on_status)

        app = WillItScaleApp(service=RenderCheckingService())
        display = app._display

        def record_display(screen, renderable) -> None:
            display(screen, renderable)
            events.append("render")

        with patch.object(app, "_display", side_effect=record_display):
            async with app.run_test(size=(100, 30)):
                await asyncio.wait_for(started.wait(), timeout=5)
                await self.wait_until_ready(app)

        self.assertLess(events.index("render"), events.index("investigate"))
        self.assertEqual(events.count("investigate"), 1)

    async def wait_until_ready(self, app: WillItScaleApp) -> None:
        for _ in range(100):
            if not app._busy:
                return
            await asyncio.sleep(0.01)
        self.fail("TUI worker did not finish")

    async def test_initial_report_and_streamed_follow_up(self) -> None:
        service = FakeAssessmentService()
        app = WillItScaleApp(service=service)

        async with app.run_test(size=(100, 30)) as pilot:
            await self.wait_until_ready(app)
            messages = list(app.query(ConversationMessage))
            self.assertIn("Initial finding", messages[0].content)

            await pilot.click("#prompt")
            await pilot.press(*"What next?", "enter")
            await self.wait_until_ready(app)

            messages = list(app.query(ConversationMessage))
            self.assertEqual(service.follow_ups, ["What next?"])
            self.assertEqual([message.content for message in messages].count("What next?"), 1)
            self.assertEqual(
                [message.content for message in messages].count("First second."), 1
            )

    async def test_slash_commands(self) -> None:
        app = WillItScaleApp(service=FakeAssessmentService())

        async with app.run_test(size=(100, 30)) as pilot:
            await self.wait_until_ready(app)
            await pilot.click("#prompt")
            await pilot.press(*"/help", "enter")
            await pilot.pause()
            help_message = list(app.query(ConversationMessage))[-1]
            self.assertIn("`/clear` clears the transcript", help_message.content)

            await pilot.press(*"/clear", "enter")
            await pilot.pause()
            self.assertEqual(len(app.query(ConversationMessage)), 0)

    async def test_failed_investigation_can_be_retried(self) -> None:
        class FailsOnceService(FakeAssessmentService):
            def __init__(self) -> None:
                super().__init__()
                self.attempts = 0

            async def investigate(self, on_status=None) -> str:
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("temporary failure")
                return await super().investigate(on_status)

        service = FailsOnceService()
        app = WillItScaleApp(service=service)

        async with app.run_test(size=(100, 30)) as pilot:
            await self.wait_until_ready(app)
            self.assertFalse(app._conversation_ready)

            await pilot.click("#prompt")
            await pilot.press(*"/retry", "enter")
            await self.wait_until_ready(app)

            self.assertEqual(service.attempts, 2)
            self.assertTrue(app._conversation_ready)


if __name__ == "__main__":
    unittest.main()