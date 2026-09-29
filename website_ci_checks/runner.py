"""Run checks, capture output, render the Markdown summary."""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
import time

from .registry import ERROR, Check, Context

TAIL_LINES = 60


@dataclasses.dataclass
class Result:
    name: str
    status: str
    code: int | None
    seconds: float
    output: str
    command: list[str]


def build_env(check: Check, local_src: str | None, base: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    env["PYTHONUTF8"] = "1"
    if local_src:
        src = os.path.join(local_src, check.folder)
        old = env.get("PYTHONPATH")
        env["PYTHONPATH"] = src + os.pathsep + old if old else src
    return env


def build_command(check: Check, ctx: Context) -> list[str]:
    return [sys.executable, "-m", check.module, *check.build(ctx)]


def tail(text: str, lines: int = TAIL_LINES) -> str:
    rows = text.rstrip().splitlines()
    if len(rows) > lines:
        rows = [f"... ({len(rows) - lines} earlier lines omitted)"] + rows[-lines:]
    return "\n".join(rows)


def run_check(check: Check, ctx: Context, local_src: str | None = None,
              timeout: float = 300.0, run=None) -> Result:
    run = run or subprocess.run
    cmd = build_command(check, ctx)
    start = time.monotonic()
    try:
        proc = run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=timeout, env=build_env(check, local_src))
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        return Result(check.name, ERROR, None, time.monotonic() - start,
                      tail(out + f"\nTimed out after {timeout:g}s"), cmd)
    except OSError as exc:
        return Result(check.name, ERROR, None, time.monotonic() - start, f"Could not start: {exc}", cmd)
    secs = time.monotonic() - start
    text = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    return Result(check.name, check.interpret(proc.returncode), proc.returncode, secs, tail(text), cmd)


def should_fail(results: list[Result], fail_on: str) -> bool:
    if fail_on == "none":
        return False
    wanted = None if fail_on == "any" else {x.strip() for x in fail_on.split(",") if x.strip()}
    return any(r.status != "pass" and (wanted is None or r.name in wanted) for r in results)


ICON = {"pass": "PASS", "fail": "FAIL", "error": "ERROR"}


def render_summary(url: str, results: list[Result]) -> str:
    lines = [f"## Website checks: {url}", "",
             "| Check | Status | Exit code | Duration |", "|---|---|---|---|"]
    for r in results:
        code = "-" if r.code is None else str(r.code)
        lines.append(f"| {r.name} | {ICON[r.status]} | {code} | {r.seconds:.1f}s |")
    passed = sum(r.status == "pass" for r in results)
    lines += ["", f"{passed} of {len(results)} checks passed.", ""]
    for r in results:
        lines += [f"<details><summary>{r.name}: {ICON[r.status]}</summary>", "",
                  "`" + " ".join(_display(a) for a in r.command[1:]) + "`", "",
                  "```", r.output or "(no output)", "```", "", "</details>", ""]
    return "\n".join(lines)


def _display(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg
