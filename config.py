"""
Doubao2api - 配置文件

本模块定义了代理服务的所有配置项，包括服务器配置、API配置、请求头、模型映射等。
所有配置项均使用 dataclass 进行管理，支持类型提示和默认值。

协议参数基于 2026-09 抓包的豆包网页版 (pc_version 3.38.5) 前端逆向得出。

@author: Doubao2api
@version: 2.0.0
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ModelProfile:
    """
    单个豆包模型的请求参数档案

    Attributes:
        model_item_key: 豆包内部模型键（前端 modeSelectConfig 中的 model_item_key）
        agent_mode: 智能体模式（2=对话, 1=工作任务）
        conversation_mode: 会话模式（1=chat, 2=office, 3=creation）
        reasoning_effort: 推理力度（3=低, 4=中, 5=高）
        model_extra_params: 模型额外参数（如 total_window_size）
    """
    model_item_key: str
    agent_mode: int = 2
    conversation_mode: int = 1
    reasoning_effort: int = 3
    model_extra_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    """
    代理配置类

    包含服务器配置、Doubao API配置、通用查询参数、默认请求头、模型映射等配置项。

    Attributes:
        host: 服务器监听地址，默认为 "0.0.0.0"
        port: 服务器监听端口，默认为 9876
        doubao_base_url: 豆包API基础URL
        bot_id: 豆包机器人ID
        aid: 应用ID
        version_code: 版本号
        pc_version: PC端版本号（跟随网页版更新，当前 3.38.5）
        pkg_type: 包类型
        device_platform: 设备平台
        web_platform: Web平台
        samantha_web: Samantha Web标识
        use_olympus_account: 使用Olympus账户标识
        language: 语言
        region: 地区
        sys_region: 系统地区
        default_headers: 默认请求头
        cookie_file: Cookie文件路径
        model_profiles: API模型名 -> 模型档案映射
        available_models: 可用模型列表
    """

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 9876

    # Doubao API 配置
    doubao_base_url: str = "https://www.doubao.com"
    bot_id: str = "7338286299411103781"

    # 通用查询参数
    aid: str = "497858"
    version_code: str = "20800"
    pc_version: str = "3.38.5"
    pkg_type: str = "release_version"
    device_platform: str = "web"
    web_platform: str = "browser"
    samantha_web: str = "1"
    use_olympus_account: str = "1"
    language: str = "zh"
    region: str = "CN"
    sys_region: str = "CN"

    # 默认请求头（agw-js-conv 为 SSE 网关要求的固定头）
    default_headers: Dict[str, str] = field(default_factory=lambda: {
        "accept": "text/event-stream",
        "accept-language": "zh-CN,zh;q=0.9",
        "agw-js-conv": "str",
        "content-type": "application/json",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
    })

    # Cookie 文件路径
    cookie_file: str = "cookies.txt"

    # 模型映射：对外 API 模型名 -> 豆包模型档案
    # model_item_key / agent_mode / reasoning_effort 来自网页版
    # _ROUTER_DATA.actionBarBriefList.modeSelectData 配置
    model_profiles: Dict[str, ModelProfile] = field(default_factory=lambda: {
        # 对话模式
        "doubao-fast": ModelProfile("0", agent_mode=2, conversation_mode=1, reasoning_effort=3),
        "doubao-turbo": ModelProfile("3", agent_mode=2, conversation_mode=1, reasoning_effort=4),
        # 工作任务模式
        "doubao-auto": ModelProfile("9", agent_mode=1, conversation_mode=1, reasoning_effort=5,
                                    model_extra_params={"total_window_size": "256000"}),
        "doubao-work-turbo": ModelProfile("4", agent_mode=1, conversation_mode=1, reasoning_effort=5,
                                          model_extra_params={"total_window_size": "256000"}),
        "doubao-pro": ModelProfile("5", agent_mode=1, conversation_mode=1, reasoning_effort=5,
                                   model_extra_params={"total_window_size": "256000"}),
        "doubao-lite": ModelProfile("seed-lite-7b", agent_mode=1, conversation_mode=1, reasoning_effort=5,
                                    model_extra_params={"memory_profile": "256k", "total_window_size": "256000"}),
        # 旧模型名兼容别名
        "doubao-1.5-pro": ModelProfile("3", agent_mode=2, conversation_mode=1, reasoning_effort=4),
        "doubao-1.5-lite": ModelProfile("seed-lite-7b", agent_mode=1, conversation_mode=1, reasoning_effort=5),
    })

    # 可用模型列表（/v1/models 展示顺序）
    available_models: List[str] = field(default_factory=lambda: [
        "doubao-fast",
        "doubao-turbo",
        "doubao-auto",
        "doubao-work-turbo",
        "doubao-pro",
        "doubao-lite",
    ])

    # 请求模型名不在映射中时使用的兜底模型
    default_model: str = "doubao-fast"

    def get_model_profile(self, model_name: str) -> ModelProfile:
        """
        获取模型档案，未知模型名回退到默认模型

        Args:
            model_name: 对外 API 模型名

        Returns:
            对应的 ModelProfile
        """
        return self.model_profiles.get(model_name) or self.model_profiles[self.default_model]


# 全局配置实例
config = Config()
