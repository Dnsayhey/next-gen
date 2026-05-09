# 步骤执行顺序与变量作用域

基于 `nextgen/core/scheduler.py` 实际代码梳理。

## 用例级执行流程

```
Scheduler.run()
  │
  ├─ 1. load_discovered_hooks()        加载 hooks.py 文件
  ├─ 2. execute_hooks(before_all)       全局 context
  ├─ 3. DAG 调度，执行各步骤
  │     ├─ step A (run_step)
  │     ├─ step B (run_step)            可能并发
  │     └─ ...
  └─ 4. execute_hooks(after_all)        全局 context
```

- `before_all` 使用全局 `self.context`，它初始化自 testcase 的 `vars` 字段。
- `after_all` 同样使用全局 `self.context`，此时已包含所有成功步骤 extract 的变量。

---

## 单个步骤的执行流程

### 总体时序

```
run_step()
  │
  └─ _run_step_with_retry()
       │
       ├─ base_step_ctx = self.context.derive()     ─┐
       │                                              │ 第一层派生
       ├─ execute_hooks(before_each)                  │ 使用 base_step_ctx
       │                                              │
       │   ┌── [重试循环] ────────────────────────────┤ 每次重试：
       │   │  step_ctx = base_step_ctx.derive()     ─┤   第二层派生
       │   │                                          │
       │   │  _execute_step_logic(step_ctx)           │   使用 step_ctx
       │   │    ├─ 1. set_vars                        │
       │   │    ├─ 2. when (条件判断)                  │
       │   │    ├─ 3. hooks.before                    │
       │   │    ├─ 4. action (执行)                    │
       │   │    ├─ 5. validate (断言)                  │
       │   │    ├─ 6. extract (提取)                   │
       │   │    ├─ 7. export (显式导出)                │
       │   │    │  ★ SUCCESS                           │
       │   │    └─ 8. hooks.after (非阻断)             │
       │   │                                          │
       │   └── extract 之前失败则重试 ──────────────────┘
       │
       ├─ finally:
       │    ├─ execute_hooks(after_each)    使用最后一次重试的 step_ctx
       │    ├─ 若 SUCCESS → self.context.merge(pending_extracts + pending_exports)
       │    └─ 若非 SUCCESS → 清空 pending_extracts / pending_exports
       │
```

### 各阶段详解

#### 1. set_vars（设置步骤变量）

```yaml
steps:
  login:
    set_vars:
      base_url: "https://api.example.com"
      username: "${env_user}"
```

- **时机：** action 之前，when 之前。每个重试尝试都会重新执行。
- **作用域：** 写入 `step_ctx`（步骤局部），不影响全局 context。
- **注意：** 值会经过 `${var}` 变量渲染。可以使用全局变量和 before_each 设置的变量。

#### 2. when（条件执行）

```yaml
steps:
  cleanup:
    when:
      op: eq
      left: "${should_cleanup}"
      right: "true"
```

- **时机：** set_vars 之后，hooks.before 之前。每个重试尝试都会判断。
- **行为：** 条件不满足 → 步骤状态设为 SKIPPED，跳过后续所有逻辑（hooks、action、validate、extract 均不执行）。
- **作用域：** 读取 `step_ctx`。可以利用当前步骤的 set_vars。

#### 3. hooks.before（步骤前置钩子）

```yaml
steps:
  login:
    hooks:
      before:
        - get_random_str: { var: "request_id", length: 12 }
        - log: "sending login request"
```

- **时机：** when 之后，action 之前。每个重试尝试都会执行。
- **作用域：** 读写 `step_ctx`（步骤局部）。hook 设置的变量在本次重试的后续阶段可见。

#### 4. action（执行动作）

```yaml
steps:
  login:
    action:
      type: http
      config:
        method: POST
        url: "${base_url}/login"
```

- **时机：** hooks.before 之后，validate 之前。
- **作用域：** 读取 `step_ctx`。action 内部通过 `ctx.render()` 渲染配置中的变量引用。

#### 5. validate（断言验证）

```yaml
steps:
  login:
    validate:
      - op: eq
        left: status_code
        right: 200
      - op: contains
        left: body.token
        right: "eyJ"
```

- **时机：** action 之后，extract / export 之前。
- **行为：** 断言失败抛出 `ValidationError`，触发重试（如有）。
- **作用域：** `right` 值会经过 `step_ctx.render()` 渲染。`left` 是由 action 实现解释的表达式（如 `status_code`、`body.token`），不走变量替换。

#### 6. extract（提取变量）

```yaml
steps:
  login:
    extract:
      token: body.token
      user_id: body.user.id
```

- **时机：** validate 之后，export 之前。
- **作用域：** 写入 `step_ctx`（步骤局部），同时记录到 `step.pending_extracts`。
- **关键：** extract 完成后，其值可被后续 export 引用。

#### 7. export（显式导出变量）

```yaml
steps:
  login:
    extract:
      raw_token: $.token
    export:
      auth_header: "Bearer ${raw_token}"
```

- **时机：** extract 之后，hooks.after 之前。
- **作用域：** 从 `step_ctx` 渲染变量，同时记录到 `step.pending_exports`。同一个 export 中后面的变量可以引用前面已导出的变量。
- **提交：** 和 extract 一样，只有步骤最终 SUCCESS 后才发布到全局上下文；同名时 export 覆盖 extract。

