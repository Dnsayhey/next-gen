# Next-Gen API Test Engine

轻量但具备架构价值的接口测试执行引擎。

## 特性

- DSL（YAML/JSON）定义测试用例
- DAG（依赖图）执行模型
- 变量系统（Context）
- 异步并发执行（asyncio）
- 插件化执行器（HTTP / DB / 自定义）
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
- `examples/hook_demo.yaml`：`before_all / after_all / before_each / after_each / before / after` 与自定义 hook 示例
- `examples/retry_demo.yaml`：固定间隔和指数退避重试示例
- `examples/timeout_demo.yaml`：请求级和步骤级超时示例
- `examples/db_demo.yaml`：SQLite 查询、提取和跨步骤引用示例

例如：

```bash
uv run nextgen examples/full_demo.yaml --verbose
uv run nextgen examples/hook_demo.yaml --verbose
```

`examples/hook_demo.yaml` 会自动加载同目录下的 [examples/hooks.py](/Users/yanlei/Projects/python/next-gen/examples/hooks.py:1)，用来演示自定义 hook 的发现与注册。

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

## 项目结构

```
nextgen/
├── cli.py              # CLI 入口
├── core/
│   ├── model.py        # AST 模型
│   ├── context.py      # 变量系统
│   ├── planner.py      # DAG 规划
│   ├── protocol.py     # 协议定义
│   └── scheduler.py    # 调度器
├── parser/
│   └── loader.py       # YAML/JSON 解析
├── executors/
│   └── http/           # HTTP 执行器
└── reporter/
    └── json_reporter.py
```

## 扩展新 Action 类型

```python
from nextgen import ActionSpec, register_action

# 1. 实现 executor 函数
async def execute_db(action_config, ctx): ...
def extract_db(result, config, ctx): ...
def validate_db(result, assertions): ...
def validate_db_config(config): ...

# 2. 注册
register_action(ActionSpec(
    name="db",
    execute=execute_db,
    extract=extract_db,
    validate=validate_db,
    validate_config=validate_db_config,
))
```

## 文档

- [设计文档](docs/design.md)

## License

MIT
