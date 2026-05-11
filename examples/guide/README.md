# Nextgen Guide Examples

This directory is a runnable walkthrough rather than a feature dump. Start with one file, then move to suite and discovery workflows.

## 1. First testcase

In HTTP assertions, `$` reads the response body (for example JSON fields) and `$$` reads response metadata such as `status_code` and headers.

```bash
uv run nextgen examples/guide/01_first_test.yaml
```

## 2. Variables and extracted values

```bash
uv run nextgen examples/guide/02_variables_and_extract.yaml
```

## 3. Suite setup and shared exports

The setup testcase logs in once and exports an auth header. Normal testcases receive that value as a suite variable.

```bash
uv run nextgen examples/guide/suite.yaml
```

## 4. Review the plan before running

```bash
uv run nextgen examples/guide/suite.yaml --dry-run
uv run nextgen examples/guide/ --dry-run
```

Directory discovery skips `suite.yaml` with a warning and collects only testcase files.

## 5. Run a smoke subset

```bash
uv run nextgen examples/guide/suite.yaml --tags smoke
```

This runs only steps tagged `smoke`, while still keeping any required dependency steps. In this suite, `login`, `fetch_profile`, and `create_order` run; `fetch_order` is excluded because it is tagged only `orders`.

## 6. CI-style report

```bash
uv run nextgen examples/guide/suite.yaml --report junit --output reports/junit.xml
```
