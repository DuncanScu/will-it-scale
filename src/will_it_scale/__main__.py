import argparse
import logging

from will_it_scale.tui import WillItScaleApp


def main() -> None:
    configure_logging(debug=parse_args().debug)
    WillItScaleApp().run(inline=True, inline_no_clear=True)


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
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=(
            [logging.FileHandler("will-it-scale.log", encoding="utf-8")]
            if debug
            else [logging.NullHandler()]
        ),
        force=True,
    )


if __name__ == "__main__":
    main()