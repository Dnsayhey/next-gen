# Hook 功能规划

## 0. 实现前置条件

在实现 hook 之前，建议先完成两项基础收敛，否则 hook 语义会和当前运行时行为持续打架：

1. `sequential` 模式真正落到运行时。
   当前 `planner` 会为 `sequential` 推导自动依赖，但 `Scheduler` 实际只读取 `StepNode.depends_on`。如果不先把自动依赖写回运行时，hook 的“前序步骤”定义在默认串行模式下也不成立。
2. 统一步骤内部真实执行顺序。
   hook 方案以下面这个顺序为准：
   `before_each -> set_vars -> when -> before -> action -> validate -> extract -> after -> after_each`

本文档基于以上前提设计。

## 1. 设计目标

为 DSL 提供两类 hook 能力：

- 用例级 hook：在整个 testcase 的开始、结束，以及每个步骤前后执行
- 步骤级 hook：在单个步骤的 action 前后执行

hook 是执行流程的一部分，不是旁路能力。hook 失败会影响步骤或用例结果，不做静默吞错。

## 2. 钩子层级

```text
全局钩子（testcase 级别）
├── before_all:    整个用例开始前（执行一次）
├── after_all:     整个用例结束后（执行一次）
├── before_each:   每个步骤开始前
└── after_each:    每个步骤结束后

步骤钩子（step 级别）
├── before:        当前步骤 action 前
└── after:         当前步骤 extract 后
```

说明：

- 所有 hook 在 `sequential` 和 `parallel` 模式下都生效
- `before_all` 和 `after_all` 总是只执行一次
- `before_each`、`after_each`、`before`、`after` 都属于步骤协程内部逻辑
- `after` 明确定义为“步骤最终 hook”，位于 `validate` 和 `extract` 之后

## 3. 执行顺序

### 3.1 Sequential 模式

```text
before_all
  ↓
before_each -> set_vars -> when -> before -> [action] -> validate -> extract -> after -> after_each   (step 1)
before_each -> set_vars -> when -> before -> [action] -> validate -> extract -> after -> after_each   (step 2)
before_each -> set_vars -> when -> before -> [action] -> validate -> extract -> after -> after_each   (step 3)
  ↓
after_all
```

### 3.2 Parallel 模式

```text
before_all
  ↓
┌─ before_each -> set_vars -> when -> before -> [action] -> validate -> extract -> after -> after_each ─┐
├─ before_each -> set_vars -> when -> before -> [action] -> validate -> extract -> after -> after_each ─┤
└─ before_each -> set_vars -> when -> before -> [action] -> validate -> extract -> after -> after_each ─┘
  ↓
after_all
```

说明：

- `before_each` 到 `after_each` 的整段逻辑都在单个步骤协程内执行
- 并行模式下，一个步骤中的 `sleep` 不会阻塞其他步骤
- `after_all` 在全部步骤协程结束后执行

## 4. 变量作用域与可见性

当前项目已经有共享 `Context`，但 hook 上线后建议引入两层上下文：

- `global ctx`：用例级共享变量
- `step ctx`：当前步骤局部变量视图，读取时先查局部，再查全局

建议规则：

- `vars`、前置步骤 `extract` 结果、`before_all` 写入内容进入 `global ctx`
- `set_vars` 默认写入 `step ctx`
- `before_each`、`before` 默认写入 `step ctx`
- `extract` 结果先写入 `step ctx`，步骤成功后再按规则提交到 `global ctx`
- `after` 能看到当前步骤 `extract` 的结果

### 4.1 可见性矩阵

| hook/阶段 | 可读取变量 |
|-----------|-----------|
| `before_all` | 全局 `vars` |
| `before_each` | `global ctx` |
| `set_vars` 后的 `when` | `global ctx` + 当前步骤 `set_vars` |
| `before` | `global ctx` + 当前步骤 `set_vars` + `before_each`/`before` 已写入变量 |
| `action`/`validate` | `global ctx` + 当前步骤局部变量 |
| `extract` 后的 `after` | `global ctx` + 当前步骤局部变量 + 当前步骤 `extract` |
| `after_each` | `global ctx` + 当前步骤局部变量 |
| `after_all` | 最终 `global ctx` |

### 4.2 提交规则

为避免 parallel 下变量互相踩踏，建议采用下面的提交语义：

- `before_all`：直接写入 `global ctx`
- `before_each` / `before` / `set_vars`：默认只写 `step ctx`
- `extract`：步骤成功后，把配置中声明要导出的变量从 `step ctx` 提交到 `global ctx`
- `after` / `after_each`：
  - 默认只写 `step ctx`
  - 如果后续确实需要“显式写全局”，建议后续单独扩展 `ctx.set_global()`，不要默认全部提升到全局
- `after_all`：可读最终上下文，写入通常无实际意义

这样可以保证：

- sequential 下语义自然
- parallel 下不会因为两个步骤同时 `ctx.set("token", ...)` 产生不可预测覆盖
- “后续步骤可见的变量”只来自显式导出的结果，而不是所有 hook 临时变量

