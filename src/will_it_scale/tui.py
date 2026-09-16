import asyncio
from time import monotonic

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Label, LoadingIndicator, Markdown, Static

from will_it_scale.assessment import AssessmentService, REQUIREMENTS_PROMPT


class BlenderIntro(Static):
    FRAME_COUNT = 48
    RESOURCES = ("[POD]", "<SVC>", "{DEPLOY}", "[NODE]", "<INGRESS>", "{HPA}", "[PVC]", "{CONFIG}")
    COLORS = ("#65b5ff", "#72c4ba", "#f0a45d")

    def __init__(self) -> None:
        super().__init__(id="blender-intro")
        self.frame = 0

    def on_mount(self) -> None:
        self.animation_timer = self.set_interval(0.08, self.advance)

    def advance(self) -> None:
        self.frame += 1
        if self.frame >= self.FRAME_COUNT:
            self.finish()
        else:
            self.refresh()

    def finish(self) -> None:
        if not self.display:
            return
        self.animation_timer.stop()
        self.display = False
        self.app.query_one("#shell").remove_class("hidden")
        transcript = self.app.query_one("#transcript", VerticalScroll)
        self.call_after_refresh(transcript.scroll_end, animate=False)
        prompt = self.app.query_one("#prompt", Input)
        if not prompt.disabled:
            self.call_after_refresh(prompt.focus)

    def render(self) -> Text:
        width = max(1, self.size.width)
        height = max(1, self.size.height)
        canvas = [[" " for _ in range(width)] for _ in range(height)]
        styles = [["" for _ in range(width)] for _ in range(height)]

        def draw(column: int, row: int, text: str, style: str) -> None:
            if 0 <= row < height:
                for offset, character in enumerate(text):
                    if 0 <= column + offset < width:
                        canvas[row][column + offset] = character
                        styles[row][column + offset] = style

        center = width // 2
        blender = (
            "   .-----------.   ",
            "   |           |==.",
            "   |           |  |",
            "    \\         /===\u0027",
            "     \\_______/     ",
            "     /=======\\     ",
            "    |   (O)   |    ",
            "    |_________|    ",
        )
        compact = height < 11
        if compact:
            blender = (
                "   |           |==.",
                "   |           |__|",
                "    \\_________/    ",
                "    |   (O)   |    ",
                "    |_________|    ",
            )
        fall_height = max(1, min(8, height - len(blender)))
        top = max(0, (height - fall_height - len(blender)) // 2)
        for row, line in enumerate(blender):
            draw(center - 9, top + fall_height + row, line, "bold #b9b3a9")

        lanes = (0,) if width < 50 else (-1, 0, 1)
        for index, lane in enumerate(lanes):
            tick = self.frame + index * 5
            progress = (tick % 16) / 16
            spread = min(23, max(0, (width - 10) // 2))
            column = center + round(lane * spread * (1 - progress))
            row = top + int(progress * (fall_height + 2))
            resource = self.RESOURCES[(tick // 16 + index * 3) % len(self.RESOURCES)]
            if progress > 0.55 or row >= top + fall_height:
                resource = ("+", "*", "o")[index % 3]
            draw(column - len(resource) // 2, row, resource, self.COLORS[index % 3])

        swirl = ("~ * + ~", "+ ~ * +", "* + ~ *", "~ + * ~")[self.frame % 4]
        draw(center - 3, top + fall_height + (1 if compact else 2), swirl, "bold #65b5ff")
        blade = ("- + -", "\\ | /", "--*--", "/ | \\")[self.frame % 4]
        if not compact:
            draw(center - 2, top + fall_height + 3, blade, "bold #72c4ba")
        draw(center, top + fall_height + (3 if compact else 6), "o" if self.frame % 2 else "O", "bold #f0a45d")

        output = Text(no_wrap=True, overflow="crop")
        for row in range(height):
            for column in range(width):
                output.append(canvas[row][column], style=styles[row][column])
            if row < height - 1:
                output.append("\n")
        return output


class ConversationMessage(Vertical):
    def __init__(self, role: str, content: str = "", *, message_id: str) -> None:
        super().__init__(id=message_id, classes=f"message {role.lower()}")
        self.role = role
        self.content = content

    def compose(self) -> ComposeResult:
        yield Label(self.role, classes="message-role")
        yield Markdown(self.content, classes="message-content")

    async def set_content(self, content: str) -> None:
        self.content = content
        await self.query_one(Markdown).update(content)


class WillItScaleApp(App[None]):
    TITLE = "will it scale"
    SUB_TITLE = "scalability investigator"

    CSS = """
    Screen {
        background: #171717;
        color: #e8e3d8;
    }

    Screen:inline {
        height: 100vh;
    }

    #shell {
        height: 100%;
        margin: 0 1;
    }

    #brand {
        height: 3;
        padding: 1 1 0 1;
        color: #f0a45d;
        text-style: bold;
    }

    #transcript {
        height: 1fr;
        padding: 0 1;
        scrollbar-color: #65615a;
        scrollbar-background: #242321;
    }

    #blender-intro {
        height: 1fr;
        overflow: hidden;
    }

    .message {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
        border-left: tall #4d4a45;
    }

    .message.user {
        border-left: tall #5ba8a0;
        background: #202928;
    }

    .message.assistant {
        border-left: tall #d7894d;
    }

    .message.system {
        border-left: tall #77736c;
        color: #b9b3a9;
    }

    .message-role {
        height: 1;
        color: #8f8a82;
        text-style: bold;
    }

    .message.user .message-role {
        color: #72c4ba;
    }

    .message.assistant .message-role {
        color: #f0a45d;
    }

    .message-content {
        height: auto;
        background: transparent;
        padding: 0;
    }

    #activity {
        height: 2;
        padding: 0 1;
        color: #aaa49a;
    }

    #spinner {
        width: 4;
        height: 1;
        color: #f0a45d;
    }

    #status {
        width: 1fr;
        height: 1;
    }

    #prompt-box {
        height: 3;
        margin: 0 1;
        border: round #77736c;
        background: #22211f;
    }

    #prompt-marker {
        width: 3;
        height: 1;
        margin: 0 0 0 1;
        color: #f0a45d;
        text-style: bold;
        content-align: center middle;
    }

    #prompt {
        width: 1fr;
        height: 1;
        border: none;
        padding: 0;
        background: transparent;
        color: #f5f1e8;
    }

    #prompt:focus {
        border: none;
    }

    #hint {
        height: 1;
        margin: 0 2;
        color: #77736c;
        text-align: right;
    }

    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+l", "clear", "Clear", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, service: AssessmentService | None = None) -> None:
        super().__init__()
        self.service = service or AssessmentService()
        self._started_at = monotonic()
        self._status_text = "Waiting for requirements"
        self._message_number = 0
        self._busy = False
        self._awaiting_requirements = False
        self._conversation_ready = False

    def compose(self) -> ComposeResult:
        yield BlenderIntro()
        with Vertical(id="shell", classes="hidden"):
            yield Static("◆ WILL IT SCALE?", id="brand")
            yield VerticalScroll(id="transcript")
            with Horizontal(id="activity"):
                yield LoadingIndicator(id="spinner")
                yield Static(self._status_text, id="status")
            with Horizontal(id="prompt-box"):
                yield Static(">", id="prompt-marker")
                yield Input(
                    placeholder="Ask about the assessment...",
                    id="prompt",
                    disabled=True,
                )
            yield Static("/help  ·  esc cancel  ·  ctrl+c quit", id="hint")

    def on_mount(self) -> None:
        self.set_interval(1, self._refresh_status)
        self._set_busy(True, "Preparing questions")
        self.call_after_refresh(self.request_requirements)

    def _refresh_status(self) -> None:
        if self._busy:
            elapsed = int(monotonic() - self._started_at)
            self.query_one("#status", Static).update(
                f"{self._status_text}  ·  {elapsed}s"
            )

    def _set_status(self, status: str) -> None:
        self._status_text = status
        self.query_one("#status", Static).update(status)

    def _set_busy(self, busy: bool, status: str = "Ready") -> None:
        self._busy = busy
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = busy
        self.query_one("#spinner", LoadingIndicator).set_class(not busy, "hidden")
        self._set_status(status)
        if not busy:
            prompt.focus()

    async def _add_message(self, role: str, content: str) -> ConversationMessage:
        self._message_number += 1
        message = ConversationMessage(
            role,
            content,
            message_id=f"message-{self._message_number}",
        )
        await self.query_one("#transcript", VerticalScroll).mount(message)
        self.call_after_refresh(self._scroll_to_end)
        return message

    def _scroll_to_end(self) -> None:
        self.query_one("#transcript", VerticalScroll).scroll_end(animate=False)

    @work(exclusive=True, group="agent")
    async def request_requirements(self) -> None:
        self._started_at = monotonic()
        self._awaiting_requirements = False
        self._conversation_ready = False
        await self._add_message("Assistant", REQUIREMENTS_PROMPT)
        self._awaiting_requirements = True
        self.query_one("#prompt", Input).placeholder = (
            "Describe the target workload and reliability goals..."
        )
        self._set_busy(False, "Waiting for requirements")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        event.input.value = ""
        if not message or self._busy:
            return

        self.query_one(BlenderIntro).finish()
        command = message.lower()
        if command in {"exit", "quit", "/exit", "/quit"}:
            self.exit()
            return
        if command == "/retry":
            if not self._conversation_ready and not self._awaiting_requirements:
                self.request_requirements()
            return
        if command == "/clear":
            await self.action_clear()
            return
        if command == "/help":
            await self._add_message(
                "System",
                "**Commands:** `/clear` clears the transcript; `/retry` restarts a "
                "failed investigation; `/exit` quits. Press **Esc** to cancel an "
                "active response.",
            )
            return
        if self._awaiting_requirements:
            await self._add_message("You", message)
            self.run_report(message)
            return
        if not self._conversation_ready:
            await self._add_message(
                "System",
                "The investigation is not ready. Use `/retry` to run it again.",
            )
            return

        await self._add_message("You", message)
        self.run_follow_up(message)

    @work(exclusive=True, group="agent")
    async def run_report(self, requirements: str) -> None:
        self._started_at = monotonic()
        self._set_busy(True, "Preparing the assessment")
        response = await self._add_message("Assistant", "# Assessment\n\n")
        content = ""
        try:
            async for chunk in self.service.stream_report(
                requirements, self._set_status
            ):
                content += chunk
                await response.set_content(f"# Assessment\n\n{content}")
                self.call_after_refresh(self._scroll_to_end)
        except asyncio.CancelledError:
            if not content:
                await response.set_content("# Assessment\n\n*Assessment cancelled.*")
            self._set_busy(False, "Waiting for requirements")
            raise
        except Exception as error:
            await response.set_content(f"Assessment failed: `{error}`")
            self._set_busy(False, "Assessment failed · answer again")
            return

        self._awaiting_requirements = False
        self._conversation_ready = True
        self.query_one("#prompt", Input).placeholder = "Ask about the assessment..."
        self._set_busy(False)

    @work(exclusive=True, group="agent")
    async def run_follow_up(self, message: str) -> None:
        self._started_at = monotonic()
        self._set_busy(True, "Thinking")
        response = await self._add_message("Assistant", "")
        content = ""
        try:
            async for chunk in self.service.stream_follow_up(message):
                content += chunk
                await response.set_content(content)
                self.call_after_refresh(self._scroll_to_end)
        except asyncio.CancelledError:
            if not content:
                await response.set_content("*Response cancelled.*")
            raise
        except Exception as error:
            await response.set_content(f"Request failed: `{error}`")
            self._set_busy(False, "Request failed")
            return

        self._set_busy(False)

    async def action_clear(self) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        await transcript.remove_children()

    def action_cancel(self) -> None:
        intro = self.query_one(BlenderIntro)
        if intro.display:
            intro.finish()
            return
        workers = self.workers
        if self._busy:
            workers.cancel_group(self, "agent")
            status = "Cancelled" if self._conversation_ready else "Cancelled · use /retry"
            self._set_busy(False, status)
