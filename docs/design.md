# Next-Gen API Test Engine（Python版）设计文档

## 1. 项目目标

构建一个**轻量但具备架构价值的接口测试执行引擎**，具备以下能力：

* DSL（YAML/JSON）定义测试用例
* DAG（依赖图）执行模型
* 变量系统（Context）
* 异步并发执行（asyncio）
* 插件化执行器（HTTP / DB / 自定义）
* 状态机驱动调度器（支持 retry）

> ❗ 本项目聚焦"执行引擎"，不做重平台（UI/权限系统）

---

## 2. 技术选型

| 类别 | 选型 | 说明 |
|------|------|------|
| 包管理 | uv | 现代 Python 包管理器 |
| HTTP 客户端 | httpx | 原生 async 支持 |
| JSONPath | jsonpath-ng | 标准 JSONPath 表达式 |
| CLI | typer | 基于类型提示，自动生成 help |
| 日志 | loguru | 开箱即用，格式美观 |
| YAML 解析 | pyyaml | YAML 文件解析 |

### 设计决策

* **变量作用域**：局部优先（extract 覆盖全局同名变量）
* **断言操作符**：基础比较（eq / ne / gt / lt / gte / lte）+ contains
* **报告格式**：JSON 输出到 stdout
* **DSL 格式**：支持 YAML 和 JSON 两种格式
* **Executor 架构**：Protocol + 注册表模式，支持扩展

---

## 3. 总体架构

```text
DSL (YAML/JSON)
   ↓
Parser（解析 + 校验）
   ↓
AST（抽象语法树）
   ↓
Planner（构建 DAG + 循环检测）
   ↓
Scheduler（调度器 + 状态机）
   ↓
Executor（执行器：HTTP / DB / ...）
   ↓
Reporter（结果输出）
```

---

## 4. DSL 设计

### 4.1 完整示例

```yaml
version: 1

vars:
  base_url: https://httpbin.org

steps:
  # GET 请求 + 变量提取
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

  # POST JSON + 依赖关系
  post_json:
    request:
      method: POST
      url: ${base_url}/post
      json:
        username: admin
        password: "123456"
    extract:
      request_body: $.json
    validate:
      - eq: [$.json.username, admin]

  # 依赖其他步骤
  dependent_step:
    depends_on: [get_test]
    request:
      method: GET
      url: ${base_url}/get
      params:
        ref: ${param_name}
    validate:
      - eq: [$.args.ref, test]
```

### 4.2 请求体类型

支持 4 种请求体类型（互斥，同时出现会报错）：

```yaml
request:
  # JSON 请求体
  json: { "username": "admin" }

  # form 表单
  form:
    username: admin
    password: 123456

  # multipart 上传（支持 @ 前缀读取本地文件）
  multipart:
    file: "@./data.csv"
    name: test

  # raw body（支持 @ 前缀读取文件）
  body: "@./request.xml"
  content_type: application/xml
```

**文件路径规则：**
- 使用 `@` 前缀表示读取文件内容：`"@./file.txt"`、` "@/abs/path/file.txt"`
- 支持相对路径和绝对路径
- 自动根据扩展名判断文本/二进制读取模式
- 如文件不存在会报错

**YAML 注意事项：**
- `@` 是 YAML 保留字符，需要加引号：`file: "@./data.csv"`

### 4.3 变量系统

```yaml
vars:
  base_url: https://httpbin.org  # 全局变量

steps:
  login:
    request: ...
    extract:
      token: $.data.token  # 从响应中提取变量（局部优先）

  use_token:
    request:
      headers:
        Authorization: Bearer ${token}  # 使用变量
```

**支持的变量来源：**
- `${var}` — 从全局 vars 或已提取的变量中替换
- `$.data.token` — 从 response body 提取（JSONPath）
- `$.status_code` — 提取状态码
- `$.headers.xxx` — 从 response body 中的 headers 字段提取

### 4.4 断言系统

```yaml
validate:
  # 基础比较
  - eq: [$.code, 0]            # 等于
  - ne: [$.code, 1]            # 不等于
  - gt: [$.count, 10]          # 大于
  - lt: [$.count, 100]         # 小于
  - gte: [$.count, 10]         # 大于等于
  - lte: [$.count, 100]        # 小于等于

  # 字符串
  - contains: [$.message, success]  # 包含
```

### 4.5 执行配置

```yaml
steps:
  with_retry:
    request: ...
    config:
      retry: 3              # 最大重试次数
      retry_delay: 1        # 重试间隔（秒）
      retry_backoff: true   # 启用指数退避
      retry_max_delay: 60   # 最大重试间隔（秒），默认 60
      timeout: 30           # 步骤超时（秒），包含所有重试
```

**指数退避公式：** `delay = min(base * (2 ** attempt), max_delay)`