## 5. 条件执行与 hook 的关系

执行顺序固定为：

```text
before_each -> set_vars -> when -> before -> [action] -> validate -> extract -> after -> after_each
```

规则如下：

- `when` 不满足时，步骤标记为 `SKIPPED`
- `when` 不满足时，不执行 `before`、`action`、`validate`、`extract`、`after`
- `before_each` 和 `after_each` 仍然执行

即：

```text
before_each -> set_vars -> when(不满足) -> after_each
before_each -> set_vars -> when(满足) -> before -> [action] -> validate -> extract -> after -> after_each
```

## 6. 参数格式

支持简写和完整格式：

```yaml
hooks:
  before:
    - sleep: 2
    - log: "简单日志"
    - getTimestamp: start_time

    - log: { level: "info", message: "请求开始" }
    - getTimestamp: { var: "start_time" }
    - getRandomStr: { var: "request_id", length: 16 }
```

解析规则：

- hook 列表中的每一项必须是“单 key dict”
- 值为非 `dict` 时，转换为标准参数格式
- 值为 `dict` 时，直接作为参数

建议标准化结果：

```python
HookAction(type="sleep", params={"seconds": 2})
HookAction(type="log", params={"message": "简单日志"})
HookAction(type="getTimestamp", params={"var": "start_time"})
```

## 7. 内置操作

| 操作 | 简写 | 完整格式 | 说明 |
|------|------|----------|------|
| `sleep` | `sleep: 2` | `sleep: { seconds: 2 }` | 等待指定秒数 |
| `log` | `log: "msg"` | `log: { level: "info", message: "msg" }` | 输出日志 |
| `getTimestamp` | `getTimestamp: var` | `getTimestamp: { var: "var" }` | 获取毫秒时间戳 |
| `getTimeStr` | `getTimeStr: var` | `getTimeStr: { var: "var", format: "%Y-%m-%d %H:%M:%S" }` | 获取格式化时间 |
| `getRandomStr` | `getRandomStr: var` | `getRandomStr: { var: "var", length: 8 }` | 获取指定长度随机字符串 |

实现建议：

- `sleep` -> `asyncio.sleep(seconds)`
- `log` -> 根据 `level` 调用 `logger`
- `getTimestamp` -> `int(time.time() * 1000)`
- `getTimeStr` -> `datetime.now().strftime(format)`
- `getRandomStr` -> 按 `length` 生成，不要固定 `token_hex(4)`

## 8. 失败处理

### 8.1 基本规则

| 场景 | 行为 |
|------|------|
| `before_all` 失败 | 用例直接中止，全部未开始步骤不执行 |
| `after_all` 失败 | 记录错误，标记 testcase 失败 |
| `before_each` 失败 | 当前步骤失败，跳过后续阶段 |
| `before` 失败 | 当前步骤失败，跳过 `action` 及其后续阶段 |
| `action` 失败 | 进入现有 retry/failed 逻辑 |
| `validate` 失败 | 当前步骤失败，不执行 `extract` / `after`，但执行 `after_each` |
| `extract` 失败 | 当前步骤失败，不执行 `after`，但执行 `after_each` |
| `after` 失败 | 当前步骤失败，仍执行 `after_each` |
| `after_each` 失败 | 当前步骤失败 |

建议原则：

- `after_each` 尽量作为 finally 语义处理，只要 `before_each` 已经开始，就应该尝试执行
- `after_all` 也应尽量作为 testcase finally 语义处理

### 8.2 与 retry 的关系

建议明确为“attempt 级”语义：

- `before_each` / `after_each`：每次步骤最终执行只跑一次，不随 retry 重复
- `before` / `after`：每次 attempt 都执行一次
- `action` 失败进入重试时，下一次 attempt 重新走：
  `before -> action -> validate -> extract -> after`

这样比较符合直觉：

- `before_each` 适合申请步骤级资源
- `before` 适合构造单次请求数据
- `after` 适合记录单次 attempt 的结果

### 8.3 与 timeout 的关系

建议把 timeout 分成两个层次并写清楚：

- `request.timeout`：底层请求超时
- `step.config.timeout`：整个步骤总超时，覆盖 `before_each` 到 `after_each`，并包含全部 retry

也就是说，step timeout 应计入：

- hook 执行时间
- action 执行时间
- retry 等待时间

否则用户很难理解“步骤超时”到底包不包括 hook。

## 9. DSL 示例

```yaml
version: 1

vars:
  base_url: https://httpbin.org

hooks:
  before_all:
    - log: "测试开始"
    - getTimestamp: suite_start

  after_all:
    - getTimestamp: suite_end
    - log: "测试结束"

  before_each:
    - log: "准备执行步骤"

  after_each:
    - log: "步骤结束"

steps:
  login:
    set_vars:
      user: admin
    request:
      method: POST
      url: ${base_url}/post
      json: { user: ${user} }
    hooks:
      before:
        - getRandomStr: { var: "request_id", length: 16 }
        - log: "执行登录: ${user}, request_id=${request_id}"
      after:
        - log: "登录结束, token=${token}"
    extract:
      token: $.json.user
    validate:
      - eq: [$.json.user, admin]
```

