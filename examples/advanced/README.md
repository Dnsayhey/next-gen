# Advanced Examples

These examples focus on individual DSL features. Some are intentionally failing so you can inspect retry, timeout, and fail-fast behavior.

Suggested commands:

```bash
uv run nextgen examples/advanced/tags.yaml --tags smoke --dry-run
uv run nextgen examples/advanced/tags.yaml --tags smoke --skip-tags slow
uv run nextgen examples/advanced/conditional.yaml
uv run nextgen examples/advanced/matrix.yaml --dry-run
uv run nextgen examples/advanced/matrix.yaml --parallel=5
uv run nextgen examples/advanced/hooks.yaml --verbose
uv run nextgen examples/advanced/db_sqlite.yaml
uv run nextgen examples/advanced/failure_and_retry.yaml
uv run nextgen examples/advanced/timeout_failure.yaml
```