```
retry_delay: 1, retry_max_delay: 60
attempt 0 → 1s
attempt 1 → 2s
attempt 2 → 4s
attempt 3 → 8s
...
```

### 4.6 超时配置

支持两个层次的超时：

```yaml
steps:
  slow_api:
    request:
      method: GET
      url: ${base_url}/slow
      timeout: 10         # 请求级超时（秒），传递给 httpx
    config:
      timeout: 30         # 步骤级超时（秒），包含重试的总时间
      retry: 3
```

**超时优先级：** 请求级 > 步骤级 > httpx 默认（30s）

### 4.7 条件执行（when）

支持基于变量的条件执行，条件不满足时步骤自动跳过。

```yaml
steps:
  # 简单条件（列表默认 AND）
  login:
    request: ...
    extract:
      is_admin: $.data.is_admin

  admin_only:
    when:
      - eq: [${is_admin}, true]
    request: ...

  # 显式 AND 逻辑
  complex_and:
    when:
      and:
        - eq: [${role}, admin]
        - gt: [${level}, 5]
    request: ...

  # 显式 OR 逻辑
  fallback:
    when:
      or:
        - eq: [${env}, staging]
        - eq: [${env}, development]
    request: ...
```

**条件格式：**
- `list` — 断言列表，默认 AND 逻辑
- `dict` — 必须包含 `and` 或 `or` 键，值为断言列表
- 支持所有断言操作符：eq / ne / gt / lt / gte / lte / contains
- 支持 `${var}` 变量替换

**执行行为：**
- 条件为 false → 步骤标记为 SKIPPED
- SKIPPED 的步骤不会阻塞后续步骤
- 依赖被跳过步骤的步骤也会被跳过

### 4.8 设置变量（set_vars）

在步骤执行前设置变量，支持变量拼接。

```yaml
steps:
  setup:
    set_vars:
      user1: ${user}_1          # 变量拼接
      endpoint: ${base_url}/api # 构建 URL
      prefix: test              # 常量
    request:
      method: GET
      url: ${endpoint}/${user1}
```

**执行顺序：**
1. `set_vars` — 先设置变量
2. `when` — 评估条件
3. `request` / `db` — 执行 action
4. `validate` — 验证结果
5. `extract` — 提取变量

---

## 5. AST 设计

### 5.1 StepNode

```python
@dataclass
class StepNode:
    name: str
    action_type: str              # "request" / "db" / "python" 等
    action_config: dict[str, Any] # 原始 action 配置
    depends_on: list[str]
    extract: dict[str, str]
    validate: list[AssertionNode]
    when: list | dict | None      # 条件执行（list=AND, dict=and/or）
    set_vars: dict[str, str]      # 设置变量
    config: dict[str, Any]
```

### 5.2 RequestNode

```python
@dataclass
class RequestNode:
    method: str
    url: str
    headers: dict[str, str]
    params: dict[str, str]
    json: dict[str, Any] | None
    form: dict[str, str] | None
    multipart: dict[str, str] | None
    body: str | None
    content_type: str | None
```

### 5.3 AssertionNode

```python
@dataclass
class AssertionNode:
    op: str      # eq / ne / gt / lt / gte / lte / contains
    left: str    # 表达式（由 executor 解释）
    right: Any   # 期望值
```

---

## 6. 核心模块

### 6.1 Parser（DSL → AST）

**职责：**
- 加载 YAML/JSON 文件
- 校验 DSL 格式
- 解析为 AST（StepNode, RequestNode 等）

**Action 注册表：**
```python
SUPPORTED_ACTIONS = {"request"}

def register_action(action_type: str) -> None:
    """注册新的 action 类型"""
    SUPPORTED_ACTIONS.add(action_type)
```

### 6.2 Context（变量系统）

**职责：**
- 管理全局变量和提取的变量
- 渲染 `${var}` 语法

```python
class Context:
    def set(self, key: str, value: Any) -> None: ...
    def get(self, key: str) -> Any | None: ...
    def render(self, value: Any) -> Any: ...
    def render_dict(self, data: dict) -> dict: ...
```

### 6.3 Planner（DAG 规划）

**职责：**
- 构建依赖图
- 检测循环依赖
- 拓扑排序

```python
def build_graph(testcase: TestCase) -> dict[str, list[str]]: ...
def detect_cycle(graph: dict[str, list[str]]) -> None: ...
def get_execution_order(graph: dict[str, list[str]]) -> list[list[str]]: ...
```

### 6.4 Scheduler（调度器）

**职责：**
- 状态机驱动的 DAG 调度
- 并发控制（asyncio.Semaphore）
- 重试逻辑