## 10. 数据结构设计

```python
@dataclass
class HookAction:
    type: str
    params: dict[str, Any]


@dataclass
class TestCaseHooks:
    before_all: list[HookAction] = field(default_factory=list)
    after_all: list[HookAction] = field(default_factory=list)
    before_each: list[HookAction] = field(default_factory=list)
    after_each: list[HookAction] = field(default_factory=list)


@dataclass
class StepHooks:
    before: list[HookAction] = field(default_factory=list)
    after: list[HookAction] = field(default_factory=list)


@dataclass
class StepNode:
    ...
    hooks: StepHooks = field(default_factory=StepHooks)


@dataclass
class TestCase:
    ...
    hooks: TestCaseHooks = field(default_factory=TestCaseHooks)
    source_path: str | None = None
```

补充建议：

- `source_path` 用于 hook discovery
- 如果后续引入局部上下文，可以在运行时新增 `StepContext`，不必急着进 AST

## 11. 实现拆分

### 11.1 第一阶段：先补运行时前置条件

- 让 `sequential` 自动依赖真正进入 `Scheduler`
- 重排步骤内部顺序为：
  `before_each -> set_vars -> when -> before -> action -> validate -> extract -> after -> after_each`
- 梳理 retry/timeout 的真实边界

这一阶段不引入 DSL hook，也值得单独提交。

### 11.2 第二阶段：模型与解析

- `model.py`
  - 新增 `HookAction`
  - 新增 `TestCaseHooks`
  - 新增 `StepHooks`
  - `TestCase` 增加 `hooks`、`source_path`
  - `StepNode` 增加 `hooks`
- `loader.py`
  - 新增 `parse_hook_action()`
  - 新增 `parse_step_hooks()` / `parse_testcase_hooks()`
  - `load_testcase()` 把文件路径写入 `source_path`

### 11.3 第三阶段：执行器

- 新增 `nextgen/core/hooks.py`
  - hook 注册表
  - 内置 hook 注册
  - `register_hook()` 装饰器
- `scheduler.py`
  - 新增 `HookExecutor`
  - 在 testcase/step 生命周期中接入 hook
  - 明确 `after_each` / `after_all` 的 finally 行为
- `context.py`
  - 增加局部上下文能力，或通过 overlay 实现 step 级作用域

### 11.4 第四阶段：hook 发现

- `discover_hooks(testcase.source_path, cwd)`
- 从用例目录向上扫描到运行时 cwd
- 加载顺序从外到内，内层覆盖外层

### 11.5 第五阶段：测试

至少补这些测试：

- `tests/parser/test_loader.py`
  - hook 简写/完整格式解析
  - 非法 hook 格式报错
- `tests/core/test_scheduler_hooks.py`
  - sequential 顺序
  - parallel 下 hook 独立执行
  - `when` skip 路径
  - hook failure 路径
  - retry 与 hook 的关系
  - timeout 覆盖 hook 和 retry
- `tests/core/test_context.py`
  - global/step 作用域
  - extract 提交规则
- `tests/core/test_hook_registry.py`
  - 内置 hook
  - 自定义 hook 覆盖
- `tests/core/test_hook_discovery.py`
  - 多层 `hooks.py` 加载顺序

## 12. 自定义 Hook 注册

### 12.1 注册方式

```python
from nextgen import register_hook


@register_hook("setup_db")
async def setup_db(ctx, params):
    db_url = ctx.get("db_url")
    ...


@register_hook("cleanup")
async def cleanup(ctx, params):
    ...
```

DSL 中按名称引用：

```yaml
hooks:
  before_all:
    - setup_db: { env: "staging" }
  after_all:
    - cleanup: {}
```

### 12.2 发现规则

规则：

- 从 testcase 文件所在目录开始向上扫描 `hooks.py`
- 扫描上界是运行命令时的 cwd
- 加载顺序从外到内，越靠近 testcase 的 `hooks.py` 优先级越高

示例：

```text
my_project/
├── hooks.py
├── testcases/
│   ├── hooks.py
│   └── api/
│       ├── hooks.py
│       └── login.yaml
```

在 `my_project` 下执行 `nextgen run testcases/api/login.yaml` 时，加载顺序应为：

1. `my_project/hooks.py`
2. `my_project/testcases/hooks.py`
3. `my_project/testcases/api/hooks.py`

同名 hook 以后加载者覆盖先加载者。

## 13. 扩展性

后续可支持第三方包通过 entry points 注册 hook：

```toml
[project.entry-points."nextgen.hooks"]
my_plugin = "my_plugin.hooks"
```

启动时加载：

```python
for ep in importlib.metadata.entry_points(group="nextgen.hooks"):
    plugin = ep.load()
    plugin.register()
```

这部分不建议放进第一版实现，先把单项目内的 `hooks.py` 路径跑通更重要。
