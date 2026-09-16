import asyncio
import unittest
from unittest.mock import PropertyMock, patch

from textual.drivers.headless_driver import HeadlessDriver

from will_it_scale.tui import BlenderIntro, ConversationMessage, WillItScaleApp


class FakeAssessmentService:
    def __init__(self) -> None:
        self.requirements: list[str] = []
        self.follow_ups: list[str] = []

    async def stream_report(self, requirements: str, on_status=None):
        self.requirements.append(requirements)
        if on_status is not None:
            on_status("Preparing the assessment")
        yield "- Initial "
        await asyncio.sleep(0)
        yield "finding"

    async def stream_follow_up(self, message: str):
        self.follow_ups.append(message)
        yield "First "
        await asyncio.sleep(0)
        yield "second."


class WillItScaleAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_prompt_waits_before_investigation(self) -> None:
        service = FakeAssessmentService()
        app = WillItScaleApp(service=service)

        async with app.run_test(size=(100, 30)) as pilot:
            await self.wait_until_ready(app)
            self.assertEqual(service.requirements, [])
            self.assertIn(
                "Before I investigate", app.query_one(ConversationMessage).content
            )
            await pilot.press("escape")
            await pilot.click("#prompt")
            await pilot.press(*"250 RPS with 99.9% availability", "enter")
            await self.wait_until_ready(app)

        self.assertEqual(service.requirements, ["250 RPS with 99.9% availability"])

    async def test_blender_intro_animates_and_reveals_report(self) -> None:
        for size in ((32, 16), (60, 20), (120, 40)):
            with self.subTest(size=size):
                app = WillItScaleApp(service=FakeAssessmentService())
                async with app.run_test(size=size) as pilot:
                    await self.wait_until_ready(app)
                    intro = app.query_one(BlenderIntro)
                    intro.animation_timer.pause()
                    self.assertTrue(intro.display)
                    first_frame = intro.render().plain
                    self.assertIn("|_________|", first_frame)
                    self.assertEqual(len(first_frame.splitlines()), intro.size.height)
                    self.assertTrue(all(len(line) == intro.size.width for line in first_frame.splitlines()))
                    intro.advance()
                    self.assertNotEqual(first_frame, intro.render().plain)
                    intro.frame = intro.FRAME_COUNT - 1
                    intro.advance()
                    await pilot.pause()
                    self.assertFalse(intro.display)
                    self.assertTrue(app.query_one("#shell").display)
                    self.assertIs(app.focused, app.query_one("#prompt"))

    async def test_splash_automatically_reveals_tui(self) -> None:
        with patch.object(BlenderIntro, "FRAME_COUNT", 3):
            app = WillItScaleApp(service=FakeAssessmentService())
            async with app.run_test(size=(60, 20)) as pilot:
                await pilot.pause(0.4)
                self.assertFalse(app.query_one(BlenderIntro).display)
                self.assertTrue(app.query_one("#shell").display)
                self.assertIs(app.focused, app.query_one("#prompt"))

    async def test_investigation_starts_only_after_requirements(self) -> None:
        started = asyncio.Event()

        class SlowService(FakeAssessmentService):
            async def stream_report(self, requirements: str, on_status=None):
                started.set()
                async for chunk in super().stream_report(requirements, on_status):
                    yield chunk

        app = WillItScaleApp(service=SlowService())
        async with app.run_test(size=(60, 20)) as pilot:
            await self.wait_until_ready(app)
            self.assertFalse(started.is_set())
            await pilot.press("escape")
            await pilot.click("#prompt")
            await pilot.press(*"250 RPS", "enter")
            await asyncio.wait_for(started.wait(), timeout=5)
            await self.wait_until_ready(app)
            self.assertTrue(app._conversation_ready)

    async def test_inline_investigation_has_visible_layout(self) -> None:
        for size in ((60, 20), (120, 40)):
            with self.subTest(size=size):
                service = FakeAssessmentService()
                app = WillItScaleApp(service=service)
                with patch.object(
                    HeadlessDriver, "is_inline", new_callable=PropertyMock,
                    return_value=True,
                ):
                    async with app.run_test(size=size) as pilot:
                        await self.wait_until_ready(app)
                        self.assertTrue(app.is_inline)
                        self.assertEqual(
                            app.query_one(BlenderIntro).region,
                            app.screen.content_region,
                        )
                        await pilot.press("escape")
                        for selector in ("#brand", "#prompt", "#status", "#hint"):
                            region = app.query_one(selector).region
                            self.assertGreater(region.width, 0, selector)
                            self.assertGreater(region.height, 0, selector)
                            self.assertTrue(
                                app.screen.region.contains_region(region), selector
                            )
                        self.assertEqual(service.requirements, [])

    async def test_requirements_prompt_is_shown_after_first_render(self) -> None:
        events: list[str] = []
        app = WillItScaleApp(service=FakeAssessmentService())
        display = app._display

        def record_display(screen, renderable) -> None:
            display(screen, renderable)
            events.append("render")

        with patch.object(app, "_display", side_effect=record_display):
            async with app.run_test(size=(100, 30)):
                await self.wait_until_ready(app)
                events.append("requirements")

        self.assertLess(events.index("render"), events.index("requirements"))

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
            await pilot.press("escape")
            await pilot.click("#prompt")
            await pilot.press(*"250 RPS with 99.9% availability", "enter")
            await self.wait_until_ready(app)

            messages = list(app.query(ConversationMessage))
            self.assertEqual(
                service.requirements, ["250 RPS with 99.9% availability"]
            )
            self.assertIn("Initial finding", messages[-1].content)
            self.assertTrue(app._conversation_ready)

            await pilot.press(*"What next?", "enter")
            await self.wait_until_ready(app)

            messages = list(app.query(ConversationMessage))
            self.assertEqual(service.follow_ups, ["What next?"])
            self.assertEqual([message.content for message in messages].count("What next?"), 1)
            self.assertEqual(
                [message.content for message in messages].count("First second."), 1
            )

    async def test_assessment_title_waits_for_first_report_chunk(self) -> None:
        first_chunk = asyncio.Event()

        class DelayedService(FakeAssessmentService):
            async def stream_report(self, requirements: str, on_status=None):
                await first_chunk.wait()
                async for chunk in super().stream_report(requirements, on_status):
                    yield chunk

        app = WillItScaleApp(service=DelayedService())
        async with app.run_test(size=(100, 30)) as pilot:
            await self.wait_until_ready(app)
            await pilot.press("escape")
            await pilot.click("#prompt")
            await pilot.press(*"250 RPS", "enter")
            await pilot.pause()

            messages = list(app.query(ConversationMessage))
            self.assertEqual(messages[-1].content, "")

            first_chunk.set()
            await self.wait_until_ready(app)
            self.assertIn("Initial finding", messages[-1].content)

    async def test_slash_commands(self) -> None:
        app = WillItScaleApp(service=FakeAssessmentService())

        async with app.run_test(size=(100, 30)) as pilot:
            await self.wait_until_ready(app)
            await pilot.press("escape")
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

            async def stream_report(self, requirements: str, on_status=None):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("temporary failure")
                async for chunk in super().stream_report(requirements, on_status):
                    yield chunk

        service = FailsOnceService()
        app = WillItScaleApp(service=service)

        async with app.run_test(size=(100, 30)) as pilot:
            await self.wait_until_ready(app)
            await pilot.press("escape")
            await pilot.click("#prompt")
            await pilot.press(*"250 RPS", "enter")
            await self.wait_until_ready(app)
            self.assertFalse(app._conversation_ready)

            await pilot.click("#prompt")
            await pilot.press(*"250 RPS", "enter")
            await self.wait_until_ready(app)

            self.assertEqual(service.attempts, 2)
            self.assertTrue(app._conversation_ready)


if __name__ == "__main__":
    unittest.main()