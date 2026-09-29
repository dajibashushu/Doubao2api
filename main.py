"""
Doubao2api - FastAPI 主服务

本模块实现了 OpenAI 兼容的 API 端点，将豆包 (doubao.com/chat) 封装为
标准的 OpenAI Chat Completions API 格式。

主要功能：
- GET /v1/models: 列出可用模型
- POST /v1/chat/completions: 聊天补全（支持流式和非流式）
- GET /health: 健康检查
- POST /reload-cookies: 重新加载 Cookie

@author: Doubao2api
@version: 1.0.0
"""
import hmac
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from config import config
from doubao_client import DoubaoClient, load_cookies_from_file
from models import (
    ChatCompletionChunk,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatMessage,
    DeltaMessage,
    ModelInfo,
    ModelListResponse,
    StreamChoice,
)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全局 Cookie 缓存
_cookies_cache: Dict[str, str] = {}


def _estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量

    使用简单的规则估算中文字符、英文单词、数字和标点符号的 token 数量。

    Args:
        text: 待估算的文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0

    chinese_chars = len(re.findall(r'[一-鿿]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    numbers = len(re.findall(r'\d+', text))
    punctuation = len(re.findall(r'[^\w\s]', text))

    tokens = int(chinese_chars * 1.5 + english_words + numbers + punctuation * 0.5)
    return max(tokens, 1)


def get_cookies() -> Dict[str, str]:
    """
    获取 Cookie（带缓存）

    从文件加载 Cookie 并缓存，后续调用直接返回缓存的 Cookie。

    Returns:
        Cookie 字典
    """
    global _cookies_cache
    if not _cookies_cache:
        _cookies_cache = load_cookies_from_file()
    return _cookies_cache


def reload_cookies() -> None:
    """
    重新加载 Cookie

    清除缓存并重新从文件加载 Cookie。
    """
    global _cookies_cache
    _cookies_cache = load_cookies_from_file()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    在应用启动时打印配置信息，关闭时打印停止信息。

    Args:
        app: FastAPI 应用实例

    Yields:
        None
    """
    logger.info("豆包 OpenAI 代理启动中...")
    logger.info(f"监听地址: http://{config.host}:{config.port}")
    logger.info("OpenAI 兼容端点:")
    logger.info("   GET  /v1/models")
    logger.info("   POST /v1/chat/completions")
    logger.info("   GET  /health")
    logger.info("   POST /reload-cookies")

    try:
        cookies = get_cookies()
        logger.info(f"Cookie 加载成功 (共 {len(cookies)} 个)")
        if "ttwid" in cookies:
            logger.info(f"   ttwid: {cookies['ttwid'][:20]}...")
    except Exception as e:
        logger.error(f"Cookie 加载失败: {e}")
        logger.info("   请先运行 'python cookie_helper.py' 提取 Cookie")

    logger.info("cc-switch 配置:")
    logger.info(f"   base_url: http://localhost:{config.port}/v1")
    logger.info(f"   api_key:  doubao")

    yield

    logger.info("豆包 OpenAI 代理已停止")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="Doubao2api",
    description="将豆包 (doubao.com/chat) 封装为 OpenAI 兼容 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    """API Key 闸门（本地补丁，2026-09-29 加）。

    上游版本**完全没有鉴权**：`/v1/chat/completions` 谁都能调，挂上公网就等于把
    自己的豆包账号送人。这里加一层可选闸门：只有设置了环境变量 `DOUBAO_API_KEY`
    才启用（不设 = 保持上游行为，纯本地用不受影响）。

    接受三种传法：`Authorization: Bearer <key>`、`x-api-key` / `x-goog-api-key`、
    查询串 `?key=`。`/health` 永远放行（探活用）；比较用 hmac.compare_digest。
    """
    key = (os.environ.get("DOUBAO_API_KEY") or "").strip()
    if key and request.url.path != "/health":
        supplied = ""
        auth = request.headers.get("authorization", "") or ""
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
        if not supplied:
            supplied = (request.headers.get("x-api-key")
                        or request.headers.get("x-goog-api-key") or "").strip()
        if not supplied:
            supplied = (request.query_params.get("key") or "").strip()
        if not hmac.compare_digest(supplied, key):
            return JSONResponse(
                status_code=401,
                content={"error": {"message": "invalid api key",
                                   "type": "auth_error", "code": "invalid_api_key"}},
            )
    return await call_next(request)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    健康检查端点

    Returns:
        包含状态和服务名称的字典
    """
    return {"status": "ok", "service": "Doubao2api"}


@app.post("/reload-cookies")
async def reload_cookies_endpoint() -> Dict[str, str]:
    """
    重新加载 Cookie 端点

    Returns:
        操作结果字典

    Raises:
        HTTPException: 重新加载失败时抛出异常
    """
    try:
        reload_cookies()
        return {"status": "ok", "message": "Cookie 重新加载成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models() -> ModelListResponse:
    """
    列出可用模型端点

    Returns:
        模型列表响应
    """
    models = [
        ModelInfo(id=model_name)
        for model_name in config.available_models
    ]
    return ModelListResponse(data=models)


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> Any:
    """
    聊天补全端点 - OpenAI 兼容

    支持流式和非流式响应。

    Args:
        request: 聊天补全请求

    Returns:
        聊天补全响应或流式响应

    Raises:
        HTTPException: Cookie 加载失败或请求处理失败时抛出异常
    """
    try:
        cookies = get_cookies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cookie 加载失败: {e}")

    client = DoubaoClient(cookies)
    messages = _process_messages(request.messages)

    if request.stream:
        return StreamingResponse(
            _stream_response(client, messages, request.model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            message_dicts = [
                {"role": m.role, "content": _extract_text_content(m.content)}
                for m in messages
            ]
            full_text = await client.chat_completion(message_dicts, request.model)

            prompt_text = " ".join(_extract_text_content(m.content) for m in messages)
            prompt_tokens = _estimate_tokens(prompt_text)
            completion_tokens = _estimate_tokens(full_text)

            response = ChatCompletionResponse(
                model=request.model,
                choices=[
                    ChatCompletionChoice(
                        message=ChatMessage(role="assistant", content=full_text)
                    )
                ],
                usage=ChatCompletionUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
            )
            return response.model_dump()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


def _process_messages(messages: List[ChatMessage]) -> List[ChatMessage]:
    """
    处理消息列表

    将系统消息合并到用户消息中，确保消息格式符合豆包 API 要求。

    Args:
        messages: 原始消息列表

    Returns:
        处理后的消息列表
    """
    processed: List[ChatMessage] = []
    system_content = ""

    for msg in messages:
        content = _extract_text_content(msg.content)

        if msg.role == "system":
            system_content += content + "\n"
        elif msg.role == "user":
            if system_content:
                combined = f"[系统指令]{system_content}\n[用户消息]{content}"
                processed.append(ChatMessage(role="user", content=combined))
                system_content = ""
            else:
                processed.append(ChatMessage(role="user", content=content))
        elif msg.role == "assistant":
            processed.append(ChatMessage(role="assistant", content=content))

    if system_content and not processed:
        processed.append(ChatMessage(role="user", content=system_content))

    return processed


def _extract_text_content(content: Any) -> str:
    """
    提取文本内容

    支持字符串、数组和对象格式的内容提取。

    Args:
        content: 消息内容，支持多种格式

    Returns:
        提取的文本内容
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
            elif isinstance(item, str):
                texts.append(item)
        return " ".join(texts)
    if isinstance(content, dict):
        return content.get("text", str(content))
    return str(content)


async def _stream_response(
    client: DoubaoClient,
    messages: List[ChatMessage],
    model: str,
) -> AsyncGenerator[str, None]:
    """
    生成流式响应

    将豆包的 SSE 事件转换为 OpenAI 兼容的流式响应格式。

    Args:
        client: 豆包客户端实例
        messages: 消息列表
        model: 模型名称

    Yields:
        SSE 格式的响应字符串
    """
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    def _delta_sse(delta_text: str) -> str:
        chunk = ChatCompletionChunk(
            id=request_id,
            model=model,
            created=created,
            choices=[StreamChoice(delta=DeltaMessage(content=delta_text))],
        )
        return f"data: {json.dumps(chunk.model_dump())}\n\n"

    # emitted 跟踪已输出的文本，供错误分支判断是否已有正常内容
    emitted = ""
    try:
        message_dicts = [
            {"role": m.role, "content": _extract_text_content(m.content)}
            for m in messages
        ]

        async for event in client.chat_completion_stream(message_dicts, model):
            event_type = event.get("event", "")
            data = event.get("data", {})

            if event_type in ("STREAM_MSG_NOTIFY", "STREAM_CHUNK", "CHUNK_DELTA"):
                text = client.extract_text_from_event(event)
                if not text:
                    continue
                if event_type == "STREAM_MSG_NOTIFY":
                    new_full = text
                else:
                    new_full = emitted + text
                if new_full.startswith(emitted):
                    delta = new_full[len(emitted):]
                else:
                    delta = new_full
                emitted = new_full
                if delta:
                    yield _delta_sse(delta)

            elif event_type in ("STREAM_END", "SSE_REPLY_END"):
                chunk = ChatCompletionChunk(
                    id=request_id,
                    model=model,
                    created=created,
                    choices=[
                        StreamChoice(
                            delta=DeltaMessage(),
                            finish_reason="stop"
                        )
                    ],
                )
                yield f"data: {json.dumps(chunk.model_dump())}\n\n"
                yield "data: [DONE]\n\n"
                return

            elif event_type in ("error", "STREAM_ERROR"):
                error_msg = data.get("error_msg", data.get("message", "Unknown error"))

                if "verify" in str(data.get("extra", {})).lower() or "captcha" in error_msg.lower():
                    error_msg = f"需要验证码，请在浏览器中手动完成验证后重试。原始错误: {error_msg}"

                if emitted:
                    # 已有正常内容：以增量文本补充错误说明，保持会话完整
                    yield _delta_sse(f"\n\n[错误] {error_msg}")
                else:
                    # 尚无任何输出：以顶层 error 对象发出，客户端可识别为错误
                    # 而非当作正常回答内容
                    error_payload = {
                        "error": {
                            "message": error_msg,
                            "type": "upstream_error",
                            "code": data.get("error_code", "upstream_error"),
                        }
                    }
                    yield f"data: {json.dumps(error_payload)}\n\n"
                yield "data: [DONE]\n\n"
                return

            elif event_type in ("SSE_HEARTBEAT", "SSE_ACK"):
                continue

    except Exception as e:
        if emitted:
            yield _delta_sse(f"\n\n[错误] {str(e)}")
        else:
            yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'server_error', 'code': 'internal_error'}})}\n\n"
        yield "data: [DONE]\n\n"


# ─── AI 画图（本地补丁 2026-09-29，上游没有）───────────────────────────────
# 上游只有文本通道，客户端打 /v1/images/generations 会 404。这里按浏览器真实抓包补齐：
# 同一个 /chat/completion 端点，加 chat_ability 声明 ability_type=3（生图），
# ability_param 里带模型 "Seedream 5.0 Flash" 与比例 ratio。
# 图片 URL 在 SSE 的
#   .patch_op[0].patch_value.content_block[0].content.creation_block.creations[N].image
# 下，多个变体：image_ori / image_preview / image_thumb 带水印（右下角「豆包AI生成」），
# **image_ori_raw.url 是无水印原图**（2026-09-29 实测 3.2MB PNG、肉眼确认无水印），
# 所以优先取它，取不到再退化到 image_ori。
_IMAGE_MODEL = "Seedream 5.0 Flash"
_IMAGE_RATIOS = {"1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4, "16:9": 16 / 9,
                 "9:16": 9 / 16, "3:2": 1.5, "2:3": 2 / 3, "21:9": 21 / 9}


def _ratio_from_size(size: Optional[str]) -> str:
    """把 OpenAI 的 `size`（如 1024x1792）映射成豆包要的 ratio 字符串。"""
    m = re.match(r"^\s*(\d+)\s*[xX*]\s*(\d+)\s*$", str(size or ""))
    if not m:
        return "auto"
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0 or w == h:
        return "1:1"
    from math import gcd
    g = gcd(w, h)
    key = f"{w // g}:{h // g}"
    if key in _IMAGE_RATIOS:
        return key
    target = w / h
    return min(_IMAGE_RATIOS, key=lambda k: abs(_IMAGE_RATIOS[k] - target))


def _extract_block_text(node, out: List[str]) -> None:
    """递归收集 SSE 里的 text_block 文本（用来识别豆包的内容审核拒绝话术）。"""
    if isinstance(node, dict):
        tb = node.get("text_block")
        if isinstance(tb, dict) and tb.get("text"):
            out.append(str(tb["text"]))
        for v in node.values():
            _extract_block_text(v, out)
    elif isinstance(node, list):
        for v in node:
            _extract_block_text(v, out)


def _collect_creation_images(node, out: dict) -> None:
    """递归找出 SSE 里的 creation_block.creations，按图片 key 去重收集变体。"""
    if isinstance(node, dict):
        creations = node.get("creation_block", {}).get("creations") if "creation_block" in node else None
        if creations is None and isinstance(node.get("creations"), list):
            creations = node["creations"]
        for item in (creations or []):
            img = (item or {}).get("image") or {}
            key = img.get("image_key") or img.get("key") or (
                (img.get("image_ori") or {}).get("url", "")[:80])
            if not key:
                continue
            urls = {}
            for variant in ("image_ori_raw", "image_ori", "image_preview", "image_thumb"):
                v = img.get(variant) or {}
                if v.get("url"):
                    urls[variant] = v["url"]
            if urls:
                out.setdefault(key, {}).update(urls)
        for v in node.values():
            _collect_creation_images(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_creation_images(v, out)


async def _doubao_generate_images(prompt: str, ratio: str, want: int, timeout: float = 240.0):
    """调上游生图，返回 [{url, ...}]（去重后最多 want 张）。"""
    import httpx

    cookies = get_cookies()
    client = DoubaoClient(cookies)
    client.reset_conversation()
    payload = client._build_completion_request(f"生成图片：{prompt}")
    ability = {"ability_type": 1, "ability_param": {
        "model": _IMAGE_MODEL, "ratio": ratio,
        "input_box_content": {"user_input_content": prompt, "reply_message_format": "生成图片：%s"}}}
    payload["chat_ability"] = {
        "ability_type": 3,
        "ability_param": json.dumps(ability, ensure_ascii=False, separators=(",", ":")),
    }

    found: Dict[str, Dict[str, str]] = {}
    refusal = ""
    url = f"{config.doubao_base_url}/chat/completion"
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=30.0),
                                 cookies=cookies, follow_redirects=True) as c:
        async with c.stream("POST", url, params=client._get_query_params(),
                            headers=client._get_headers(), json=payload) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", "replace")
                raise HTTPException(status_code=502,
                                    detail=f"豆包生图返回 HTTP {resp.status_code}: {body[:300]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except Exception:
                    continue
                _collect_creation_images(event, found)
                # 内容审核拒绝时豆包会回一段说明文字（无图片）——必须识别出来，
                # 否则调用方只看到“没图”的 502，完全不知道是被审核拦了。
                texts: List[str] = []
                _extract_block_text(event, texts)
                for t in texts:
                    if any(k in t for k in ("涉嫌违反", "使用规范", "内容审核", "无法生成", "换个话题")):
                        refusal = t.strip()
                if len(found) >= want:
                    break

    images = []
    for key, variants in found.items():
        images.append({"key": key, "url": variants.get("image_ori_raw") or variants.get("image_ori"),
                       "watermarked_url": variants.get("image_ori")})
    images = [i for i in images if i["url"]]
    return images[:want], refusal


@app.post("/v1/images/generations")
async def images_generations(request: Request) -> Any:
    """OpenAI 兼容的图像生成（本地补丁）。

    请求体：{"model": "...", "prompt": "...", "n": 1, "size": "1024x1792",
             "response_format": "url" | "b64_json"}
    返回：{"created": ts, "data": [{"url": ...} | {"b64_json": ...}]}
    额外字段（guidance_scale / batch_size / image_size 等）忽略，不影响调用。
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    try:
        n = max(1, min(int(body.get("n") or 1), 4))
    except (TypeError, ValueError):
        n = 1
    ratio = _ratio_from_size(body.get("size") or body.get("image_size"))
    fmt = str(body.get("response_format") or "url").lower()

    logger.info(f"生图请求: prompt={prompt[:40]!r} n={n} size={body.get('size')} ratio={ratio}")
    images, refusal = await _doubao_generate_images(prompt, ratio, n)
    if not images:
        if refusal:
            raise HTTPException(status_code=400, detail=f"豆包内容审核拒绝：{refusal}")
        raise HTTPException(
            status_code=502,
            detail="豆包未返回图片（可能触发风控/验证码、额度不足，或上游协议又变了）")

    data: List[Dict[str, str]] = []
    if fmt == "b64_json":
        import base64
        import httpx
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as c:
            for img in images:
                r = await c.get(img["url"], headers={"referer": config.doubao_base_url + "/"})
                r.raise_for_status()
                data.append({"b64_json": base64.b64encode(r.content).decode()})
    else:
        for img in images:
            data.append({"url": img["url"], "watermarked_url": img.get("watermarked_url") or ""})

    return {"created": int(time.time()), "model": str(body.get("model") or "doubao"),
            "data": data}


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """把 /v1 下的错误统一成 OpenAI 形状的 {"error": {...}}（本地补丁）。

    FastAPI 默认回 `{"detail": "..."}`，实测 iOS 类客户端解析失败会报
    「未能读取数据，因为它的格式不正确」——错误原因完全丢失。
    """
    if request.url.path.startswith("/v1"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {
                "message": str(exc.detail),
                "type": "upstream_error" if exc.status_code >= 500 else "invalid_request_error",
                "code": exc.status_code,
            }},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    if request.url.path.startswith("/v1"):
        return JSONResponse(status_code=422, content={"error": {
            "message": f"invalid request: {exc.errors()[:2]}",
            "type": "invalid_request_error", "code": 422}})
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理

    捕获所有未处理的异常，返回统一的错误响应格式。

    Args:
        request: 请求对象
        exc: 异常对象

    Returns:
        JSON 错误响应
    """
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": str(exc),
                "type": "server_error",
                "code": "internal_error",
            }
        },
    )


def main() -> None:
    """
    启动服务器

    使用 uvicorn 启动 FastAPI 服务器。
    """
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
