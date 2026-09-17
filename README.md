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

The inline terminal UI first asks for the workload and reliability targets to assess,
then investigates the available configuration against those requirements. It streams a
short assessment and accepts follow-up questions in the same conversation.

Commands and controls:

- `/help` shows the available commands.
- `/clear` clears the visible transcript without resetting the conversation.
- `/retry` restarts a failed or cancelled initial investigation.
- `/exit` or `Ctrl+C` quits.
- `Esc` cancels the active investigation or response.

### Blender Easter Egg

Enter `/game` at the chat prompt to catch falling Kubernetes resources with the
startup animation's blender. Use the left and right arrow keys to move, `Space`
to pause, `R` to restart, and `Esc` to return to the conversation. Each catch earns
10 points; three misses end the round, and the pace increases with your score.
The game needs a playing area of at least 24 columns by 12 rows (a 24 by 14
terminal in inline mode) and pauses automatically below that size. Your
assessment and conversation are preserved.

With `--debug`, diagnostic logs are written to `will-it-scale.log` so they do not
interfere with the terminal UI.
