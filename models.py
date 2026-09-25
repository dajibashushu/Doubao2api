"""
Doubao2api - 数据模型

本模块定义了所有请求和响应的数据模型，兼容 OpenAI API 格式。
使用 Pydantic 进行数据验证和序列化。

@author: Doubao2api
@version: 1.0.0
"""
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    聊天消息模型

    表示单条聊天消息，支持字符串、数组和对象格式的内容。

    Attributes:
        role: 消息角色，可选值为 "user", "assistant", "system"
        content: 消息内容，支持字符串、数组或对象格式
        name: 可选的发送者名称
    """

    role: str
    content: Optional[Union[str, List[Any], Dict[str, Any]]] = None
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """
    聊天补全请求模型

    定义了 OpenAI 兼容的聊天补全请求格式。

    Attributes:
        model: 模型名称，默认为 "doubao"
        messages: 消息列表
        temperature: 温度参数，控制生成的随机性
        top_p: 核采样参数
        n: 生成的回复数量
        stream: 是否启用流式输出
        stop: 停止生成的标记
        max_tokens: 最大生成token数
        presence_penalty: 存在惩罚
        frequency_penalty: 频率惩罚
        logit_bias: logit偏置
        user: 用户标识
    """

    model: str = "doubao-fast"
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None


class ChatCompletionUsage(BaseModel):
    """
    Token 使用统计模型

    记录请求和响应的 token 使用情况。

    Attributes:
        prompt_tokens: 提示词token数
        completion_tokens: 生成内容token数
        total_tokens: 总token数
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionChoice(BaseModel):
    """
    聊天补全选择模型

    表示单个回复选项。

    Attributes:
        index: 选项索引
        message: 回复消息
        finish_reason: 完成原因，如 "stop", "length" 等
    """

    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    """
    聊天补全响应模型

    定义了 OpenAI 兼容的聊天补全响应格式。

    Attributes:
        id: 响应ID，自动生成
        object: 对象类型，固定为 "chat.completion"
        created: 创建时间戳
        model: 使用的模型名称
        choices: 回复选项列表
        usage: token使用统计
    """

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "doubao"
    choices: List[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None


class DeltaMessage(BaseModel):
    """
    增量消息模型

    用于流式响应中的增量消息。

    Attributes:
        role: 消息角色
        content: 消息内容增量
    """

    role: Optional[str] = None
    content: Optional[str] = None


class StreamChoice(BaseModel):
    """
    流式选择模型

    用于流式响应中的单个选项。

    Attributes:
        index: 选项索引
        delta: 增量消息
        finish_reason: 完成原因
    """

    index: int = 0
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """
    聊天补全流式块模型

    定义了 OpenAI 兼容的流式响应格式。

    Attributes:
        id: 响应ID，自动生成
        object: 对象类型，固定为 "chat.completion.chunk"
        created: 创建时间戳
        model: 使用的模型名称
        choices: 流式选项列表
    """

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "doubao"
    choices: List[StreamChoice]


class ModelInfo(BaseModel):
    """
    模型信息模型

    表示单个模型的基本信息。

    Attributes:
        id: 模型ID
        object: 对象类型，固定为 "model"
        created: 创建时间戳
        owned_by: 模型所有者
    """

    id: str = "doubao"
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "doubao"


class ModelListResponse(BaseModel):
    """
    模型列表响应模型

    定义了获取模型列表的响应格式。

    Attributes:
        object: 对象类型，固定为 "list"
        data: 模型信息列表
    """

    object: str = "list"
    data: List[ModelInfo]
