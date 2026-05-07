# Hook 功能规划

## 1. 钩子层级

```
全局钩子（testcase 级别）
├── before_all:    整个用例开始前（执行一次）
├── after_all:     整个用例结束后（执行一次）
├── before_each:   每个步骤执行前
├── after_each:    每个步骤执行后

步骤钩子（step 级别）
├── before:        当前步骤执行前
├── after:         当前步骤执行后
```

**说明：** 所有钩子在 sequential 和 parallel 模式下均生效。parallel 模式下，`before_each`/`after_each`/`before`/`after` 在每个步骤的协程中独立执行，不会阻塞其他步骤。

## 2. 执行顺序

### Sequential 模式

```
before_all
  ↓
before_each → set_vars → when → before → [action] → after → validate → extract → after_each   (step 1)
before_each → set_vars → when → before → [action] → after → validate → extract → after_each   (step 2)
before_each → set_vars → when → before → [action] → after → validate → extract → after_each   (step 3)
  ↓
after_all
```

### Parallel 模式

```
before_all
  ↓
┌─ before_each → set_vars → when → before → [action] → after → validate → extract → after_each ─┐
├─ before_each → set_vars → when → before → [action] → after → validate → extract → after_each ─┤  （并行执行）
└─ before_each → set_vars → when → before → [action] → after → validate → extract → after_each ─┘
  ↓
after_all
```

**说明：** `before_each`/`after_each` 在每个步骤的协程中独立执行，sleep 等操作不会阻塞其他步骤。

## 3. 变量可见性

钩子内可通过 `${var}` 语法引用变量，执行时通过 `ctx.render()` 渲染。

| 钩子 | 可访问的变量 |
|------|-------------|
| `before_all` | 全局 `vars` |
| `after_all` | 全局 `vars` + 所有提取的变量 |
| `before_each` | 全局 `vars` + 前序步骤提取的变量 |
| `after_each` | 全局 `vars` + 前序步骤提取的变量 |
| `before` | 全局 `vars` + 前序步骤提取的变量 + 当前步骤 `set_vars` |
| `after` | 全局 `vars` + 前序步骤提取的变量 + 当前步骤 `set_vars` + 当前步骤 `extract` |

## 4. 参数格式

支持简写和完整格式：

```yaml
hooks:
  before:
    # 单参数简写
    - sleep: 2
    - log: "简单日志"
    - getTimestamp: start_time

    # 多参数完整格式
    - log: { level: "info", message: "请求开始" }
    - getTimestamp: { var: "start_time" }
    - getRandomStr: { var: "request_id", length: 16 }
```

**解析规则：**
- 值为非 dict → 转为标准 dict 格式
- 值为 dict → 直接使用

## 5. 内置操作

| 操作 | 简写 | 完整格式 | 说明 |
|------|------|----------|------|
| `sleep` | `sleep: 2` | `sleep: { seconds: 2 }` | 等待指定秒数 |
| `log` | `log: "msg"` | `log: { level: "info", message: "msg" }` | 输出日志 |
| `getTimestamp` | `getTimestamp: var` | `getTimestamp: { var: "var" }` | 获取时间戳（毫秒） |
| `getTimeStr` | `getTimeStr: var` | `getTimeStr: { var: "var" }` | 获取时间字符串 |
| `getRandomStr` | `getRandomStr: var` | `getRandomStr: { var: "var", length: 8 }` | 获取随机字符串 |

## 6. 执行规则

### 6.1 Hook 失败处理

| 场景 | 行为 |
|------|------|
| 内置操作失败（如 sleep 被取消） | 抛出异常，当前步骤标记为 FAILED |
| 自定义 hook 抛出异常 | 抛出异常，当前步骤标记为 FAILED |
| `before_all` 失败 | 整个用例中止 |
| `after_all` 失败 | 记录错误，不影响已完成的结果 |
| `before` 失败 | 当前步骤标记为 FAILED，跳过 action |
| `after` 失败 | 当前步骤标记为 FAILED，跳过 validate/extract |
| `before_each` 失败 | 当前步骤标记为 FAILED，跳过后续流程 |
| `after_each` 失败 | 当前步骤标记为 FAILED |

