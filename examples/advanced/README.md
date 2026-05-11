# Advanced Examples

These examples focus on individual DSL features. Some are intentionally failing so you can inspect retry, timeout, and fail-fast behavior.

Suggested commands:

```bash
uv run nextgen examples/advanced/tags.yaml --tags smoke --dry-run
uv run nextgen examples/advanced/tags.yaml --tags smoke --skip-tags slow
uv run nextgen examples/advanced/conditional.yaml
uv run nextgen examples/advanced/matrix.yaml --dry-run
uv run nextgen examples/advanced/matrix.yaml --parallel=5
uv run nextgen examples/advanced/http_assertions.yaml
uv run nextgen examples/advanced/hooks.yaml --verbose
uv run nextgen examples/advanced/json_case.json
uv run nextgen examples/advanced/db_sqlite.yaml
uv run nextgen examples/advanced/upload.yaml
uv run nextgen examples/advanced/failure_and_retry.yaml
uv run nextgen examples/advanced/timeout_failure.yaml
```

`upload.yaml` demonstrates multipart file upload using `examples/assets/test_upload.csv`.
`http_assertions.yaml` demonstrates response metadata paths (`$$.headers.*`), regex and length assertions, raw request bodies with `content_type`, and extract defaults.
`hooks.yaml` uses hooks from both `hooks.py` and `hooks_extra.py` to show split hook file discovery.
`json_case.json` shows that testcase files can be written as JSON as well as YAML.
