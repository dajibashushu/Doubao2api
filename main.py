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
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List

from fastapi import FastAPI, HTTPException, Request
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

    try:
        message_dicts = [
            {"role": m.role, "content": _extract_text_content(m.content)}
            for m in messages
        ]
        emitted = ""

        def _delta_sse(delta_text: str) -> str:
            chunk = ChatCompletionChunk(
                id=request_id,
                model=model,
                created=created,
                choices=[StreamChoice(delta=DeltaMessage(content=delta_text))],
            )
            return f"data: {json.dumps(chunk.model_dump())}\n\n"

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

                chunk = ChatCompletionChunk(
                    id=request_id,
                    model=model,
                    created=created,
                    choices=[
                        StreamChoice(
                            delta=DeltaMessage(content=f"\n\n[错误] {error_msg}"),
                            finish_reason="stop"
                        )
                    ],
                )
                yield f"data: {json.dumps(chunk.model_dump())}\n\n"
                yield "data: [DONE]\n\n"
                return

            elif event_type in ("SSE_HEARTBEAT", "SSE_ACK"):
                continue

    except Exception as e:
        error_chunk = ChatCompletionChunk(
            id=request_id,
            model=model,
            created=created,
            choices=[
                StreamChoice(
                    delta=DeltaMessage(content=f"\n\n[错误] {str(e)}"),
                    finish_reason="stop"
                )
            ],
        )
        yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
        yield "data: [DONE]\n\n"


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
