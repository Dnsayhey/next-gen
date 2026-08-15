# Next-Gen Roadmap

最后更新：2026-08-16。

本文只记录当前能力边界、仍然有效的架构决策和后续优先级。已经稳定的 DSL 与实现细节分别以 [设计文档](design.md) 和 [执行顺序文档](execution-order-and-scoping.md) 为准。

## 当前基线

项目已经具备内部 API 与数据库测试所需的核心执行能力：

- YAML / JSON testcase DSL 与严格配置校验
- HTTP、PostgreSQL、MySQL、SQLite action
- `vars`、`set_vars`、`extract`、`export` 变量流
- `sequential` / `parallel` DAG 调度、`depends_on` 和 `fail_fast`
- retry、指数退避、请求超时和步骤总超时
- `when` 条件、matrix 参数化和 step tag filtering
- testcase / step 生命周期 hook，以及 `hooks.py`、`hooks_*.py` 自动发现
- env 文件、suite setup、多文件执行、目录与 glob discovery
- dry-run 执行计划、JSON / JUnit XML 报告和终端摘要
- testcase 级 HTTP session 复用
- testcase 级 DB 资源复用：PostgreSQL/MySQL 连接池和 SQLite 串行单连接

## 有效架构决策

### Testcase 是资源隔离边界

每个 testcase 拥有独立的 scheduler、context、hooks、result 和运行时资源。suite setup 与普通 testcase 只通过显式 `export` 传递数据，不共享 HTTP cookie、DB 连接或隐式事务状态。

当前不提供 run/global 级连接池。若未来增加，必须先确定：

- pool key 和配置覆盖规则
- suite、多个 CLI 输入与并发 testcase 的所有权
- 初始化失败、取消和进程退出时的清理语义
- 凭据变更与同 URL 配置漂移如何处理
- SQLite 是否应参与全局复用

### Suite 优先于 YAML include

Suite 保持 testcase 边界清晰，避免 step 名冲突以及 `vars`、hooks、mode、`fail_fast` 的跨文件合并规则。近期不实现 YAML `include`；只有当 env、hooks、suite setup 和未来模板仍无法解决复用需求时再重新评估。

### 数据流必须显式

- step 依赖只来自 `depends_on`
- step 局部变量通过 `extract` / `export` 发布
- suite setup 通过 `export` 向普通 testcase 传值
- 不依赖并发执行完成顺序或跨 testcase 隐式共享状态

### Scheduler 只管理通用生命周期

Scheduler 负责 DAG、状态、并发、retry、hook 和通用资源清理，不感知 HTTP client 或具体数据库驱动。Action 负责协议语义并通过 `Context` 注册 testcase 级资源。

## 近期优先级

### 1. 更精确的解析错误路径

把错误从 `invalid assertion format` 提升为带完整位置的信息，例如：

```text
steps.login.validate[0].eq: expected [left, right]
```

这能直接改善 DSL 编写体验，也便于编辑器和 CI 定位问题。

### 2. 文档与示例持续校验

- 保证 README 和 docs 中的相对链接有效
- 自动解析所有 runnable examples
- 对离线可运行示例增加 smoke test
- 明确区分可复制运行的示例和仅用于说明结构的片段

### 3. 自定义 Action 加载入口

`ActionSpec` 已是公开 Python API，但 CLI 目前只自动加载内置 action。后续可设计显式的模块加载参数或 entry point 机制，避免要求用户维护自定义 CLI wrapper。

### 4. CI 使用模板

JUnit reporter 已完成，但仓库还没有可直接采用的 CI workflow 示例。可以补充最小 GitHub Actions 或通用 CI 配置，展示退出码、报告落盘和 artifact 收集。

## 后续候选

- Shell/exec action，用于非 Python setup 工作流
- JSON Schema 或 OpenAPI 响应校验
- `--var key=value` 命令行覆盖
- 面向外部报告的可选字段脱敏
- 在存在明确跨 testcase 性能需求后，评估 run/global 级连接池
- 仅在需要执行不可信 testcase 时增加 ReDoS 等安全加固

## 暂不规划

- 重型 UI、权限系统和服务端管理平台
- 跨 testcase `depends_on`
- 默认共享跨 testcase cookie 或事务
- 没有明确复用场景的 YAML fragment include