**原则：** hook 是执行流程的一部分，失败即步骤失败，不做静默吞掉。

### 6.2 变量读写

Hook 函数通过 `ctx` 读写变量：

```python
@register_hook("gen_data")
async def gen_data(ctx, params):
    # 读变量
    env = ctx.get("env")
    # 写变量（后续步骤和 hook 可用 ${request_id}）
    ctx.set("request_id", "abc123")
```

**变量写入时机：**

| 钩子 | 可写入变量 | 何时生效 |
|------|-----------|----------|
| `before_all` | 全局变量 | 对所有步骤生效 |
| `before_each` | 全局变量 | 对当前步骤生效 |
| `before` | 全局变量 | 对当前步骤的 action、after、validate、extract 生效 |
| `after` | 全局变量 | 对后续步骤生效 |
| `after_each` | 全局变量 | 对后续步骤生效 |
| `after_all` | 全局变量 | 无实际意义（已无后续步骤） |

**注意：** 内置操作（`getTimestamp`、`getRandomStr` 等）通过 `params.var` 指定写入的变量名，本质也是调用 `ctx.set()`。

### 6.3 条件执行与 hook 的关系

执行顺序：`set_vars → when → before → [action]`

- `when` 条件不满足 → 步骤标记为 SKIPPED，`before`/`after` 均不执行
- `before_each`/`after_each` 无论条件是否满足都会执行（它们在条件判断之前/之后）

```
before_each → set_vars → when(不满足) → after_each   (SKIPPED)
before_each → set_vars → when(满足) → before → [action] → after → validate → extract → after_each
```

## 7. DSL 完整示例

```yaml
version: 1

vars:
  base_url: https://httpbin.org

hooks:
  before_all:
    - log: "测试开始"
    - getTimestamp: start_time

  after_all:
    - getTimestamp: end_time
    - log: "测试结束"

  before_each:
    - log: "准备执行步骤"

  after_each:
    - sleep: 1

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
        - log: "执行登录: ${user}"
        - getRandomStr: request_id
      after:
        - log: "登录完成, request_id: ${request_id}"
    extract:
      token: $.json.user
    validate:
      - eq: [$.json.user, admin]
```

## 8. 数据结构设计

### AST 模型

```python
@dataclass
class HookAction:
    """钩子动作"""
    type: str               # sleep / log / getTimestamp / getTimeStr / getRandomStr
    params: dict[str, Any]  # 参数（统一 dict 格式）

@dataclass
class TestCase:
    # ... 现有字段
    hooks: TestCaseHooks = field(default_factory=TestCaseHooks)

@dataclass
class TestCaseHooks:
    """用例级钩子"""
    before_all: list[HookAction] = field(default_factory=list)
    after_all: list[HookAction] = field(default_factory=list)
    before_each: list[HookAction] = field(default_factory=list)
    after_each: list[HookAction] = field(default_factory=list)

@dataclass
class StepNode:
    # ... 现有字段
    hooks: StepHooks = field(default_factory=StepHooks)

@dataclass
class StepHooks:
    """步骤级钩子"""
    before: list[HookAction] = field(default_factory=list)
    after: list[HookAction] = field(default_factory=list)
```

## 9. 实现步骤

### 9.1 模型层（model.py）
- 新增 `HookAction` 数据类
- 新增 `TestCaseHooks` 数据类
- 新增 `StepHooks` 数据类
- `TestCase` 添加 `hooks` 字段
- `StepNode` 添加 `hooks` 字段

### 9.2 解析层（loader.py）
- 新增 `parse_hook_action()` 解析单个钩子动作
- 新增 `parse_hooks()` 解析钩子列表
- 更新 `parse_step()` 解析步骤钩子
- 更新 `parse_testcase()` 解析全局钩子

### 9.3 执行层（scheduler.py）
- 新增 `HookExecutor` 类执行钩子动作
- 内置操作实现：
  - `sleep` → `asyncio.sleep()`
  - `log` → `logger.info()`
  - `getTimestamp` → `int(time.time() * 1000)`
  - `getTimeStr` → `datetime.now().strftime()`
  - `getRandomStr` → `secrets.token_hex(4)`
