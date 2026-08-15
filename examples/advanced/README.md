# 进阶示例

这些示例分别展示独立 DSL 能力。部分示例会故意失败，用于观察 retry、timeout 和 fail-fast 行为。

建议命令：

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

- `db_sqlite.yaml` 展示 DB 查询、结果提取与断言；同一 testcase 中的步骤会复用一个串行 SQLite 连接。
- `upload.yaml` 使用 `examples/assets/test_upload.csv` 展示 multipart 文件上传。
- `http_assertions.yaml` 展示响应元信息路径（`$$.headers.*`）、正则与长度断言、带 `content_type` 的 raw body，以及 extract 默认值。
- `hooks.yaml` 同时使用 `hooks.py` 和 `hooks_extra.py`，展示拆分 hook 文件的发现顺序。
- `json_case.json` 展示使用 JSON 而不是 YAML 编写 testcase。
