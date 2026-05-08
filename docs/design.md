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

* **变量作用域**：`set_vars` 和大部分 step hook 默认只在当前步骤内可见，`extract` 声明的变量会回写全局上下文
* **断言操作符**：基础比较（eq / ne / gt / lt / gte / lte）+ contains
* **报告格式**：JSON 输出到 stdout
* **DSL 格式**：支持 YAML 和 JSON 两种格式
* **Executor / Hook 架构**：注册表模式，支持扩展 action 和自定义 hook

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

### 4.1 执行模式（mode）

支持两种执行模式：

```yaml
version: 1
mode: sequential  # 默认值，可省略

steps:
  login:
    request: ...
  get_user:
    request: ...      # 自动依赖 login
  get_order:
    request: ...      # 自动依赖 get_user
```

| 模式 | 行为 |
|------|------|
| `sequential`（默认） | 无 `depends_on` 则按定义顺序串行 |
| `parallel` | 无 `depends_on` 则可并行执行 |

**显式依赖优先：**
```yaml
mode: sequential

steps:
  login:
    request: ...
  get_user:
    request: ...           # 自动依赖 login
  independent_task:
    depends_on: [login]    # 显式依赖，覆盖自动顺序
    request: ...
```

**适用场景：**
- API 测试：`parallel`（独立步骤可并行）
- UI 自动化：`sequential`（步骤必须顺序执行）

### 4.2 完整示例

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
    set_vars:
      request_user: admin
    request: ...
    extract:
      token: $.data.token  # 声明导出到全局上下文
      csrf:
        regex: 'csrf=([a-z0-9]+)'
        group: 1

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
- `{jsonpath: "$.data.token"}` — JSONPath 显式写法
- `{regex: "token=([a-z0-9]+)", group: 1}` — 正则提取，使用 Python `re.search`
- `default` — 可选，未匹配或提取失败时使用默认值

**作用域规则：**
- `vars`、`before_all` 写入、历史步骤 `extract` 的结果存在于全局上下文
- `set_vars` 默认只在当前步骤内可见
- `before_each` / `before` / `after` / `after_each` 默认操作当前步骤上下文
- `extract` 声明的变量在步骤成功后提交到全局上下文，供后续步骤使用

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
  - contains: [$.message, success]      # 包含
  - not_contains: [$.message, error]    # 不包含
  - starts_with: [$.name, user_]        # 以前缀开头
  - ends_with: [$.file, .json]          # 以后缀结尾
  - matches: [$.email, "^[^@]+@[^@]+$"] # 正则匹配

  # 集合
  - in: [$.status, [active, pending]]   # 在候选列表中
  - not_in: [$.role, [banned]]          # 不在候选列表中

  # 长度
  - len_eq: [$.items, 3]
  - len_ne: [$.items, 0]
  - len_gt: [$.items, 0]
  - len_lt: [$.items, 10]
  - len_gte: [$.items, 1]
  - len_lte: [$.items, 100]
```

`matches` 使用 Python 标准库 `re.search` 语义；如果需要整串匹配，请在正则中显式使用 `^` / `$`。

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
      timeout: 30           # 步骤总超时（秒），包含 retry 和 hook
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
      timeout: 30         # 步骤总超时（秒），包含 hook / retry / 等待时间
      retry: 3
```

**说明：**
- `request.timeout` 只作用于单次请求
- `config.timeout` 作用于整个步骤生命周期
- 步骤总超时覆盖：`before_each -> set_vars -> when -> before -> action -> validate -> extract -> after -> after_each`

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
- `when` 可使用同一步 `set_vars` 产生的变量
- SKIPPED 的步骤不会执行 action / validate / extract / step hooks
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
3. `before` — 执行步骤前 hook
4. `request` / `db` — 执行 action
5. `validate` — 验证结果
6. `extract` — 提取变量并提交声明导出变量
7. `after` — 执行步骤后 hook

**作用域说明：**
- `set_vars` 默认只对当前步骤可见
- 跨步骤复用数据时，应通过 `extract` 显式导出变量

### 4.9 Hook 系统

支持 testcase 级和 step 级 hook：

```yaml
version: 1

hooks:
  before_all:
    - log: "suite start"
  after_all:
    - log: "suite end"
  before_each:
    - log: "step start"
  after_each:
    - log: "step end"

steps:
  login:
    request:
      method: POST
      url: ${base_url}/post
    hooks:
      before:
        - getRandomStr: { var: "request_id", length: 12 }
      after:
        - log: "request_id=${request_id}"
```

**支持的 hook 层级：**
- testcase 级：`before_all` / `after_all` / `before_each` / `after_each`
- step 级：`before` / `after`

**内置 hook：**
- `sleep`
- `log`
- `getTimestamp`
- `getTimeStr`
- `getRandomStr`

**步骤内完整顺序：**

```text
before_each -> set_vars -> when -> before -> action -> validate -> extract -> after -> after_each
```

**retry 语义：**
- `before_each` / `after_each`：每个步骤只执行一次
- `before` / `after`：每次 attempt 执行一次

**自定义 hook：**
- 用户可在 `hooks.py` 中通过 `from nextgen import register_hook` 注册
- 运行时会从 testcase 所在目录向上扫描到当前工作目录，按从外到内顺序加载

---

## 5. AST 设计

### 5.1 StepNode

```python
@dataclass
class ActionNode:
    type: str
    config: Any


@dataclass
class StepNode:
    name: str
    action: ActionNode
    depends_on: list[str]
    extract: dict[str, Any]
    validate: list[AssertionNode]
    when: list | dict | None      # 条件执行（list=AND, dict=and/or）
    set_vars: dict[str, str]      # 设置变量
    config: dict[str, Any]
    hooks: StepHooks
```

