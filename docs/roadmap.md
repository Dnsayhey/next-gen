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
- Suite / multi-file execution v1
- JSON and JUnit XML reporters
- Terminal summary for both testcase and suite results
- Structured CLI error handling

The next work should focus on CI integration, execution planning, and authoring ergonomics rather than adding many new action types.

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

Status: **implemented in v1**.

This was done before JUnit XML and dry-run so those features can be designed against the aggregate run model from the beginning.

Implemented scope:

- `SuiteResult` containing multiple `TestResult` objects.
- `TestStatus.SKIPPED` for skipped testcase-level results.
- Suite file format:

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

- `tests` is required and must contain at least one non-empty testcase path.
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
- Normal tests skipped because of setup failure appear as synthetic skipped `TestResult` entries so reports preserve the full planned test list.
- Any failed testcase makes the suite failed.
- Normal testcase load, parse, validation, or execution errors become failed `TestResult` entries, and later normal testcases continue running to produce a complete report.
- No cross-testcase `depends_on`.
- No suite hooks in the first version.
- No teardown in the first version.
- No file-level parallelism in the first version.

Input discovery and output shape:

- Explicit single testcase file -> run as one testcase and output `TestResult`.
- Explicit suite file -> run as suite and output `SuiteResult`.
- Multiple explicit testcase files -> output `SuiteResult`.
- Explicit files are classified by content:
  - only `steps` -> testcase
  - only `tests` -> suite
  - both `steps` and `tests` -> error: ambiguous file format
  - neither -> error: unrecognized file format
- Do not allow suite files to be mixed with other CLI inputs in the first version.
- De-duplicate testcase files by resolved path while preserving first occurrence.
- Execution order:
  - CLI multiple files: user-provided order
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

Deferred from v1:

- Directory discovery, including recursive YAML/JSON scanning and stable sorted ordering.
- A discovered batch result shape for directory runs.

### 2. JUnit XML Reporter

Status: **implemented**.

Suite result shape now supports CI-friendly reporting:

- `--report json|junit`
- `--output path`
- JUnit maps suite/testcase/step hierarchy to XML.

Implemented behavior:

- Default report remains JSON.
- If `--output` is provided, the selected report is written to the file and terminal summary stays on stderr.
- Without `--output`, the selected report is written to stdout.
- JSON and JUnit reporters both support single `TestResult` and `SuiteResult`.
- JUnit maps each step to a testcase entry; file-level failed or skipped results use a synthetic testcase entry.

### 3. Dry-Run / Execution Plan

Status: **implemented**.

Dry-run uses the same loading and planning code as suite execution, then stops before scheduler/action execution.

Implemented behavior:

- Load testcase or suite.
- Load env files.
- Expand matrix steps.
- Validate DAGs.
- Discover hook files.
- Print execution plan without running actions.
- Do not load or execute hooks.
- Output env variable keys, not values.
- Keep action summaries unresolved/raw, such as `POST ${base_url}/login`.
- Fail fast with exit code 2 on parse or DAG validation errors.

Output includes:

- testcase file paths
- mode and fail_fast
- step names and dependencies
- matrix-expanded step names
- env variable keys, not values
- discovered hook files
- declared export keys
- suite setup export keys and `runtime_setup_exports`

### 4. Tags / Step Filtering

Status: **implemented in v1**.

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

Implemented decisions:

- `tags: list[str]` on `StepNode`.
- Filtering should happen after parsing and graph validation but before scheduling.
- Default behavior should include dependencies of selected steps.
- `--skip-tags` takes precedence over `--tags`.
- If a selected step requires a skipped dependency, filtering fails with exit code 2.
- If a selected target step is itself skipped, it is silently excluded.
- Suite setup testcases and normal testcases both receive the same tag filter; filtering setup steps can affect setup exports.
- Dry-run shows the filtered step set and active filters.
- Avoid putting tag filtering directly in the scheduler main loop.

Deferred:

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

Start with **HTTP session reuse** next. Suite execution, JUnit reporting, dry-run planning, and step filtering now cover the core team-scale and CI-facing workflow.
