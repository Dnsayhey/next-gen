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
from nextgen.parser.loader import register_action, register_action_validator
from nextgen.core.scheduler import register_executor

# 1. 实现 executor 函数
async def execute_db(action_config, ctx): ...
def extract_db(result, config, ctx): ...
def validate_db(result, assertions): ...

# 2. 注册
register_action("db")
register_action_validator("db", validate_db_config)
register_executor("db", execute_db, extract_db, validate_db)
```

## 文档

- [设计文档](docs/design.md)

## License

MIT