### 5.2 AssertionNode

```python
@dataclass
class AssertionNode:
    op: str      # eq / ne / gt / lt / gte / lte / contains
    left: str    # 表达式（由 executor 解释）
    right: Any   # 期望值
```

### 5.3 HookAction / Hooks

```python
@dataclass
class HookAction:
    type: str
    params: dict[str, Any]


@dataclass
class StepHooks:
    before: list[HookAction]
    after: list[HookAction]


@dataclass
class TestCaseHooks:
    before_all: list[HookAction]
    after_all: list[HookAction]
    before_each: list[HookAction]
    after_each: list[HookAction]
```

### 5.4 TestCase

```python
@dataclass
class TestCase:
    version: int
    steps: dict[str, StepNode]
    vars: dict[str, Any]
    mode: str = "sequential"  # "sequential" | "parallel"
    hooks: TestCaseHooks = field(default_factory=TestCaseHooks)
    source_path: str | None = None
```

---

## 6. 核心模块

### 6.1 Parser（DSL → AST）

**职责：**
- 加载 YAML/JSON 文件
- 校验 DSL 格式
- 解析为通用 AST（StepNode, TestCase 等）

**Action 注册表：**
```python
@dataclass(frozen=True)
class ActionSpec:
    name: str
    parse_config: ActionParseConfig
    execute: ActionExecute
    extract: ActionExtract
    validate: ActionValidate
    summarize: ActionSummarize

def register_action(spec: ActionSpec) -> None: ...
def get_action(name: str) -> ActionSpec | None: ...
```

### 6.2 Context（变量系统）

**职责：**
- 管理全局变量和提取的变量
- 渲染 `${var}` 语法

```python
class Context:
    def set(self, key: str, value: Any) -> None: ...
    def get(self, key: str) -> Any | None: ...
    def snapshot(self) -> dict[str, Any]: ...
    def derive(self, initial: dict[str, Any] | None = None) -> "Context": ...
    def merge(self, updates: dict[str, Any]) -> None: ...
    def render(self, value: Any) -> Any: ...
    def render_dict(self, data: dict) -> dict: ...
```

调度器运行时会基于全局上下文派生步骤局部上下文，以支持：
- `set_vars` 和 step hooks 的局部可见性
- `extract` 成功后再回写全局上下文

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
- hook 生命周期调度
- 自动发现并加载 `hooks.py`

Scheduler 从 Action 注册表读取 `execute / extract / validate / summarize`，不再维护独立执行器注册表。

### 6.5 Hooks（hook 注册表）

```python
HOOK_REGISTRY: dict[str, HookHandler] = {}

def register_hook(name: str): ...
def get_hook(name: str): ...
def discover_hooks(testcase_path: str | Path, cwd: str | Path) -> list[Path]: ...
def load_discovered_hooks(testcase_path: str | Path, cwd: str | Path) -> list[Path]: ...
```

### 6.6 Action（执行器）

**Protocol 定义：**
```python
class Action(Protocol):
    def parse_config(self, raw: dict[str, Any]) -> Any: ...
    async def execute(self, config: Any, ctx: Context) -> dict: ...
    def extract(self, result: dict, config: dict, ctx: Context) -> dict: ...
    def validate(self, result: dict, assertions: list) -> list[str]: ...
    def summarize(self, config: Any) -> str: ...
```

### 6.7 DB 执行器

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
│   ├── model.py        # 通用 AST 模型（StepNode, TestCase 等）
│   ├── context.py      # 变量系统
│   ├── planner.py      # DAG 规划
│   ├── condition.py    # 条件评估器
│   ├── hooks.py        # hook 注册表与发现逻辑
│   └── scheduler.py    # 调度器（action 注册表）
├── parser/
│   └── loader.py       # YAML/JSON 解析（action 注册表）
├── executors/
│   ├── http/           # HTTP 执行器
│   │   ├── __init__.py
│   │   ├── client.py   # 请求发送
│   │   ├── model.py    # HTTP action 内部模型
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
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DbConfig:
    url: str
    query: str
    params: list[Any] = field(default_factory=list)


# 1. 实现 action 函数
def parse_db_config(raw: dict[str, Any]) -> DbConfig:
    ...

async def execute_db(config: DbConfig, ctx: Context) -> dict:
    ...

def extract_db(result: dict, config: dict, ctx: Context) -> dict:
    ...

def validate_db(result: dict, assertions: list) -> list[str]:
    ...

def summarize_db(config: DbConfig) -> str:
    ...

# 2. 注册
from nextgen import ActionSpec, register_action

register_action(ActionSpec(
    name="db",
    parse_config=parse_db_config,
    execute=execute_db,
    extract=extract_db,
    validate=validate_db,
    summarize=summarize_db,
))
```

---

## 10. CLI 使用

```bash
# 基本执行
nextgen demo.yaml

# 指定并发数
nextgen demo.yaml --parallel=5

# 显示详细日志
nextgen demo.yaml --verbose

# 支持 JSON 格式
nextgen demo.json
```

也可以通过 `uv` 运行：

```bash
uv run nextgen demo.yaml
```

---

## 11. 迭代路线

### 已完成

* [x] DSL 解析（YAML/JSON）
* [x] AST 模型
* [x] DAG 调度
* [x] HTTP 执行器
* [x] DB 执行器
* [x] 变量系统
* [x] 断言系统
* [x] 重试机制
* [x] 并发控制
* [x] JSON 报告
* [x] CLI 工具
* [x] Action 注册表架构
* [x] Hook 系统（内置 + 自定义）
* [x] 超时配置
* [x] 指数退避重试

### 待实现

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
