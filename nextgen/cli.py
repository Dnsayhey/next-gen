"""CLI 入口"""

import asyncio
from pathlib import Path

import typer
from loguru import logger

from nextgen.bootstrap import load_builtin_actions
from nextgen.core.planner import validate_testcase
from nextgen.core.scheduler import Scheduler
from nextgen.core.model import TestStatus
from nextgen.parser.loader import load_testcase
from nextgen.reporter.json_reporter import to_json

app = typer.Typer(name="nextgen", help="Next-Gen API Test Engine")


@app.command()
def run(
    file: Path = typer.Argument(..., help="测试用例 YAML 文件路径"),
    parallel: int = typer.Option(10, "--parallel", "-p", help="最大并发数"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细日志"),
) -> None:
    """运行测试用例"""
    if not verbose:
        logger.remove()
        logger.add(lambda m: None, level="WARNING")

    try:
        load_builtin_actions()

        # 加载测试用例
        testcase = load_testcase(file)

        # 验证 DAG
        validate_testcase(testcase)

        # 执行
        scheduler = Scheduler(testcase, max_concurrency=parallel)
        result = asyncio.run(scheduler.run())
        result.testcase = str(file)

        # 输出报告
        print(to_json(result))

        # 退出码
        if result.status == TestStatus.FAILED:
            raise typer.Exit(code=1)

    except FileNotFoundError as e:
        logger.error(str(e))
        raise typer.Exit(code=2)
    except ValueError as e:
        logger.error(f"测试用例格式错误: {e}")
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
