import argparse
import asyncio
from contextlib import suppress
import logging
from pathlib import Path
from time import monotonic
from typing import Awaitable, TypeVar

from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown

from will_it_scale.agents.investigation_architect import create_investigation_architect_agent
from will_it_scale.agents.kubernetes_investigator import create_kubernetes_investigator_agent

FIXTURE_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "test_data/sample_service/kubernetes/deployment.yaml"
)
LOGGER = logging.getLogger("will_it_scale")
T = TypeVar("T")


def main() -> None:
    args = parse_args()
    configure_logging(debug=args.debug)
    asyncio.run(run_agent())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assess whether a service can support its target workload."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show detailed progress while agents are running",
    )
    return parser.parse_args()


def configure_logging(*, debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=Console(stderr=True),
                rich_tracebacks=True,
                show_path=debug,
            )
        ],
    )


async def run_step(label: str, operation: Awaitable[T]) -> T:
    started_at = monotonic()
    LOGGER.info("%s started", label)

    async def log_heartbeat() -> None:
        while True:
            await asyncio.sleep(10)
            LOGGER.debug(
                "%s is still running (%.0fs elapsed)", label, monotonic() - started_at
            )

    heartbeat = asyncio.create_task(log_heartbeat())
    try:
        result = await operation
    except Exception:
        LOGGER.exception("%s failed after %.1fs", label, monotonic() - started_at)
        raise
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat

    LOGGER.info("%s completed in %.1fs", label, monotonic() - started_at)
    return result


async def run_agent() -> None:
    LOGGER.debug("Reading Kubernetes manifest from %s", FIXTURE_MANIFEST)
    kubernetes_investigator = create_kubernetes_investigator_agent()
    manifest = FIXTURE_MANIFEST.read_text(encoding="utf-8")
    LOGGER.debug("Loaded Kubernetes manifest (%d characters)", len(manifest))

    investigation = await run_step(
        "Kubernetes investigation",
        kubernetes_investigator.run(
            """
            Investigate the Kubernetes configuration below for an order service that must support
            100 requests per second. Return concise, evidence-backed findings for the Investigation
            Architect. Identify scaling, scheduling, and availability risks, cite the relevant
            manifest fields, and call out any unknowns.

            Kubernetes manifest:
            """
            + manifest
        ),
    )

    LOGGER.debug("Creating Investigation Architect agent")
    architect = create_investigation_architect_agent()
    review = await run_step(
        "Architecture review",
        architect.run(
            """
            Review the Kubernetes investigator's findings below for the order service assessment.
            The primary concern is whether the service can support 100 requests per second. Identify
            confirmed concerns, handled concerns, new risks, unknowns, contradictions, and the next
            validation steps. Explain which conclusions are supported by the investigator's evidence.

            Kubernetes investigator findings:
            """
            + str(investigation)
        ),
    )

    LOGGER.debug("Rendering final report")
    console = Console()
    console.print(Markdown(f"# Investigation Architect\n\n{review}"))


if __name__ == "__main__":
    main()