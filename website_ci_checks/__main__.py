"""python -m website_ci_checks --url URL --checks a,b,c"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .registry import CHECKS, Context, normalise_url
from .runner import render_summary, run_check, should_fail


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="website_ci_checks",
                                description="Run website checks and write one Markdown summary.")
    p.add_argument("--url", required=True, help="site to check, e.g. https://example.com")
    p.add_argument("--checks", default="all",
                   help="comma list of: " + ", ".join(CHECKS) + " (default all)")
    p.add_argument("--fail-on", default="any",
                   help="any, none, or a comma list of checks whose failure fails the run (default any)")
    p.add_argument("--local-src", help="folder holding one source folder per tool (run without install)")
    p.add_argument("--sarif-dir", help="write html-lint SARIF to DIR/html-lint.sarif")
    p.add_argument("--summary", help="also append the Markdown summary to this file")
    p.add_argument("--timeout", type=float, default=300.0, help="seconds allowed per check (300)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _names(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def main(argv: list[str] | None = None, run=None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    names = list(CHECKS) if args.checks.strip() in ("", "all") else _names(args.checks)
    extra = [] if args.fail_on in ("any", "none") else _names(args.fail_on)
    unknown = [n for n in names + extra if n not in CHECKS]
    if unknown or not names:
        print("website_ci_checks: unknown check(s): " + (", ".join(unknown) or "(none given)")
              + "; choose from " + ", ".join(CHECKS), file=sys.stderr)
        return 2
    try:
        base = normalise_url(args.url)
    except ValueError as exc:
        print(f"website_ci_checks: {exc}", file=sys.stderr)
        return 2
    names = list(dict.fromkeys(names))
    sarif = None
    if args.sarif_dir:
        os.makedirs(args.sarif_dir, exist_ok=True)
        sarif = os.path.join(args.sarif_dir, "html-lint.sarif")
    ctx = Context(base.url, base.host, sarif)
    results = [run_check(CHECKS[n], ctx, args.local_src, args.timeout, run) for n in names]
    summary = render_summary(base.url, results)
    for path in (os.environ.get("GITHUB_STEP_SUMMARY"), args.summary):
        if path:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(summary + "\n")
    sys.stdout.buffer.write((summary + "\n").encode("utf-8", "replace"))
    sys.stdout.flush()
    return 1 if should_fail(results, args.fail_on) else 0


if __name__ == "__main__":
    sys.exit(main())
