# Next-Gen API Test Engine

轻量但具备架构价值的接口测试执行引擎。

## 特性

- DSL（YAML/JSON）定义测试用例
- DAG（依赖图）执行模型
- 变量系统（Context）
- 异步并发执行（asyncio）
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

# 或使用 python -m 方式
uv run python -m nextgen.cli demo.yaml
```

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

## 执行语义（mode / depends_on / fail_fast）

- `depends_on` 是唯一依赖来源，默认不会自动给步骤补依赖
- `mode: sequential`：每轮只执行一个可运行步骤（按定义顺序）
- `mode: parallel`：每轮可并发执行多个可运行步骤
- `fail_fast` 默认 `true`：出现失败后，尚未开始的步骤会被标记为 `skipped`；已运行中的并发步骤不会被强制取消
- `fail_fast: false`：继续执行其他可运行步骤（但依赖失败步骤的节点仍会被跳过）

## 执行结果（JSON）

CLI 会将结果以 JSON 输出到 stdout。每个步骤包含：

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
│   ├── planner.py      # DAG 规划
│   ├── condition.py    # when 条件评估
│   ├── operators.py    # 通用断言操作符
│   ├── extract.py      # 通用提取规则
│   ├── result.py       # 执行结果模型
│   └── scheduler.py    # 调度器
├── parser/
│   └── loader.py       # YAML/JSON 解析
├── actions/
│   ├── http/           # 内置 HTTP action 实现
│   └── db/             # 内置 DB action 实现
└── reporter/
    ├── base.py          # reporter 接口
    └── json_reporter.py # JSON 报告实现
```

## 扩展新 Action 类型

完整扩展示例见 [设计文档 §9](docs/design.md#9-扩展新-action-类型)。注册入口是 `ActionSpec`：

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
