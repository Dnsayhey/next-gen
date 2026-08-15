# Nextgen 入门示例

本目录按实际使用路径组织可运行示例：先执行单文件 testcase，再学习变量、suite 和目录发现。

## 1. 第一个 testcase

HTTP 断言中，`$` 读取响应 body（例如 JSON 字段），`$$` 读取 `status_code`、headers 等响应元信息。

```bash
uv run nextgen examples/guide/01_first_test.yaml
```

## 2. 变量与提取值

```bash
uv run nextgen examples/guide/02_variables_and_extract.yaml
```

## 3. Suite setup 与显式 export

Setup testcase 登录一次并导出认证 header，普通 testcase 会把该值作为 suite 变量使用。

```bash
uv run nextgen examples/guide/suite.yaml
```

## 4. 执行前检查计划

```bash
uv run nextgen examples/guide/suite.yaml --dry-run
uv run nextgen examples/guide/ --dry-run
```

目录发现会 warning 并跳过 `suite.yaml`，只收集 testcase 文件。

## 5. 运行 smoke 子集

```bash
uv run nextgen examples/guide/suite.yaml --tags smoke
```

命令只选择带 `smoke` tag 的步骤，同时保留其依赖。本 suite 中会运行 `login`、`fetch_profile` 和 `create_order`；仅带 `orders` tag 的 `fetch_order` 会被排除。

## 6. CI 报告

```bash
uv run nextgen examples/guide/suite.yaml --report junit --output reports/junit.xml
```
