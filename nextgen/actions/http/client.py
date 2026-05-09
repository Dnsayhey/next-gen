"""HTTP action 客户端 - 发送请求"""

from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from nextgen.core.context import Context
from nextgen.core.errors import ActionExecutionError
from nextgen.core.files import load_file_content, resolve_case_path
from nextgen.core.result import ActionResult

from .model import RequestConfig
from .utils import check_content_type_conflict


def _body_preview(body_type: str | None, request: RequestConfig, ctx: Context) -> Any:
    if body_type == "json":
        return ctx.render_dict(request.json or {})
    if body_type == "form":
        return ctx.render_dict(request.form or {})
    if body_type == "multipart":
        multipart_data = ctx.render_dict(request.multipart or {})
        preview = {}
        for key, value in multipart_data.items():
            if isinstance(value, str) and value.startswith("@"):
                preview[key] = {"source": value}
            else:
                preview[key] = value
        return preview
    if body_type == "raw":
        rendered_body = ctx.render(request.body)
        if isinstance(rendered_body, str) and rendered_body.startswith("@"):
            return {"source": rendered_body}
        return rendered_body
    return None


def _build_action_input(
    request: RequestConfig,
    ctx: Context,
    headers: dict[str, Any],
    params: dict[str, Any],
    body_type: str | None,
) -> dict[str, Any]:
    return {
        "type": "http",
        "method": request.method,
        "url": ctx.render(request.url),
        "headers": headers,
        "params": params,
        "body_type": body_type,
        "body": _body_preview(body_type, request, ctx),
        "timeout": request.timeout,
    }


async def execute_request(
    request: RequestConfig,
    ctx: Context,
) -> ActionResult:
    """执行 HTTP 请求

    Returns:
        ActionResult with HTTP response data and reporting snapshots.
    """
    base_dir = ctx.metadata.get("base_dir")

    # 渲染变量
    url = ctx.render(request.url)
    headers = ctx.render_dict(request.headers)
    params = ctx.render_dict(request.params)
    body_type = request.body_type()

    # 检查 header 冲突
    check_content_type_conflict(request)

    # 设置默认 content_type
    if request.content_type and "content-type" not in {k.lower() for k in headers}:
        headers["content-type"] = request.content_type

    action_input = _build_action_input(request, ctx, headers, params, body_type)
    logger.info(f"发送请求: {request.method} {url}")

    # 设置超时
    timeout = request.timeout if request.timeout else None

    # 根据请求体类型发送请求
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if body_type == "json":
                json_body = ctx.render_dict(request.json)
                response = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )

            elif body_type == "form":
                form_data = ctx.render_dict(request.form)
                response = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=form_data,
                )

            elif body_type == "multipart":
                # multipart 需要特殊处理 @ 前缀的文件
                files = {}
                form_fields = {}
                multipart_data = ctx.render_dict(request.multipart)

                for key, value in multipart_data.items():
                    if isinstance(value, str) and value.startswith("@"):
                        # 文件上传
                        file_content = load_file_content(value, base_dir)
                        file_path = resolve_case_path(value[1:], base_dir)
                        files[key] = (
                            file_path.name,
                            file_content,
                            "application/octet-stream",
                        )
                    else:
                        form_fields[key] = value

                response = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    files=files,
                    data=form_fields if form_fields else None,
                )

            elif body_type == "raw":
                # 处理 @ 前缀的文件
                raw_content = load_file_content(request.body, base_dir)
                if isinstance(raw_content, str):
                    raw_content = ctx.render(raw_content)

                response = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    content=raw_content.encode("utf-8") if isinstance(raw_content, str) else raw_content,
                )

            else:
                # 无请求体
                response = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    params=params,
                )
    except Exception as exc:
        raise ActionExecutionError(str(exc), action_input) from exc

    logger.info(f"响应状态: {response.status_code}")

    # 解析响应体
    try:
        body = response.json()
    except Exception:
        body = response.text

    data = {
        "status_code": response.status_code,
        "body": body,
        "headers": dict(response.headers),
    }
    return ActionResult(
        data=data,
        action_input=action_input,
        action_output=data,
        metric={"label": "status_code", "value": response.status_code},
    )
