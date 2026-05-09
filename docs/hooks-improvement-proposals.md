# Hooks 系统设计

> 状态：已实施基础易用版。

## 设计目标

Hook 是生命周期副作用函数，不是返回值管道。

用户写 hook 时应尽量像写普通 Python 函数：

- 用 `@hook` 注册。
- 函数名默认就是 hook 名。
- 支持同步函数和异步函数。
- YAML 参数按函数签名绑定。
- 需要上下文时声明 `ctx` 或 `context` 参数。
- 要写变量时显式调用 `ctx.set(...)`。
- 返回非 `None` 值不会参与执行语义，只记录 warning。

## 用户 API

```python
from nextgen import hook


@hook
def mask_token(ctx, source="token", target="masked_token", keep=2):
    value = str(ctx.get(source, ""))
    ctx.set(target, value[:keep] + "***" + value[-keep:])
```

YAML:

```yaml
hooks:
  after:
    - mask_token:
        source: token
        target: masked_token
        keep: 2
```

需要自定义 hook 名时：

```python
@hook("mask")
def mask_token(ctx):
    ...
```

默认不允许重复注册同名 hook。确实需要覆盖时必须显式声明：

```python
@hook("mask", override=True)
def custom_mask(ctx):
    ...
```

## 参数绑定规则

```python
@hook
def notify(message: str, level: str = "info"):
    ...
```

```yaml
- notify:
    message: "done"
    level: warning
```

- YAML 中的 dict 参数按函数签名传入。
- 有默认值的参数可以省略。
- 没有默认值的参数缺失时报错。
- 传入函数不认识的参数时报错。
- 函数声明 `**kwargs` 时可以接收任意额外参数。
- `ctx` 和 `context` 是保留注入参数，不从 YAML 读取，也不应作为业务参数名使用。

## 标量简写

如果 YAML 参数是标量，执行期会根据函数签名绑定到业务参数：

```python
@hook
async def sleep(seconds: float = 0):
    ...
```

```yaml
- sleep: 1
```

等价于：

```yaml
- sleep:
    seconds: 1
```

绑定规则：

- 如果只有一个必填业务参数，绑定到该参数。
- 如果没有必填业务参数，绑定到第一个非 `ctx` / `context` 的业务参数。
- 如果有多个必填业务参数，标量简写会报错，要求使用 dict。

因此：

```yaml
- log: "done"
```

会绑定为 `log(message="done")`。

## 返回值语义

Hook 不通过返回值传递数据。

- `return None`：正常。
- `return 非 None`：执行继续，记录 warning。

提示信息：

```text
hook 'foo' returned a value and it was ignored; use ctx.set(...) to write variables
```

## 内置 hooks

内置 hook 名统一使用 snake_case：

- `log(ctx, message="", level="info")`
- `sleep(seconds=0)`
- `get_timestamp(ctx, var)`
- `get_time_str(ctx, var, format="%Y-%m-%d %H:%M:%S")`
- `get_random_str(ctx, var, length=8)`
- `set_vars(ctx, **vars)`

## 生命周期语义

### step 级 hooks.after 非阻断执行

`hooks.after` 在 extract / export 之后执行。步骤已标记为成功后，`hooks.after` 通过 best-effort 方式执行：

- 单个 after hook 失败只记录 warning。
- 不改变步骤状态。
- 不阻止 extract / export 发布到全局 context。
- 不影响后续 after hook 执行。

其他 hook 阶段仍然是阻断式执行。

## 后续提案

| 优先级 | 提案 | 理由 |
|--------|------|------|
| P2 | 参数类型转换 | 可基于 type hint 做轻量转换，但别过早引入复杂 schema |
| P3 | 放宽文件名限制 | 允许按功能拆分 hook 文件，同时保留 `hooks.py` 默认约定 |
| P3 | 条件执行 | 可先在 hook 内部判断，等真实需求稳定后再扩 DSL |
| P3 | 更细生命周期点 | 如 `on_retry`、`on_error`、`after_validate`，等真实案例出现再扩 |
