# Next-Gen API Test Engine

轻量但具备架构价值的接口测试执行引擎。

## 特性

- DSL（YAML/JSON）定义测试用例
- DAG（依赖图）执行模型
- 变量系统（Context）
- 异步并发执行（asyncio）
- Suite / 多文件执行
- 插件化 action（HTTP / DB / 自定义）
- 状态机驱动调度器（支持 retry）

## 安装

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

## 快速开始

创建测试用例 `demo.yaml`：

```yaml
version: 1

vars:
  base_url: https://httpbin.org

steps:
  get_test:
    request:
      method: GET
      url: ${base_url}/get
      params:
        name: test
    extract:
      param_name: $.args.name
    validate:
      - eq: [$.args.name, test]

  post_json:
    request:
      method: POST
      url: ${base_url}/post
      json:
        key: value
    validate:
      - eq: [$.json.key, value]

  login_matrix:
    matrix:
      user: [admin, user1, user2]
    request:
      method: POST
      url: ${base_url}/post
      json:
        username: ${user}
```

运行测试：

```bash
# 基本执行
uv run nextgen demo.yaml

# 指定并发数
uv run nextgen demo.yaml --parallel=5

# 显示详细日志
uv run nextgen demo.yaml --verbose

# 从环境文件加载变量（可传多个，后者覆盖前者）
uv run nextgen demo.yaml --env env/base.yaml --env env/staging.yaml

# 输出 JUnit XML 到 stdout
uv run nextgen demo.yaml --report junit

# 写报告到文件，终端摘要仍输出到 stderr
uv run nextgen smoke.yaml --report junit --output reports/junit.xml

# 只生成执行计划，不真正执行 HTTP/DB action 或 hooks
uv run nextgen smoke.yaml --dry-run

# 只运行带 smoke 标签的步骤，并自动包含它们的依赖
uv run nextgen smoke.yaml --tags smoke

# 跳过 slow 标签步骤
uv run nextgen smoke.yaml --skip-tags slow

# 执行 suite 文件
uv run nextgen smoke.yaml

# 执行多个 testcase 文件，输出聚合 suite 结果
uv run nextgen tests/user/profile.yaml tests/order/create.yaml

# 递归发现目录下的 testcase 文件
uv run nextgen tests/

# 使用 glob pattern 发现 testcase 文件
uv run nextgen "tests/**/*.yaml"

# 或使用 python -m 方式
uv run python -m nextgen.cli demo.yaml
```

## 环境文件

`--env` / `-e` 可从 YAML 或 JSON 文件加载变量，并覆盖 testcase 中的 `vars`。多个环境文件按传入顺序合并，后面的文件覆盖前面的同名变量。

```yaml
# env/staging.yaml
base_url: https://staging.example.com
db_url: postgres://user:pass@localhost:5432/app
timeout: 5
debug: false
```

```bash
uv run nextgen examples/full_demo.yaml --env env/staging.yaml
```

环境文件顶层必须是对象，key 必须是字符串。建议将本地私密配置放在未提交的文件中，例如 `env/local.yaml` 或 `*.local.yaml`。

## Suite / 多文件执行

单个 suite 文件可以组织多个 testcase，并在普通测试前运行可选的 setup testcase：

