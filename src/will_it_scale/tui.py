import asyncio
from time import monotonic

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Label, LoadingIndicator, Markdown, Static

from will_it_scale.assessment import AssessmentService


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
        self._status_text = "Starting investigation"
        self._message_number = 0
        self._busy = False
        self._conversation_ready = False

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
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
        self._set_busy(True, "Starting investigation")
        self.call_after_refresh(self.run_initial_assessment)

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
    async def run_initial_assessment(self) -> None:
        self._started_at = monotonic()
        self._set_busy(True, "Starting investigation")
        try:
            report = await self.service.investigate(self._set_status)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._add_message("System", f"Investigation failed: `{error}`")
            self._set_busy(False, "Investigation failed · use /retry")
            return

        await self._add_message("Assistant", f"# Assessment\n\n{report}")
        self._conversation_ready = True
        self._set_busy(False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        event.input.value = ""
        if not message or self._busy:
            return

        command = message.lower()
        if command in {"exit", "quit", "/exit", "/quit"}:
            self.exit()
            return
        if command == "/retry":
            if not self._conversation_ready:
                self.run_initial_assessment()
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
        if not self._conversation_ready:
            await self._add_message(
                "System",
                "The investigation is not ready. Use `/retry` to run it again.",
            )
            return

        await self._add_message("You", message)
        self.run_follow_up(message)

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
        workers = self.workers
        if self._busy:
            workers.cancel_group(self, "agent")
            status = "Cancelled" if self._conversation_ready else "Cancelled · use /retry"
            self._set_busy(False, status)
