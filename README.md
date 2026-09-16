# will-it-scale

A very small Python CLI for answering the important question.

## Development

Install the project and its development dependencies:

```shell
uv sync
```

Run the CLI:

```shell
uv run will-it-scale
```

The inline terminal UI runs the initial investigation, prints a short assessment,
and then accepts follow-up questions in the same conversation. Responses stream into
the transcript as they arrive.

Commands and controls:

- `/help` shows the available commands.
- `/clear` clears the visible transcript without resetting the conversation.
- `/retry` restarts a failed or cancelled initial investigation.
- `/exit` or `Ctrl+C` quits.
- `Esc` cancels the active investigation or response.

With `--debug`, diagnostic logs are written to `will-it-scale.log` so they do not
interfere with the terminal UI.