```yaml
# smoke.yaml
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

```bash
uv run nextgen smoke.yaml
```

Suite 语义：

- `tests` 必填，且至少包含一个 testcase 路径
- `env`、`setup`、`tests` 路径都相对 suite 文件解析
- setup testcase 是普通 testcase 文件，按顺序先运行
- setup 成功后，每个成功步骤的 `export` 会作为 suite 变量提供给普通 tests
- 变量优先级：setup testcase 为 `testcase.vars < suite env < CLI --env`；普通 testcase 为 `testcase.vars < suite env < setup exports < CLI --env`
- setup 失败会让 suite 失败，普通 tests 不再执行，并在报告中显示为 testcase 级 `skipped`
- 普通 testcase 失败不会阻止后续普通 testcase 执行，suite 会尽量产出完整报告
- 多个 setup 文件导出同名变量时，后面的 setup 覆盖前面的 setup
- suite 内 testcase 的 context、hooks、result 彼此隔离；不支持跨 testcase `depends_on`

CLI 也支持直接传多个 testcase 文件：

```bash
uv run nextgen tests/user/profile.yaml tests/order/create.yaml
uv run nextgen tests/
uv run nextgen "tests/**/*.yaml"
```

显式传多个 testcase 文件时，会按传入顺序执行，按解析后的绝对路径去重，并输出聚合的 `SuiteResult`。

目录和 glob 输入会递归发现 `.yaml`、`.yml`、`.json` testcase 文件，按稳定路径顺序执行，并输出聚合的 `SuiteResult`。目录发现是 testcase 批量收集，不是 suite 编排：

- 只有 `steps` 的文件会作为 testcase 收集
- 只有 `tests` 的 suite 文件会 warning 并跳过；suite 文件需要显式传入
- 同时包含 `steps` 和 `tests` 的文件会报错
- 二者都没有的 YAML/JSON 会被忽略，便于把 env/example 文件放在测试目录里
- 发现后没有任何 testcase 会报错

显式 suite 文件暂不允许和其他 CLI 输入混用。

## 示例

可以直接从 `examples/` 里的 DSL 开始试跑：

- `examples/full_demo.yaml`：HTTP DSL 的完整示例，覆盖 GET/POST、提取、断言、依赖和重试
- `examples/full_demo.json`：JSON 版完整示例
- `examples/conditional_demo.yaml`：`when` 条件执行示例
- `examples/set_vars_demo.yaml`：`set_vars` 与 `extract` 的作用域示例
- `examples/export_demo.yaml`：`extract` 后用 `export` 显式导出拼接变量的示例
- `examples/matrix_demo.yaml`：`matrix` 参数化示例，包含单维展开和笛卡尔积展开
- `examples/parallel_demo.yaml`：`mode: parallel` 并行调度示例
- `examples/fail_fast_demo.yaml`：`fail_fast: false` 与依赖失败跳过语义示例
- `examples/hook_demo.yaml`：`before_all / after_all / before_each / after_each / before / after` 与自定义 hook 示例
- `examples/retry_demo.yaml`：固定间隔和指数退避重试示例
- `examples/timeout_demo.yaml`：请求级和步骤级超时示例
- `examples/db_demo.yaml`：SQLite 查询、提取和跨步骤引用示例

例如：

```bash
uv run nextgen examples/full_demo.yaml --verbose
uv run nextgen examples/hook_demo.yaml --verbose
```

`examples/hook_demo.yaml` 会自动加载同目录下的 `examples/hooks.py`，用来演示自定义 hook 的发现与注册。

## Tags / Step Filtering

Step 可以声明标签：

```yaml
steps:
  login:
    tags: [auth]
    request: ...

  profile:
    tags: [smoke]
    depends_on: [login]
    request: ...

  audit:
    tags: [slow]
    request: ...
```

CLI 可以按标签选择或排除步骤：

```bash
uv run nextgen case.yaml --tags smoke
uv run nextgen case.yaml --tags smoke --skip-tags slow
```

过滤语义：

- 多个 `--tags` 是 OR 关系，选中带任一 include tag 的 step
- 被选中的 step 会自动递归包含所有 `depends_on` 依赖
- 多个 `--skip-tags` 是 OR 关系，带任一 skip tag 的 step 会被排除
- `--skip-tags` 优先级高于 `--tags`
- 如果被选中的 step 依赖了被 skip 的 step，会报错并返回 exit code 2
- 如果 target step 自己同时被 include 和 skip，v1 会静默排除它
- 过滤后没有任何 step 会报错
- suite 中 setup testcase 和普通 testcase 都会应用同一套 tag filter；如果 setup 中负责 `export` 的 step 被过滤掉，后续普通 testcase 可能缺少对应变量
- dry-run 会展示过滤后的 steps、execution order 和 filters

## Dry-run / 执行计划

`--dry-run` 会完整加载 testcase 或 suite、合并 env 文件、展开 matrix、校验 DAG、发现 `hooks.py`，然后输出 JSON 执行计划，但不会执行 action，也不会加载或执行 hook。

```bash
uv run nextgen smoke.yaml --dry-run
uv run nextgen tests/user/profile.yaml --dry-run --env env/staging.yaml
uv run nextgen tests/ --dry-run
```

Dry-run 输出只包含 env key，不输出 env value，避免泄露 token/password 等敏感配置。步骤里的 `summary` 来自动作的原始配置摘要，变量模板不会被渲染，例如 `POST ${base_url}/login`。

单 testcase 计划包含：

- `testcase`、`mode`、`fail_fast`
- `env_keys`
- `hook_files`
- `declared_export_keys`
- `steps`
- `execution_order`

Suite 计划还会包含 `setup`、`tests`、`setup_export_keys` 和 `runtime_setup_exports: true`。其中 setup export 的实际值只有运行时才能知道，dry-run 只静态列出声明的 export key。

## HTTP Session Reuse

同一个 testcase run 内的 HTTP steps 会自动复用一个 `httpx.AsyncClient`。这会复用连接池，并让 cookie jar 在同一 testcase 的多个 HTTP step 之间保持。

```yaml
steps:
  login:
    request:
      method: GET
      url: https://example.com/login

  profile:
    depends_on: [login]
    request:
      method: GET
      url: https://example.com/profile
