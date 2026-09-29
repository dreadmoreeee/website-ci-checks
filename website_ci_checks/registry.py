"""The checks: how to build each command and how to read its exit code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

OK, PROBLEMS, ERROR = "pass", "fail", "error"


@dataclass(frozen=True)
class Context:
    url: str            # normalised, no trailing slash, e.g. https://example.com
    host: str           # example.com
    sarif_path: str | None = None


@dataclass(frozen=True)
class Check:
    name: str
    module: str         # python -m <module>
    folder: str         # tool folder name (repo / source folder)
    build: Callable[[Context], list[str]]
    problem_codes: tuple[int, ...] = (1,)   # exit codes meaning "the site has problems"
    doc: str = ""

    def interpret(self, code: int) -> str:
        if code == 0:
            return OK
        if code in self.problem_codes:
            return PROBLEMS
        return ERROR


def _security(c: Context) -> list[str]:
    # The tool only exits 1 with --fail-under; grade B is the CI bar.
    return [c.url, "--fail-under", "B", "--delay", "1"]


def _robots(c: Context) -> list[str]:
    return [c.url, "--lint"]


def _redirects(c: Context) -> list[str]:
    return ["canonical", c.host, "--delay", "1"]


def _html(c: Context) -> list[str]:
    args = [c.url + "/", "--crawl", "--max-pages", "10"]
    if c.sarif_path:
        args += ["--format", "sarif", "--output", c.sarif_path]
    return args


def _sitemap(c: Context) -> list[str]:
    return ["check", c.url, "--sample", "7", "--delay", "1.5", "--max-requests", "30"]


def _og(c: Context) -> list[str]:
    return [c.url, "--no-preview", "--delay", "1"]


CHECKS: dict[str, Check] = {
    ch.name: ch
    for ch in (
        Check("security-headers", "security_headers_audit", "security-headers-audit", _security,
              doc="grade below B exits 1"),
        Check("robots", "robots9309", "robots9309", _robots,
              doc="--lint, 1 = errors in robots.txt"),
        Check("redirects", "redirect_checker", "redirect-checker", _redirects,
              doc="canonical host check, 1 = failure, 2 = usage error"),
        Check("html-lint", "html_lint", "html-lint", _html,
              doc="crawl up to 10 pages, 1 = findings, 2 = unreadable input"),
        Check("sitemap", "sitemap_diff", "sitemap-diff", _sitemap,
              doc="check subcommand, 1 = problems, 2 = error"),
        Check("og-card", "og_card_check", "og-card-check", _og,
              doc="1 = errors in Open Graph tags"),
    )
}


def normalise_url(url: str) -> Context:
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"not an http(s) URL: {url}")
    base = f"{parts.scheme}://{parts.netloc}"
    path = parts.path.rstrip("/")
    return Context(url=base + path, host=parts.netloc)
