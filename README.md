# website-ci-checks

One GitHub Action that runs six small website checks against a live URL and puts the results in a single job summary.

```yaml
- uses: dreadmoreeee/website-ci-checks@main
  with:
    url: https://example.com
```

It runs these tools (all standard library, no dependencies), each with a polite request rate:

| Check | Tool | What runs | Exit code 1 means |
|---|---|---|---|
| `security-headers` | [security-headers-audit](https://github.com/dreadmoreeee/security-headers-audit) | `URL --fail-under B` | grade below B |
| `robots` | [robots9309](https://github.com/dreadmoreeee/robots9309) | `URL --lint` | errors in robots.txt |
| `redirects` | [redirect-checker](https://github.com/dreadmoreeee/redirect-checker) | `canonical HOST` | a canonical-host variant fails |
| `html-lint` | [html-lint](https://github.com/dreadmoreeee/html-lint) | `URL/ --crawl --max-pages 10` | findings at error level |
| `sitemap` | [sitemap-diff](https://github.com/dreadmoreeee/sitemap-diff) | `check URL --sample 7` | sitemap problems |
| `og-card` | [og-card-check](https://github.com/dreadmoreeee/og-card-check) | `URL --no-preview` | Open Graph errors |

Exit codes are read per tool: `0` is pass, `1` is a problem found on the site (status **fail**), anything else (a usage error, an unreachable site, a timeout, a crash) is **error**. Both count as failures for `fail-on`.

## Usage

```yaml
name: Website checks
on:
  schedule:
    - cron: "0 7 * * 1"
  workflow_dispatch:

permissions:
  contents: read
  security-events: write   # only with sarif: "true"

jobs:
  website:
    runs-on: ubuntu-latest
    steps:
      - uses: dreadmoreeee/website-ci-checks@main
        with:
          url: https://example.com
          checks: all
          fail-on: any
          sarif: "true"
```

Inputs:

| Input | Default | Meaning |
|---|---|---|
| `url` | required | site to check |
| `checks` | `all` | comma list of `security-headers`, `robots`, `redirects`, `html-lint`, `sitemap`, `og-card` |
| `fail-on` | `any` | `any`, `none`, or a comma list of checks whose failure fails the job |
| `sarif` | `false` | `true` uploads the html-lint SARIF to code scanning |
| `python-version` | `3.12` | Python for the checks |
| `tools-ref` | `main` | branch, tag or commit of the tool repositories to install |

Only the tools for the selected checks are installed. The Markdown summary is appended to `$GITHUB_STEP_SUMMARY` and printed to the log. The runner's exit code fails the job.

**SARIF.** With `sarif: "true"` and `html-lint` selected, html-lint writes SARIF and the action uploads it with `github/codeql-action/upload-sarif@v3` (also when a check failed). The job needs `security-events: write`, and code scanning must be available for the repository (public repositories, or GitHub Advanced Security). [examples/workflow.yml](examples/workflow.yml) runs on push, weekly and on demand (copy it to `.github/workflows/` in your repository); [examples/workflow-minimal.yml](examples/workflow-minimal.yml) is a smaller starting point.

## Run it locally

```
python -m website_ci_checks --url URL --checks a,b,c [--fail-on any|none|a,b] [--local-src DIR]
                            [--sarif-dir DIR] [--summary FILE] [--timeout S]
```

`--local-src DIR` prepends `DIR/<tool folder>` to `PYTHONPATH` for each tool, so they run from source without installing. Exit code: `1` if a check selected by `--fail-on` failed or errored, `2` for usage errors or an unknown check, else `0`.

## Measured result

Real run on 2026-09-29 against my own site, all six checks, tools run from source. The run took about 40 seconds and exited `0`:

```
$ python -m website_ci_checks --url https://marvin.demarkstudio.ca --checks security-headers,robots,redirects,html-lint,sitemap,og-card --local-src C:\Users\marvin --sarif-dir sarif-out
## Website checks: https://marvin.demarkstudio.ca

| Check | Status | Exit code | Duration |
|---|---|---|---|
| security-headers | PASS | 0 | 2.3s |
| robots | PASS | 0 | 0.4s |
| redirects | PASS | 0 | 4.6s |
| html-lint | PASS | 0 | 7.1s |
| sitemap | PASS | 0 | 21.1s |
| og-card | PASS | 0 | 3.5s |

6 of 6 checks passed.
```

Each check also gets a collapsible section with the tail of its output. Two lines from them, verbatim: `https://marvin.demarkstudio.ca  grade A (90/100)` (security-headers, so the grade B bar passed) and `1 page(s), 0 error(s), 1 warning(s)` (og-card: the title is 68 characters, and warnings do not fail the check).

```
$ python -m pytest -q -p no:cacheprovider --import-mode=importlib website-ci-checks
...........
11 passed in 0.08s
```

The tests mock `subprocess.run`, so they need no network.

## Limitations

- The pass bar is fixed per check (grade B, robots.txt errors, at most 10 crawled pages, 7 sampled sitemap URLs). Run the tools directly for other thresholds.
- It checks one URL per run; use a matrix over `url` for several sites.

## Author

Marvin Palencia, founder of [DeMark Studio](https://demarkstudio.ca), Miramichi, New Brunswick, Canada. Portfolio: [marvin.demarkstudio.ca](https://marvin.demarkstudio.ca)

MIT License.
