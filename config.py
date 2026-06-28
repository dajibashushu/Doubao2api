"""
Doubao2api - 配置文件

本模块定义了代理服务的所有配置项，包括服务器配置、API配置、请求头等。
所有配置项均使用 dataclass 进行管理，支持类型提示和默认值。

@author: Doubao2api
@version: 1.0.0
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Config:
    """
    代理配置类

    包含服务器配置、Doubao API配置、通用查询参数、默认请求头等配置项。
    使用 dataclass 装饰器实现，支持类型提示和默认值。

    Attributes:
        host: 服务器监听地址，默认为 "0.0.0.0"
        port: 服务器监听端口，默认为 9876
        doubao_base_url: 豆包API基础URL
        bot_id: 豆包机器人ID
        aid: 应用ID
        version_code: 版本号
        pc_version: PC端版本号
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
    pc_version: str = "3.23.10"
    pkg_type: str = "release_version"
    device_platform: str = "web"
    web_platform: str = "browser"
    samantha_web: str = "1"
    use_olympus_account: str = "1"
    language: str = "zh"
    region: str = "CN"
    sys_region: str = "CN"

    # 默认请求头
    default_headers: Dict[str, str] = field(default_factory=lambda: {
        "accept": "application/json, text/plain, */*",
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

    # 可用模型列表
    available_models: List[str] = field(default_factory=lambda: [
        "doubao-pro",
        "doubao-lite",
        "doubao-1.5-pro",
        "doubao-1.5-lite",
    ])


# 全局配置实例
config = Config()