#### 8. hooks.after（步骤后置钩子）

```yaml
steps:
  login:
    hooks:
      after:
        - log: "login done, token=${token}"
```

- **时机：** export 之后，步骤已标记为 SUCCESS 之后。仅当本次 attempt 成功走到 export 之后才执行；如果 action 或 validate 失败并触发重试，该次失败 attempt 不会跑 after hooks。
- **作用域：** 读写 `step_ctx`。可以读到 extract 提取出的变量和 export 设置的变量，但 after hook 的额外写入不会自动发布到全局。
- **非阻断：** 通过 `execute_hooks_best_effort` 执行，单个 hook 失败只记 warning 日志，不改变步骤状态，不阻止 extract/export 发布，不影响后续 hook 执行。

---

## 变量作用域层级

```
全局 context (self.context)
│  初始来源：testcase.vars
│  增量来源：成功步骤的 extract 合并
│  用于：before_all, after_all
│
├─ base_step_ctx = self.context.derive()
│  拥有全局变量的完整副本
│  写入不影响全局
│  用于：before_each, after_each
│  生命周期：单个步骤（跨越所有重试）
│
│  ├─ step_ctx = base_step_ctx.derive()    [第 1 次重试]
│  │  拥有 base_step_ctx 的完整副本
│  │  写入不影响 base_step_ctx
│  │  用于：set_vars, when, hooks.before, action, validate, extract, hooks.after
│  │  生命周期：单次重试尝试
│  │
│  ├─ step_ctx = base_step_ctx.derive()    [第 2 次重试]
│  │  全新的副本，第 1 次重试中的修改全部不可见
│  │  ...
```

### 关键规则

| 规则 | 说明 |
|------|------|
| **derive 是深拷贝** | `derive()` 对 vars 做 `deepcopy`，子 context 的修改不影响父级 |
| **每次重试都是全新的 step_ctx** | `step_ctx = base_step_ctx.derive()` 在每次重试循环顶部执行，前一次重试的 set_vars、extract、hook 修改变量等全部丢弃 |
| **before_each 写入可跨重试** | before_each 操作的是 `base_step_ctx`，它在重试循环外部，所以 before_each 设置的变量对所有重试可见 |
| **extract/export 延迟合并** | extract/export 结果先存在 pending 区，只有步骤最终 SUCCESS 才 merge 到全局，且 export 同名覆盖 extract |
| **after_each 总是执行（有前提）** | 在 finally 块中执行，但仅限真正进入 `_run_step_with_retry` 的步骤。`when` skip 会进入（会跑 after_each）；依赖失败或 fail_fast 导致 scheduler 直接标 SKIPPED 的步骤不会跑 after_each |
| **after_each 之后才合并** | 先执行 after_each，再根据状态决定是否 merge pending_extracts / pending_exports。after_each 和 after hooks 可以通过 `ctx.set()` 修改变量，但只有 pending 区中记录的 key 才会 merge 到全局——after hook 额外 `ctx.set()` 的变量不会自动发布 |
| **hooks.after 非阻断** | hooks.after 通过 `execute_hooks_best_effort` 执行，失败只记日志不影响步骤状态和 extract/export 发布 |

---

## before_each vs before、after_each vs after 的区别

| 维度 | before_each / after_each | before / after |
|------|--------------------------|----------------|
| 定义位置 | 用例级 `hooks:` 字段 | 步骤级 `hooks:` 字段 |
| 执行次数 | 每步 1 次 | before: 每次 attempt；after: 仅成功走到 export 的 attempt |
| 作用域 | `base_step_ctx` | `step_ctx`（每次重试重新派生） |
| before_each | 在所有重试之前执行 | — |
| after_each | 在所有重试之后执行（finally） | — |
| before | — | 在 action 之前执行 |
| after | — | 在 action 之后、extract/export 之后执行 |

---

## 完整执行时序图

```
用例开始
│
├─ before_all hooks                    [全局 context]
│
├─ ─ ─ ─ Step A ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│  │
│  ├─ base_step_ctx = global.derive()
│  ├─ before_each hooks                [base_step_ctx]
│  │
│  │  ┌─ Retry #1 ────────────────────────────┐
│  │  │  step_ctx = base.derive()             │
│  │  │  set_vars              → step_ctx     │
│  │  │  when                  → skip/continue│
│  │  │  hooks.before          → step_ctx     │
│  │  │  action                → result       │
│  │  │  validate              → pass/fail    │
│  │  │  extract               → step_ctx     │
│  │  │  export                → step_ctx     │
│  │  │  ★ SUCCESS                            │
│  │  │  hooks.after (非阻断)   → step_ctx     │
│  │  └───────────────────────────────────────┘
│  │  (如果失败，Retry #2: 重新 derive step_ctx，再来一遍)
│  │
│  ├─ after_each hooks                  [最后一次的 step_ctx]
│  ├─ global.merge(pending_extracts + pending_exports)
│  │                                      [仅 SUCCESS 时，export 覆盖 extract]
│
├─ ─ ─ ─ Step B ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│  (仅 sequential 或 B depends_on A 时，全局 context 包含 Step A extract)
│  (parallel 下独立步骤并发执行，不能假设看到彼此 extract)
│
├─ after_all hooks                     [全局 context]
│
用例结束
```
