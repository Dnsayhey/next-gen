# Next-Gen 当前状态

最后更新：2026-08-16。

本文只记录已经实现的能力和当前有效的架构边界。DSL 与实现细节分别以 [设计与 DSL 参考](design.md) 和 [执行顺序与变量作用域](execution-order-and-scoping.md) 为准。

## 已实现能力

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

## 当前架构边界

### Testcase 是资源隔离边界

每个 testcase 拥有独立的 scheduler、context、hooks、result 和运行时资源。suite setup 与普通 testcase 通过显式 `export` 传递数据，不共享 HTTP cookie、DB 连接或事务状态。

### 数据流必须显式

- step 依赖只来自 `depends_on`
- step 局部变量通过 `extract` / `export` 发布
- suite setup 通过 `export` 向普通 testcase 传值
- 并发步骤不能依赖彼此的完成顺序

### Scheduler 管理通用生命周期

Scheduler 负责 DAG、状态、并发、retry、hook 和通用资源清理。Action 负责协议语义，并通过 `Context` 注册 testcase 级资源。

### Suite 保持 testcase 独立

Suite 按文件组织独立 testcase。每个文件分别解析、调度和生成结果，每张依赖图限定在单个 testcase 内。