```

Session 边界：

- session 只在单个 testcase 内共享
- suite 中每个 setup/test testcase 都有独立 session，不跨 testcase 文件共享 cookie
- suite setup 如果要给普通 testcase 传递登录态，应通过 `extract` / `export` 显式传 token/header 等变量
- testcase 结束后会自动关闭 HTTP client
- v1 不新增 DSL 配置项
- redirect 行为保持 httpx/client 默认语义；step 级 `timeout` 仍按 request 配置传入

## 执行语义（mode / depends_on / fail_fast）

- `depends_on` 是唯一依赖来源，默认不会自动给步骤补依赖
- `mode: sequential`：每轮只执行一个可运行步骤（按定义顺序）
- `mode: parallel`：每轮可并发执行多个可运行步骤
- `fail_fast` 默认 `true`：出现失败后，尚未开始的步骤会被标记为 `skipped`；已运行中的并发步骤不会被强制取消
- `fail_fast: false`：继续执行其他可运行步骤（但依赖失败步骤的节点仍会被跳过）

## 执行结果与报告

CLI 默认将 JSON 结果输出到 stdout。单个 testcase 输出 `TestResult`；suite 文件或多个 testcase 输入输出 `SuiteResult`，其中 `tests` 包含每个 testcase 的 `TestResult`。

每个步骤包含：

- `metric`：该步骤最核心的摘要指标，例如 HTTP 的 `{"label": "status_code", "value": 200}` 或 DB 的 `{"label": "row_count", "value": 1}`；`label` 使用稳定的 snake_case 标识
- `action_input`：action 收到的已渲染输入（便于排查变量替换与参数问题）
- `action_output`：action 输出快照（HTTP 为 `status_code/headers/body`，DB 为 `row_count/columns/rows`）
- `extracted` / `exported`：步骤成功后准备发布到全局上下文的提取变量与显式导出变量

失败定位语义：

- 请求/连接阶段失败：`action_input` 有值，`action_output` 通常为 `null`
- 收到响应后断言失败：`action_input` 和 `action_output` 都有值

示例（节选）：

```json
{
  "name": "verify_file_uploaded",
  "status": "failed",
  "action": "GET https://fs.example.com/fs",
  "metric": { "label": "status_code", "value": 200 },
  "action_input": {
    "type": "http",
    "method": "GET",
    "url": "https://fs.example.com/fs",
    "headers": { "Authorization": "Bearer xxx" },
    "params": { "path": "/" },
    "body_type": null,
    "body": null,
    "timeout": null
  },
  "action_output": {
    "status_code": 200,
    "headers": { "content-type": "application/json" },
    "body": { "code": 0, "infos": [] }
  },
  "error": "contains 断言失败: ..."
}
```

也可以选择 JUnit XML，便于 CI 系统收集测试报告：

```bash
uv run nextgen smoke.yaml --report junit --output reports/junit.xml
```

当前支持的报告格式：

- `json`：默认格式，stdout 输出完整结构化结果
- `junit`：JUnit XML，按 step 映射为 JUnit testcase；文件级失败或跳过会生成 synthetic testcase

如果提供 `--output`，报告写入指定文件，终端摘要仍输出到 stderr；未提供 `--output` 时，报告写入 stdout。

## 支持的请求体类型

```yaml
# JSON
request:
  json: { "key": "value" }

# Form 表单
request:
  form:
    key: value

# Multipart 文件上传
request:
  multipart:
    file: "@./data.csv"

# Raw Body
request:
  body: "@./file.xml"
  content_type: application/xml
```

`@` 文件路径可以使用相对路径或绝对路径；相对路径以 testcase 文件所在目录为基准。

## 项目结构

```
nextgen/
├── cli.py              # CLI 入口
├── bootstrap.py        # 内置 action 加载
├── core/
│   ├── model.py        # AST 模型
│   ├── errors.py       # 通用错误层级
│   ├── context.py      # 变量系统
│   ├── actions.py      # action 注册表
│   ├── hooks.py        # hook 注册表与发现
│   ├── discovery.py    # CLI 目录 / glob 输入发现
│   ├── planner.py      # DAG 规划
│   ├── condition.py    # when 条件评估
│   ├── operators.py    # 通用断言操作符
│   ├── extract.py      # 通用提取规则
│   ├── result.py       # 执行结果模型
│   ├── scheduler.py    # 调度器
│   └── suite.py        # Suite / 多文件执行编排
├── parser/
│   └── loader.py       # YAML/JSON 解析
├── actions/
│   ├── http/           # 内置 HTTP action 实现
│   └── db/             # 内置 DB action 实现
└── reporter/
    ├── base.py          # reporter 接口
    ├── junit_reporter.py # JUnit XML 报告实现
    └── json_reporter.py # JSON 报告实现
```

## 扩展新 Action 类型

完整扩展示例见 [设计文档 §14](docs/design.md#14-扩展新-action-类型)。注册入口是 `ActionSpec`：

```python
from nextgen import ActionSpec, register_action
from nextgen.core.result import ActionResult

# 1. 实现 action 函数
async def execute_db(config, ctx) -> ActionResult: ...
def extract_db(result, config, ctx): ...
def validate_db(result, assertions): ...

# 2. 注册
register_action(ActionSpec(
    name="db",
    parse_config=DbConfig.from_dict,
    execute=execute_db,
    extract=extract_db,
    validate=validate_db,
    summarize=lambda config: config.summary(),
))
```

## 文档

- [设计文档](docs/design.md)

## License

MIT