**Executor 注册表：**
```python
EXECUTOR_REGISTRY = {
    "request": {
        "execute": execute_request,
        "extract": extract_variables,
        "validate": validate_response,
    },
}

def register_executor(action_type, execute_fn, extract_fn, validate_fn) -> None:
    """注册新的 executor"""
    EXECUTOR_REGISTRY[action_type] = {
        "execute": execute_fn,
        "extract": extract_fn,
        "validate": validate_fn,
    }
```

### 6.5 Executor（执行器）

**Protocol 定义：**
```python
class Executor(Protocol):
    async def execute(self, action_config: dict, ctx: Context) -> dict: ...
    def extract(self, result: dict, config: dict, ctx: Context) -> dict: ...
    def validate(self, result: dict, assertions: list) -> list[str]: ...
```

### 6.6 DB 执行器

支持 PostgreSQL、MySQL、SQLite 三种数据库。

**DSL 示例：**
```yaml
vars:
  pg_url: postgres://user:pass@localhost:5432/mydb

steps:
  query_user:
    db:
      url: ${pg_url}
      query: SELECT * FROM users WHERE id = $1
      params: [${user_id}]
    extract:
      username: $.rows[0].name
    validate:
      - eq: [$.row_count, 1]
```

**结果格式：**
```python
{
    "rows": [{"id": 1, "name": "Alice"}, ...],
    "row_count": 1,
    "columns": ["id", "name"],
}
```

**支持的 URL 格式：**
- PostgreSQL: `postgres://user:pass@host:5432/dbname`
- MySQL: `mysql://user:pass@host:3306/dbname`
- SQLite: `sqlite:///path/to/db.sqlite`

---

## 7. 状态机设计

### 状态流转

```text
PENDING → RUNNING → SUCCESS
                   ↘
                    FAILED → RETRYING → RUNNING
                   ↘
                    SKIPPED
```

### 状态定义

```python
class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
```

---

## 8. 项目结构

```text
nextgen/
├── cli.py              # CLI 入口
├── core/
│   ├── model.py        # AST 模型（StepNode, RequestNode 等）
│   ├── context.py      # 变量系统
│   ├── planner.py      # DAG 规划
│   ├── condition.py    # 条件评估器
│   ├── protocol.py     # Action/Executor 协议定义
│   └── scheduler.py    # 调度器（executor 注册表）
├── parser/
│   └── loader.py       # YAML/JSON 解析（action 注册表）
├── executors/
│   ├── http/           # HTTP 执行器
│   │   ├── __init__.py
│   │   ├── client.py   # 请求发送
│   │   ├── extract.py  # 变量提取
│   │   ├── validate.py # 断言验证
│   │   └── utils.py    # 工具函数
│   └── db/             # DB 执行器
│       ├── __init__.py
│       ├── client.py   # 查询执行（路由）
│       ├── extract.py  # 变量提取
│       ├── validate.py # 结果验证
│       └── drivers/    # 数据库驱动
│           ├── postgres.py
│           ├── mysql.py
│           └── sqlite.py
└── reporter/
    └── json_reporter.py
```

---

## 9. 扩展新 Action 类型

```python
# 1. 实现 executor 函数
async def execute_db(action_config: dict, ctx: Context) -> dict:
    ...

def extract_db(result: dict, config: dict, ctx: Context) -> dict:
    ...

def validate_db(result: dict, assertions: list) -> list[str]:
    ...

# 2. 注册
from nextgen.parser.loader import register_action, register_action_validator
from nextgen.core.scheduler import register_executor

register_action("db")
register_action_validator("db", validate_db_config)
register_executor("db", execute_db, extract_db, validate_db)
```

---

## 10. CLI 使用

```bash
# 基本执行
nextgen run demo.yaml

# 指定并发数
nextgen run demo.yaml --parallel=5

# 显示详细日志
nextgen run demo.yaml --verbose

# 支持 JSON 格式
nextgen run demo.json
```

---

## 11. 迭代路线

### 已完成

* [x] DSL 解析（YAML/JSON）
* [x] AST 模型
* [x] DAG 调度
* [x] HTTP 执行器
* [x] 变量系统
* [x] 断言系统
* [x] 重试机制
* [x] 并发控制
* [x] JSON 报告
* [x] CLI 工具
* [x] Executor 注册表架构

### 待实现

* [ ] DB 执行器
* [ ] Python 执行器
* [ ] 指数退避重试
* [ ] 超时配置
* [ ] fail-fast 策略
* [ ] 彩色终端报告
* [ ] HTML 报告
* [ ] 分布式执行

---

## 12. 关键设计原则

* **DSL ≠ 执行逻辑**：DSL 只描述"做什么"，不描述"怎么做"
* **AST ≠ Runtime**：AST 是静态描述，Runtime 是动态执行
* **Scheduler ≠ Executor**：Scheduler 负责调度，Executor 负责执行
* **一切围绕 DAG**：依赖关系是核心，驱动执行顺序
* **开闭原则**：新增 Action 类型不需要修改现有代码