- 更新 `Scheduler.run()` 执行 `before_all`/`after_all`
- 更新 `Scheduler.run_step()` 执行 `before_each`/`after_each`/`before`/`after`

### 9.4 自定义 hooks（hooks.py）
- 新增 `register_hook()` 装饰器和注册表
- 新增 `discover_hooks()` 从用例目录向上扫描到 CWD
- 新增 `_load_hooks_module()` 动态导入 hooks.py
- 内置 hook 与自定义 hook 统一注册表，名称冲突时自定义优先
- `register_hook` 导出到 `nextgen.__init__`，用户 `from nextgen import register_hook`

### 9.5 单元测试
- `test_model.py` — 测试新数据类
- `test_loader.py` — 测试钩子解析
- `test_hook.py` — 测试钩子执行
- `test_hook_discovery.py` — 测试 hooks.py 发现和加载

### 9.6 文档和示例
- 更新 `design.md`
- 新增 `examples/hook_demo.yaml`

## 10. 自定义 Hooks 注册

### 10.1 注册方式

用户通过装饰器注册自定义 hook：

```python
# hooks.py
from nextgen import register_hook

@register_hook("setup_db")
async def setup_db(ctx, params):
    db_url = ctx.get("db_url")
    # 初始化数据库连接...

@register_hook("cleanup")
async def cleanup(ctx, params):
    # 清理资源...
```

DSL 中按名称引用：

```yaml
hooks:
  before_all:
    - setup_db: { env: "staging" }
  after_all:
    - cleanup: {}
```

### 10.2 hooks.py 自动发现

**规则：** CWD 为项目顶层，从用例目录向上逐级扫描 `hooks.py`，到 CWD 为止。

```
my_project/                    # CWD，扫描上界
├── hooks.py                   # ✓ 加载
├── testcases/
│   ├── hooks.py               # ✓ 加载
│   └── api/
│       ├── hooks.py           # ✓ 加载
│       └── login.yaml         # 用例，从这里开始往上找
```

执行 `cd my_project && nextgen run testcases/api/login.yaml`：

```
1. testcases/api/hooks.py  → 加载
2. testcases/hooks.py      → 加载
3. hooks.py                → 加载
4. 已到 CWD，停止
```

**特点：**
- 零配置，放对位置就生效
- 外层 hooks 全局生效，内层 hooks 局部生效
- 同名 hook 内层覆盖外层
- CWD 即项目顶层，用户 `cd` 到项目根目录执行即可

### 10.3 内置 hook 与自定义 hook 的关系

| 类型 | 定义方式 | 引用方式 |
|------|----------|----------|
| 内置 | 引擎内置 | 直接用名称：`sleep: 2` |
| 自定义 | `hooks.py` 中 `@register_hook` | 按名称引用：`my_hook: { ... }` |

名称冲突时自定义 hook 优先。

### 10.4 实现要点

```python
# hooks.py 自动发现逻辑
def discover_hooks(yaml_path: Path, cwd: Path) -> list[Path]:
    """从用例目录向上扫描 hooks.py，到 CWD 为止"""
    hooks_files = []
    current = yaml_path.resolve().parent
    cwd = cwd.resolve()

    while current >= cwd:
        hooks_file = current / "hooks.py"
        if hooks_file.exists():
            hooks_files.append(hooks_file)
        if current == cwd:
            break
        current = current.parent

    # 从外到内加载，内层可覆盖外层
    return list(reversed(hooks_files))
```

## 11. 扩展性

支持 Entry Points 方式供第三方包注册 hook：

```python
# 第三方包 pyproject.toml
[project.entry-points."nextgen.hooks"]
my_plugin = "my_plugin.hooks"
```

引擎启动时自动发现：
```python
for ep in importlib.metadata.entry_points(group="nextgen.hooks"):
    plugin = ep.load()
    plugin.register()
```

适用于插件生态，单项目用户不需要关心。
