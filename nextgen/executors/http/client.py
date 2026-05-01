"""HTTP 客户端 - 发送请求"""

from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from nextgen.core.context import Context
from nextgen.core.model import RequestNode

from .utils import check_content_type_conflict, load_file_content


def parse_request_config(config: dict[str, Any]) -> RequestNode:
    """解析 request 配置为 RequestNode"""
    return RequestNode(
        method=config.get("method", "").upper(),
        url=config.get("url", ""),
        headers=config.get("headers", {}),
        params=config.get("params", {}),
        json=config.get("json"),
        form=config.get("form"),
        multipart=config.get("multipart"),
        body=config.get("body"),
        content_type=config.get("content_type"),
    )


async def execute_request(
    action_config: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    """执行 HTTP 请求

    Returns:
        dict: {"status_code": int, "body": Any, "headers": dict, "response": httpx.Response}
    """
    request = parse_request_config(action_config)

    # 渲染变量
    url = ctx.render(request.url)
    headers = ctx.render_dict(request.headers)
    params = ctx.render_dict(request.params)

    # 检查 header 冲突
    check_content_type_conflict(request)

    # 设置默认 content_type
    if request.content_type and "content-type" not in {k.lower() for k in headers}:
        headers["content-type"] = request.content_type

    logger.info(f"发送请求: {request.method} {url}")

    # 根据请求体类型发送请求
    body_type = request.body_type()

    async with httpx.AsyncClient() as client:
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
                    file_content = load_file_content(value)
                    file_path = Path(value[1:])
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
            raw_content = load_file_content(request.body)
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

    logger.info(f"响应状态: {response.status_code}")

    # 解析响应体
    try:
        body = response.json()
    except Exception:
        body = response.text

    return {
        "status_code": response.status_code,
        "body": body,
        "headers": dict(response.headers),
        "response": response,
    }
