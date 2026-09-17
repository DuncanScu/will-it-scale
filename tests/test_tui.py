import asyncio
import unittest
from unittest.mock import PropertyMock, patch

from textual.drivers.headless_driver import HeadlessDriver

from will_it_scale.tui import (
    BlenderGame, BlenderIntro, ConversationMessage, FallingResource, WillItScaleApp,
)


class FakeAssessmentService:
    def __init__(self) -> None:
        self.requirements: list[str] = []
        self.follow_ups: list[str] = []

    async def stream_report(self, requirements: str, on_status=None):
        self.requirements.append(requirements)
        if on_status is not None:
            on_status("Preparing the assessment")
            on_status("Read Kubernetes manifest: deployment.yaml")
            on_status("Read application source: app.py")
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

    async def test_clicking_shell_focuses_prompt(self) -> None:
        app = WillItScaleApp(service=FakeAssessmentService())
        async with app.run_test(size=(100, 30)) as pilot:
            await self.wait_until_ready(app)
            await pilot.click("#brand")
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
            assistant_messages = [
                message for message in messages if message.role == "Assistant"
            ]
            self.assertIn("Initial finding", assistant_messages[-1].content)
            self.assertTrue(app._conversation_ready)
            self.assertIn(
                "Read Kubernetes manifest: `deployment.yaml`",
                [message.content for message in messages],
            )
            self.assertIn(
                "Read application source: `app.py`",
                [message.content for message in messages],
            )

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
            initial_assistant_count = len(
                [message for message in app.query(ConversationMessage)
                 if message.role == "Assistant"]
            )
            await pilot.press("escape")
            await pilot.click("#prompt")
            await pilot.press(*"250 RPS", "enter")
            await pilot.pause()

            messages = list(app.query(ConversationMessage))
            self.assertEqual(
                len([message for message in messages if message.role == "Assistant"]),
                initial_assistant_count,
            )

            first_chunk.set()
            await self.wait_until_ready(app)
            assistant_messages = [
                message
                for message in app.query(ConversationMessage)
                if message.role == "Assistant"
            ]
            self.assertIn("Initial finding", assistant_messages[-1].content)

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

    async def test_game_command_controls_and_return_to_chat(self) -> None:
        service = FakeAssessmentService()
        app = WillItScaleApp(service=service)
        async with app.run_test(size=(60, 20)) as pilot:
            await self.wait_until_ready(app)
            await pilot.press("escape")
            messages = [message.content for message in app.query(ConversationMessage)]
            await pilot.press(*"/game", "enter")
            game = app.query_one(BlenderGame)
            game.game_timer.pause()
            self.assertTrue(game.display)
            self.assertFalse(app.query_one("#shell").display)
            self.assertIs(app.focused, game)
            self.assertEqual(service.requirements, [])
            self.assertEqual(service.follow_ups, [])
            column = game.blender_column
            await pilot.press("left")
            self.assertEqual(game.blender_column, column - 3)
            await pilot.press("right")
            self.assertEqual(game.blender_column, column)
            await pilot.press("space")
            self.assertTrue(game.paused)
            game.advance()
            await pilot.press("left")
            self.assertEqual(game.blender_column, column)
            await pilot.press("space")
            self.assertFalse(game.paused)
            await pilot.press("escape")
            self.assertFalse(game.display)
            self.assertTrue(app.query_one("#shell").display)
            self.assertIs(app.focused, app.query_one("#prompt"))
            self.assertEqual(messages, [message.content for message in app.query(ConversationMessage)])
            await pilot.press(*"250 RPS", "enter")
            await self.wait_until_ready(app)
            self.assertEqual(service.requirements, ["250 RPS"])
            await pilot.press(*"/game", "enter")
            game.game_timer.pause()
            self.assertTrue(game.display)
            self.assertEqual(game.score, 0)
            self.assertEqual(game.lives, 3)
            await pilot.press("escape")
            score = game.score
            game.advance()
            self.assertEqual(game.score, score)
            self.assertEqual(game.resources, [])
            await pilot.press(*"What next?", "enter")
            await self.wait_until_ready(app)
            self.assertEqual(service.follow_ups, ["What next?"])

    async def test_game_catches_misses_and_restart(self) -> None:
        app = WillItScaleApp(service=FakeAssessmentService())
        async with app.run_test(size=(60, 20)) as pilot:
            await self.wait_until_ready(app)
            await pilot.press("escape")
            await pilot.press(*"/game", "enter")
            game = app.query_one(BlenderGame)
            game.game_timer.pause()
            game.spawn_in = 100
            game.resources = [FallingResource(game.blender_column + 7, game.catch_row - 0.01, "[POD]", "red")]
            game.advance()
            self.assertEqual(game.score, 10)
            self.assertEqual(game.lives, 3)
            self.assertEqual(game.resources, [])
            for lives in (2, 1, 0):
                game.resources = [FallingResource(0, game.catch_row - 0.01, "[POD]", "red")]
                game.advance()
                self.assertEqual(game.lives, lives)
            self.assertIn("GAME OVER", game.render().plain)
            game.advance()
            self.assertEqual(game.lives, 0)
            await pilot.press("r")
            self.assertEqual(game.score, 0)
            self.assertEqual(game.lives, 3)
            self.assertEqual(game.resources, [])

    async def test_game_faster_falls_with_spaced_spawns(self) -> None:
        app = WillItScaleApp(service=FakeAssessmentService())
        async with app.run_test(size=(120, 40)) as pilot:
            await self.wait_until_ready(app)
            await pilot.press("escape")
            await pilot.press(*"/game", "enter")
            game = app.query_one(BlenderGame)
            game.game_timer.pause()
            for score, speed, interval in ((0, 6.0, 2.4), (300, 11.0, 1.8), (1200, 16.0, 1.2)):
                with self.subTest(score=score):
                    game.restart()
                    game.score = score
                    game.advance()
                    resource = game.resources[0]
                    self.assertAlmostEqual(game.spawn_in, interval)
                    row = resource.row
                    game.advance()
                    self.assertAlmostEqual(resource.row - row, speed * game.TICK)
                    for _ in range(18):
                        game.advance()
                    self.assertEqual(len(game.resources), 1)
                    for _ in range(round(interval / game.TICK) - 19 + 1):
                        game.advance()
                    self.assertEqual(len(game.resources), 2)

    async def test_game_inline_layout_resize_and_movement_bounds(self) -> None:
        app = WillItScaleApp(service=FakeAssessmentService())
        with patch.object(HeadlessDriver, "is_inline", new_callable=PropertyMock, return_value=True):
            async with app.run_test(size=(120, 40)) as pilot:
                await self.wait_until_ready(app)
                await pilot.press("escape")
                await pilot.press(*"/game", "enter")
                game = app.query_one(BlenderGame)
                game.game_timer.pause()
                for width, height in ((120, 40), (60, 20), (32, 16), (24, 14)):
                    with self.subTest(size=(width, height)):
                        await pilot.resize_terminal(width, height)
                        self.assertEqual(game.region, app.screen.content_region)
                        self.assertTrue(game.playable)
                        game.blender_column = 0
                        await pilot.press("left")
                        self.assertEqual(game.blender_column, 0)
                        game.blender_column = width - 19
                        await pilot.press("right")
                        self.assertEqual(game.blender_column, width - 19)
                        frame = game.render().plain
                        self.assertIn("|_________|", frame)
                        self.assertEqual(len(frame.splitlines()), game.size.height)
                        self.assertTrue(all(len(line) == game.size.width for line in frame.splitlines()))

                game.resources.clear()
                game.spawn_in = 0
                game.advance()
                self.assertEqual(len(game.resources), 1)
                resource = game.resources[0]
                self.assertIn(resource.label, BlenderIntro.RESOURCES)
                self.assertGreaterEqual(resource.column, 0)
                self.assertLessEqual(resource.column + len(resource.label), game.size.width)
                row = resource.row
                game.advance()
                self.assertGreater(resource.row, row)
                await pilot.press("space")
                row = resource.row
                game.advance()
                self.assertEqual(resource.row, row)
                await pilot.press("space")
                await pilot.resize_terminal(18, 8)
                self.assertFalse(game.playable)
                self.assertIn("Terminal too small", game.render().plain)
                game.advance()
                self.assertEqual(resource.row, row)
                await pilot.resize_terminal(60, 20)
                self.assertTrue(game.playable)
                game.advance()
                self.assertGreater(resource.row, row)
                await pilot.press("escape")
                self.assertIs(app.focused, app.query_one("#prompt"))


if __name__ == "__main__":
    unittest.main()