# Next-Gen Roadmap Notes

This document captures the current product and engineering direction after the core engine reached daily-use readiness.

## Current State

The core engine is already usable for internal API and database testing:

- HTTP and DB actions
- Variable system: `vars`, `set_vars`, `extract`, `export`
- DAG scheduler with sequential and parallel modes
- `depends_on`, `fail_fast`, retry, backoff, and timeout
- `when` conditions
- Matrix expansion
- Lifecycle hooks and discovered `hooks.py`
- Environment files via `--env`
- JSON reporter and terminal summary
- Structured CLI error handling

The next work should focus on team-scale execution, CI integration, and authoring ergonomics rather than adding many new action types.

## Suite Before Include

Prefer **suite / multi-file execution** before YAML `include`.

### Why Suite First

Suite execution keeps testcase boundaries clear:

- Each testcase has its own parser, scheduler, hooks, context, and result.
- Step names do not collide across files.
- Env and hooks scoping remain understandable.
- CI reporting maps naturally to suites and testcase files.
- Future JUnit XML and dry-run output can share the same aggregate model.

YAML `include` would merge multiple files into one testcase and immediately raise harder questions:

- Step name collisions
- `vars`, hooks, mode, and `fail_fast` merge rules
- Cross-file `depends_on`
- Relative path resolution
- Whether reports represent one testcase or many testcases

Decision: do **not** implement include in the near term. Revisit only if there is a strong need for YAML fragment reuse that cannot be solved with env files, hooks, or future templates.

## Recommended Sequence

### 1. Suite / Multi-File Execution

Do this before JUnit XML and dry-run so those features can be designed against the aggregate run model from the beginning.

First version scope:

- Add `SuiteResult` containing multiple `TestResult` objects.
- Add `TestStatus.SKIPPED` so setup failures can produce skipped testcase-level results.
- Add a suite file format:

```yaml
name: smoke
env:
  - env/base.yaml
  - env/staging.yaml
setup:
  - tests/_setup/login.yaml
tests:
  - tests/user/profile.yaml
  - tests/order/create.yaml
```

- `tests` is required and must contain at least one testcase path.
- Suite `setup`, `tests`, and `env` paths are resolved relative to the suite file.
- Suite-level `env` applies to all testcases.
- CLI `--env` still applies and overrides suite env.
- Optional `setup` testcases run before normal `tests`.
- Setup testcases are ordinary testcase files.
- Successful setup exports are collected as suite-level variables for normal tests.
- Variable precedence for setup testcases:

```text
testcase.vars < suite env files < CLI --env files
```

- Variable precedence for normal testcases:

```text
testcase.vars < suite env files < setup exports < CLI --env files
```

If CLI env files define the same key as setup exports, the CLI value wins. For example, a `token` supplied via `--env` overrides a `token` exported by setup.

- Testcases run sequentially in the first version.
- Testcase contexts, hooks, and results remain isolated.
- Normal tests can read setup exports, but they do not share runtime contexts with each other.
- Multiple setup files may export the same variable; later setup exports override earlier ones.
- Setup failure makes the suite failed and prevents normal tests from running.
- Normal tests skipped because of setup failure should appear as synthetic skipped `TestResult` entries so reports preserve the full planned test list.
- Any failed testcase makes the suite failed.
- Continue running all testcase files by default to produce a complete report.
- No cross-testcase `depends_on`.
- No suite hooks in the first version.
- No teardown in the first version.
- No file-level parallelism in the first version.

Input discovery and output shape:

- Explicit single testcase file -> run as one testcase and output `TestResult`.
- Explicit suite file -> run as suite and output `SuiteResult`.
- Multiple files, directories, or any discovered batch -> output `SuiteResult`, even if discovery finds only one testcase. This keeps CI JSON shape stable.
- Explicit files are classified by content:
  - only `steps` -> testcase
  - only `tests` -> suite
  - both `steps` and `tests` -> error: ambiguous file format
  - neither -> error: unrecognized file format
- Directory discovery recursively scans YAML/JSON files but only runs testcase files:
  - only `steps` -> collect as testcase
  - only `tests` -> warn and skip; suite files must be passed explicitly
  - both `steps` and `tests` -> error
  - neither -> ignore, so env/example YAML files do not break directory runs
- If directory discovery finds no testcase files, return `no testcase files found`.
- Do not allow suite files to be mixed with other CLI inputs in the first version.
- De-duplicate testcase files by resolved path while preserving first occurrence.
- Execution order:
  - CLI multiple files: user-provided order
  - directory discovery: sorted by path for reproducibility
  - suite setup/tests: order in the suite file
  - shell-expanded globs: treated as CLI multiple files in the order received

Setup example:

```yaml
# tests/_setup/login.yaml
version: 1
steps:
  login:
    request:
      method: POST
      url: ${base_url}/login
      json:
        username: ${username}
        password: ${password}
    extract:
      token: $.data.token
    export:
      token: ${token}
```

Then normal suite tests can use `${token}` without repeating the login step in every file.

Open design points:

- Whether directory/glob discovery should be implemented in suite v1 or a separate follow-up.

### 2. JUnit XML Reporter

After suite result shape exists, add CI-friendly reporting:

- `--report json|junit`
- `--output path`
- JUnit maps naturally from suite/testcase/step hierarchy.

Design notes:

- Keep stdout JSON-compatible when no output file is requested.
- If `--output` is provided, write the selected report to the file and keep terminal summary on stderr.
- JSON reporter should support both single `TestResult` and `SuiteResult`.

### 3. Dry-Run / Execution Plan

Dry-run should use the same discovery and planning code as suite execution.

Expected behavior:

- Load testcase or suite.
- Load env files.
- Expand matrix steps.
- Validate DAGs.
- Discover hook files.
- Print execution plan without running actions.

Useful output:

- testcase file paths
- mode and fail_fast
- step names and dependencies
- matrix-expanded step names
- env variable keys, not values
- discovered hook files

### 4. Tags / Step Filtering

Tags improve day-to-day authoring and selective execution.

Example:

```yaml
steps:
  login:
    tags: [auth, smoke]
    request: ...
```

CLI:

```bash
nextgen case.yaml --tags smoke
nextgen case.yaml --tags auth --skip-tags slow
```

Design decisions:

- Add `tags: list[str]` to `StepNode`.
- Filtering should happen after parsing and graph validation but before scheduling.
- Default behavior should include dependencies of selected steps.
- Avoid putting tag filtering directly in the scheduler main loop.

Open design point:

- Add an option later for strict filtering where missing selected dependencies are reported instead of auto-included.

### 5. HTTP Session Reuse

Improve API testing ergonomics and performance:

- Reuse `httpx.AsyncClient` within one testcase run.
- Preserve cookie jar across HTTP steps.
- Close clients at the end of the run.

Design notes:

- Keep testcase isolation; sessions should not cross testcase files in suite runs.
- Be explicit about whether redirects, cookies, and default headers are preserved.

## Later Work

These are valuable, but should wait until suite/reporting/filtering foundations are stable:

- Directory and glob-based test discovery
- Better `ParseError` paths, such as `steps.login.validate[0].eq`
- Shell/exec action for non-Python setup workflows
- JSON Schema or OpenAPI validation
- Optional `--var key=value` CLI overrides
- Optional reporter redaction for externally shared artifacts
- ReDoS hardening if untrusted testcase execution becomes a goal

## Near-Term Recommendation

Start with **suite / multi-file execution**. It affects the shape of reporting, dry-run, tags, and CI behavior, so implementing it first should reduce later redesign.
