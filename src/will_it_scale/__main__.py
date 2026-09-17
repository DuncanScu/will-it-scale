import argparse
import logging
import os

from will_it_scale.tui import WillItScaleApp


def main() -> None:
    args = parse_args()
    configure_logging(debug=args.debug)
    # --interpret implies deterministic mode; both bypass the interactive UI.
    if args.checks or args.interpret:
        run_checks(source=args.source, namespace=args.namespace, interpret=args.interpret)
        return
    # Let the TUI honor the same --source/--namespace flags (via env, which from_env reads).
    if args.source:
        os.environ["ASSESS_SOURCE"] = args.source
    if args.namespace:
        os.environ["TARGET_NAMESPACE"] = args.namespace
    WillItScaleApp().run(inline=True, inline_no_clear=True)


def run_checks(*, source: str | None, namespace: str | None, interpret: bool) -> None:
    """Deterministic analysis printed to stdout, no interactive UI."""
    from will_it_scale.assess import report_findings, run
    from will_it_scale.assessment import DEFAULT_MANIFEST
    from will_it_scale.checks import evaluate_workloads
    from will_it_scale.collectors.manifest import load_workload_facts

    resolved = source or os.environ.get("ASSESS_SOURCE", "manifest")
    if resolved == "live":
        from will_it_scale.config import resolve_subscription_id

        sub = resolve_subscription_id()
        rg = os.environ.get("TARGET_RG", "deploy-assess-rg")
        cluster = os.environ.get("TARGET_CLUSTER", "deploy-assess-aks")
        ns = namespace or os.environ.get("TARGET_NAMESPACE", "default")
        print(f"Source: live cluster {cluster}, namespace {ns}")
        findings = run(sub, rg, cluster, ns)
        label = cluster
    else:
        print(f"Source: manifest {DEFAULT_MANIFEST.name}")
        findings = evaluate_workloads(load_workload_facts(DEFAULT_MANIFEST))
        label = DEFAULT_MANIFEST.stem

    report_findings(findings, label, interpret=interpret)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assess whether a service can support its target workload."
    )
    parser.add_argument(
        "--checks",
        action="store_true",
        help="run deterministic checks only and print findings, without the interactive UI",
    )
    parser.add_argument(
        "--interpret",
        action="store_true",
        help="add the Foundry interpretation pass to the deterministic findings (implies --checks)",
    )
    parser.add_argument(
        "--source",
        choices=["manifest", "live"],
        help="evidence source (default: manifest, or $ASSESS_SOURCE)",
    )
    parser.add_argument(
        "--namespace",
        help="namespace to assess in live mode (overrides $TARGET_NAMESPACE)",
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