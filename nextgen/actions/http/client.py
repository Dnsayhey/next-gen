"""HTTP action client."""

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

HTTP_CLIENT_RESOURCE = "http.client"


def _render_body(body_type: str | None, request: RequestConfig, ctx: Context) -> Any:
    if body_type == "json":
        return ctx.render_dict(request.json or {})
    if body_type == "form":
        return ctx.render_dict(request.form or {})
    if body_type == "multipart":
        return ctx.render_dict(request.multipart or {})
    if body_type == "raw":
        return ctx.render(request.body)
    return None


def _body_preview(body_type: str | None, rendered_body: Any) -> Any:
    if body_type == "multipart" and isinstance(rendered_body, dict):
        preview = {}
        for key, value in rendered_body.items():
            if isinstance(value, str) and value.startswith("@"):
                preview[key] = {"source": value}
            else:
                preview[key] = value
        return preview
    if body_type == "raw" and isinstance(rendered_body, str) and rendered_body.startswith("@"):
        return {"source": rendered_body}
    return rendered_body


def _build_action_input(
    request: RequestConfig,
    ctx: Context,
    headers: dict[str, Any],
    params: dict[str, Any],
    body_type: str | None,
    rendered_body: Any,
) -> dict[str, Any]:
    return {
        "type": "http",
        "method": request.method,
        "url": ctx.render(request.url),
        "headers": headers,
        "params": params,
        "body_type": body_type,
        "body": _body_preview(body_type, rendered_body),
        "timeout": request.timeout,
    }


async def execute_request(
    request: RequestConfig,
    ctx: Context,
) -> ActionResult:
    """Execute an HTTP request.

    Returns:
        ActionResult with HTTP response data and reporting snapshots.
    """
    base_dir = ctx.metadata.get("base_dir")

    # Render variables.
    url = ctx.render(request.url)
    headers = ctx.render_dict(request.headers)
    params = ctx.render_dict(request.params)
    body_type = request.body_type()
    rendered_body = _render_body(body_type, request, ctx)

    # Check header conflicts.
    check_content_type_conflict(request)

    # Set default content_type.
    if request.content_type and "content-type" not in {k.lower() for k in headers}:
        headers["content-type"] = request.content_type

    action_input = _build_action_input(request, ctx, headers, params, body_type, rendered_body)
    logger.info(f"Sending request: {request.method} {url}")

    # Send request according to body type.
    try:
        client = get_http_client(ctx)
        request_kwargs = {
            "method": request.method,
            "url": url,
            "headers": headers,
            "params": params,
        }
        if request.timeout:
            request_kwargs["timeout"] = request.timeout

        if body_type == "json":
            response = await client.request(
                **request_kwargs,
                json=rendered_body,
            )

        elif body_type == "form":
            response = await client.request(
                **request_kwargs,
                data=rendered_body,
            )

        elif body_type == "multipart":
            # Multipart data needs special handling for @-prefixed files.
            files = {}
            form_fields = {}

            for key, value in (rendered_body or {}).items():
                if isinstance(value, str) and value.startswith("@"):
                    # File upload.
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
                **request_kwargs,
                files=files,
                data=form_fields if form_fields else None,
            )

        elif body_type == "raw":
            # Handle @-prefixed files.
            raw_content = load_file_content(rendered_body, base_dir)
            if isinstance(raw_content, str):
                raw_content = ctx.render(raw_content)

            response = await client.request(
                **request_kwargs,
                content=raw_content.encode("utf-8") if isinstance(raw_content, str) else raw_content,
            )

        else:
            # No request body.
            response = await client.request(**request_kwargs)
    except Exception as exc:
        raise ActionExecutionError(str(exc), action_input) from exc

    logger.info(f"Response status: {response.status_code}")

    # Parse response body.
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


def get_http_client(ctx: Context) -> httpx.AsyncClient:
    """Return the testcase-scoped HTTP client."""
    client = ctx.get_resource(HTTP_CLIENT_RESOURCE)
    if client is None:
        client = httpx.AsyncClient()
        ctx.set_resource(HTTP_CLIENT_RESOURCE, client)
    return client
