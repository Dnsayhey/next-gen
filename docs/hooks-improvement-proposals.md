# Hooks 系统改进讨论

> 状态：部分已实施

## 已实施

### step 级 hooks.after 非阻断执行

**问题：** hooks.after 失败会将步骤标记为 FAILED，导致已成功 extract 的变量丢失。

**方案：** extract 完成后立即标记 SUCCESS，hooks.after 通过 `execute_hooks_best_effort` 非阻断执行——单个 hook 失败只记 warning，不改变步骤状态，不阻止 extract 发布，不影响后续 hook 执行。

**实施：** `scheduler.py` 中新增 `execute_hooks_best_effort` 方法，`_execute_step_logic` 在 extract 后调用。

## 待实施提案

### 1. 同名覆盖检测

**问题：** 不同来源注册同名 hook 会静默覆盖（内置 hook、插件 hook、自动发现的 hooks.py），难以排查。

**方案：** 加载时检测冲突，抛出 warning 或 error。

### 2. 支持同步函数注册

**问题：** 所有 hook handler 必须是 `async def`，对简单场景（设变量、打日志）门槛偏高。

**方案：** 执行层检测返回值是否 awaitable——同步函数直接调用，不做 `asyncio.to_thread`。hook 拿到 mutable Context，丢到线程里会引入线程安全问题和顺序感问题。需要阻塞 IO 的 hook 由用户自己写 async 或显式 offload。

```python
@register_hook("seedVars")
def seed_vars(ctx, params):       # 同步函数，也能正常工作
    for key, value in params.items():
        ctx.set(key, value)
```

### 3. 合并 param parser 与 handler 定义

**问题：** `register_hook_param_parser` 需要单独注册，容易遗忘或与 handler 不同步。

**方案：** 将 parser 作为 `register_hook` 的参数：

```python
@register_hook("sleep", parser=lambda v: {"seconds": v})
async def hook_sleep(ctx, params):
    await asyncio.sleep(params["seconds"])
```

### 4. 参数校验

**问题：** handler 收到的 `params` 是裸 `dict`，没有校验，传错参数只能运行时发现。

**方案：** 先支持简单 callable validator 或 dataclass parser，等 hook 使用变多再考虑复杂 schema。

### 5. 放宽文件名限制

**问题：** 只能叫 `hooks.py`，无法按功能拆分。

**方案：** 支持在 DSL 或配置中指定额外的 hook 文件路径，同时保留 `hooks.py` 作为默认约定。

### 6. 条件执行

**问题：** 所有 hook 无条件执行，需要条件判断时只能在 handler 内部写逻辑。

**方案：** DSL 层面支持 `when` 条件：

```yaml
hooks:
  after:
    - notifySlack: { message: "step failed" }
      when: "step.status == 'failed'"
```

### 7. 更细粒度的生命周期点

**问题：** 固定 5 个时机（before_all / after_all / before_each / after_each / step before & after），无法扩展。

**方案：** 增加 `on_retry`、`on_error`、`after_validate` 等更细粒度的执行点。

**注意：** 短期不建议实施。刚把 after 的语义收紧（非阻断），短期再快速扩生命周期点容易把边界弄糊，等真实案例出现再说。

## 优先级建议

| 优先级 | 提案 | 理由 |
|--------|------|------|
| P0 | 同名覆盖检测 | 静默覆盖太难排查，属于坑位修复，改动小。早期项目宁可报错清楚一点 |
| P1 | 支持同步函数 | 降低门槛，但不用 `asyncio.to_thread`，直接判断 awaitable |
| P1 | 合并 param parser | 减少认知负担，能把 handler 和 shorthand 解析放在一起 |
| P2 | 参数校验 | 有价值，但先从简单 callable validator 开始，别一上来搞复杂 schema |
| P3 | 放宽文件名限制 | 锦上添花 |
| P3 | 条件执行 | 可在 handler 内变通 |
| P3 | 细粒度生命周期 | 等真实案例出现再扩，避免把边界弄糊 |
