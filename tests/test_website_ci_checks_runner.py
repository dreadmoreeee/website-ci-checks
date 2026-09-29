import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from website_ci_checks.__main__ import main
from website_ci_checks.registry import CHECKS, Context, normalise_url
from website_ci_checks.runner import build_command, build_env, run_check, should_fail, Result


def fake_run(codes=None, calls=None, stdout="out line\n", stderr=""):
    codes = codes or {}

    def run(cmd, **kw):
        if calls is not None:
            calls.append((cmd, kw))
        module = cmd[2]
        return SimpleNamespace(returncode=codes.get(module, 0), stdout=stdout, stderr=stderr)
    return run


CTX = Context("https://example.com", "example.com")


def test_normalise():
    c = normalise_url("example.com/")
    assert (c.url, c.host) == ("https://example.com", "example.com")
    with pytest.raises(ValueError):
        normalise_url("ftp://x.org")


def args_of(name, ctx=CTX):
    cmd = build_command(CHECKS[name], ctx)
    assert cmd[:2] == [sys.executable, "-m"]
    return cmd[2], cmd[3:]


def test_command_building():
    assert args_of("security-headers") == (
        "security_headers_audit", ["https://example.com", "--fail-under", "B", "--delay", "1"])
    assert args_of("robots") == ("robots9309", ["https://example.com", "--lint"])
    assert args_of("redirects")[1][:2] == ["canonical", "example.com"]
    assert args_of("sitemap")[1][:2] == ["check", "https://example.com"]
    assert args_of("og-card")[0] == "og_card_check"
    mod, a = args_of("html-lint")
    assert mod == "html_lint" and a[0] == "https://example.com/" and "--format" not in a
    _, a = args_of("html-lint", Context("https://example.com", "example.com", "out/h.sarif"))
    assert a[-4:] == ["--format", "sarif", "--output", "out/h.sarif"]


def test_local_src_pythonpath():
    env = build_env(CHECKS["robots"], "C:/src", {"PYTHONPATH": "old"})
    assert env["PYTHONPATH"] == os.path.join("C:/src", "robots9309") + os.pathsep + "old"
    assert env["PYTHONUTF8"] == "1"
    env = build_env(CHECKS["html-lint"], "S", {})
    assert env["PYTHONPATH"] == os.path.join("S", "html-lint")
    assert "PYTHONPATH" not in build_env(CHECKS["robots"], None, {})


def test_exit_code_interpretation():
    for name, ch in CHECKS.items():
        assert ch.interpret(0) == "pass"
        assert ch.interpret(1) == "fail"
        assert ch.interpret(2) == "error"
        assert ch.interpret(137) == "error"


def test_run_check_uses_env_and_timeout():
    calls = []
    r = run_check(CHECKS["robots"], CTX, "SRC", 12, fake_run(calls=calls))
    assert r.status == "pass" and r.code == 0
    _, kw = calls[0]
    assert kw["timeout"] == 12 and kw["env"]["PYTHONPATH"].startswith(os.path.join("SRC", "robots9309"))


def test_timeout_is_error():
    def run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"], output="partial")
    r = run_check(CHECKS["robots"], CTX, None, 1, run)
    assert r.status == "error" and r.code is None and "Timed out" in r.output


def mk(name, status):
    return Result(name, status, 0, 0.1, "", ["py"])


def test_fail_on_logic():
    rs = [mk("robots", "pass"), mk("sitemap", "fail"), mk("og-card", "error")]
    assert should_fail(rs, "any")
    assert not should_fail(rs, "none")
    assert should_fail(rs, "sitemap")
    assert should_fail(rs, "robots,og-card")
    assert not should_fail(rs, "robots")


def test_main_summary_and_exit(tmp_path, monkeypatch, capsys):
    step = tmp_path / "step.md"
    extra = tmp_path / "extra.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step))
    monkeypatch.setattr(subprocess, "run", fake_run({"sitemap_diff": 1, "redirect_checker": 2}))
    code = main(["--url", "https://example.com", "--checks", "robots,sitemap,redirects",
                 "--summary", str(extra)])
    out = capsys.readouterr().out
    assert code == 1
    assert "| robots | PASS | 0 |" in out
    assert "| sitemap | FAIL | 1 |" in out
    assert "| redirects | ERROR | 2 |" in out
    assert "<details><summary>sitemap: FAIL</summary>" in out and "out line" in out
    assert step.read_text(encoding="utf-8").startswith("## Website checks: https://example.com")
    assert extra.exists()


def test_main_fail_on_none_and_subset(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run({"sitemap_diff": 1}))
    base = ["--url", "example.com", "--checks", "robots,sitemap"]
    assert main(base + ["--fail-on", "none"]) == 0
    assert main(base + ["--fail-on", "robots"]) == 0
    assert main(base + ["--fail-on", "sitemap"]) == 1


def test_main_sarif_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    calls = []
    monkeypatch.setattr(subprocess, "run", fake_run(calls=calls))
    assert main(["--url", "https://example.com", "--checks", "html-lint",
                 "--sarif-dir", str(tmp_path / "s")]) == 0
    assert calls[0][0][-1] == str(tmp_path / "s" / "html-lint.sarif")


def test_usage_errors(monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", fake_run())
    assert main(["--url", "https://example.com", "--checks", "robots,nope"]) == 2
    assert main(["--url", "https://example.com", "--fail-on", "nope"]) == 2
    assert main(["--url", "ftp://example.com"]) == 2
    assert main([]) == 2
