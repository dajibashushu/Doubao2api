"""
Doubao2api - Cookie 提取助手

本模块提供了通过扫码登录获取豆包 Cookie 的功能。

@author: Doubao2api
@version: 1.0.0
"""
import logging
import re
from typing import Dict, Optional

from config import config
from doubao_client import load_cookies_from_file

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Cookie 验证所需的关键 Cookie 名称
IMPORTANT_COOKIE_NAMES = ["ttwid", "sessionid", "sid_tt"]


def print_banner() -> None:
    """打印横幅"""
    print("=" * 60)
    print("  豆包 Cookie 提取助手")
    print("  Doubao Cookie Extractor")
    print("=" * 60)
    print()


def validate_cookies(cookies: Dict[str, str]) -> bool:
    """
    验证 Cookie 是否有效

    检查是否包含必要的 Cookie 项。

    Args:
        cookies: Cookie 字典

    Returns:
        如果包含至少 2 个必要的 Cookie 则返回 True
    """
    found = sum(1 for name in IMPORTANT_COOKIE_NAMES if name in cookies)
    return found >= 2


def save_cookies_to_file(
    cookies: Dict[str, str],
    cookie_file: Optional[str] = None
) -> None:
    """
    保存 Cookie 到文件

    将 Cookie 字典转换为字符串格式并保存到文件。

    Args:
        cookies: Cookie 字典
        cookie_file: Cookie 文件路径，默认使用配置中的路径
    """
    cookie_file = cookie_file or config.cookie_file
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])

    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write(cookie_str)

    logger.info(f"Cookie 已保存到 {cookie_file}")


def _update_config_file(
    device_id: Optional[str] = None,
    web_id: Optional[str] = None,
    tea_uuid: Optional[str] = None,
    fp: Optional[str] = None
) -> None:
    """
    更新 config.py 中的配置

    Args:
        device_id: 设备ID
        web_id: Web ID
        tea_uuid: Tea UUID
        fp: 指纹信息
    """
    if not any([device_id, web_id, tea_uuid, fp]):
        return

    config_path = "config.py"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        if device_id:
            content = re.sub(
                r'default_device_id:\s*str\s*=\s*"[^"]*"',
                f'default_device_id: str = "{device_id}"',
                content
            )

        if web_id:
            content = re.sub(
                r'default_web_id:\s*str\s*=\s*"[^"]*"',
                f'default_web_id: str = "{web_id}"',
                content
            )

        if tea_uuid:
            content = re.sub(
                r'default_tea_uuid:\s*str\s*=\s*"[^"]*"',
                f'default_tea_uuid: str = "{tea_uuid}"',
                content
            )

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("config.py 已更新")

    except Exception as e:
        logger.warning(f"更新 config.py 失败: {e}")


def _update_config_with_cookies(cookies: Dict[str, str]) -> None:
    """
    从 Cookie 中更新配置信息

    Args:
        cookies: Cookie 字典
    """
    device_id = cookies.get('device_id', '')
    web_id = cookies.get('web_id', '')
    tea_uuid = cookies.get('tea_uuid', '')
    fp = cookies.get('s_v_web_id', '')

    if any([device_id, web_id, tea_uuid]):
        _update_config_file(device_id, web_id, tea_uuid, fp)


def _display_cookie_check(cookies: Dict[str, str]) -> None:
    """
    显示 Cookie 检查结果

    Args:
        cookies: Cookie 字典
    """
    print("\nCookie 检查:")
    check_cookies = ["ttwid", "passport_csrf_token", "sessionid", "sid_guard"]
    for name in check_cookies:
        if name in cookies:
            print(f"   ✓ {name}: {cookies[name][:20]}...")
        else:
            print(f"   - {name}: 未找到")


def _print_success_info() -> None:
    """打印成功信息"""
    print("\n现在可以启动代理服务了:")
    print("   python main.py")
    print()
    print("cc-switch 配置:")
    print(f"   base_url: http://localhost:{config.port}/v1")
    print(f"   api_key:  doubao")
    print()


def _check_existing_cookies() -> bool:
    """
    检查是否已存在有效的 Cookie

    Returns:
        是否已存在有效 Cookie
    """
    try:
        cookies = load_cookies_from_file()
        if cookies and validate_cookies(cookies):
            print("\n检测到已存在有效的 Cookie:")
            _display_cookie_check(cookies)
            print("\n是否重新获取？(y/N): ", end="")
            choice = input().strip().lower()
            return choice != 'y'
        return False
    except Exception:
        return False


def _handle_qr_login() -> bool:
    """
    处理扫码登录

    Returns:
        是否登录成功
    """
    try:
        from qr_login import qr_login

        print("\n正在启动扫码登录...")
        print("将自动打开 Chrome 浏览器，请在浏览器中完成登录")
        print()

        success, cookies, config_info = qr_login()

        if success and cookies:
            print(f"\n✓ 登录成功！获取到 {len(cookies)} 个 Cookie")

            # 显示关键 Cookie
            important = ["ttwid", "sessionid", "sid_tt", "s_v_web_id"]
            print("\n关键 Cookie:")
            for name in important:
                if name in cookies:
                    print(f"   ✓ {name}: {cookies[name][:20]}...")
                else:
                    print(f"   - {name}: 未获取")

            # 保存 Cookie
            save_cookies_to_file(cookies)

            # 更新配置
            all_info = {**cookies, **config_info}
            _update_config_with_cookies(all_info)

            _print_success_info()
            return True
        else:
            print("\n✗ 登录失败或超时")
            return False

    except ImportError:
        print("\n✗ 请先安装依赖:")
        print("   pip install websocket-client")
        return False
    except Exception as e:
        logger.error(f"扫码登录失败: {e}")
        return False


def main() -> None:
    """主函数"""
    print_banner()

    # 检查是否已存在有效的 Cookie
    if _check_existing_cookies():
        print("\n使用现有 Cookie 启动服务...")
        print("   python main.py")
        return

    # 直接启动扫码登录
    _handle_qr_login()


if __name__ == "__main__":
    main()
