"""
Doubao2api - 扫码登录模块

本模块实现了豆包的扫码登录功能，使用 Chrome DevTools Protocol：
1. 启动 Chrome 浏览器
2. 打开豆包登录页面
3. 等待用户扫码完成
4. 自动提取 Cookie 和配置信息

@author: Doubao2api
@version: 1.0.0
"""
import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
import websocket
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 豆包登录页面 URL
DOUBAO_LOGIN_URL = "https://www.doubao.com/chat"

# 等待扫码超时时间（秒）
QR_CODE_TIMEOUT = 120

# Chrome 可执行文件路径（Windows）
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


class ChromeDebugger:
    """
    Chrome DevTools Protocol 客户端

    通过 WebSocket 连接到 Chrome 浏览器，使用 CDP 协议控制浏览器。
    """

    def __init__(self, websocket_url: str) -> None:
        """
        初始化 Chrome 调试器

        Args:
            websocket_url: WebSocket 连接 URL
        """
        self.ws = websocket.create_connection(websocket_url)
        self.msg_id = 0

    def send_command(self, method: str, params: Optional[Dict] = None, timeout: int = 30) -> Dict:
        """
        发送 CDP 命令

        Args:
            method: CDP 方法名
            params: 方法参数
            timeout: 超时时间（秒）

        Returns:
            响应结果
        """
        self.msg_id += 1
        message = {
            "id": self.msg_id,
            "method": method,
            "params": params or {}
        }
        self.ws.send(json.dumps(message))

        # 等待响应
        start_time = time.time()
        while time.time() - start_time < timeout:
            self.ws.settimeout(timeout)
            try:
                raw_data = self.ws.recv()
                response = json.loads(raw_data)
                if response.get("id") == self.msg_id:
                    return response
            except websocket.WebSocketTimeoutException:
                break
            except Exception:
                break
        return {"error": "Timeout or error"}

    def navigate(self, url: str) -> None:
        """
        导航到指定 URL

        Args:
            url: 目标 URL
        """
        self.send_command("Page.navigate", {"url": url})

    def evaluate(self, expression: str) -> Any:
        """
        执行 JavaScript 表达式

        Args:
            expression: JavaScript 表达式

        Returns:
            执行结果
        """
        result = self.send_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("result", {}).get("value")

    def get_cookies(self) -> List[Dict]:
        """
        获取所有 Cookie

        Returns:
            Cookie 列表
        """
        result = self.send_command("Network.getCookies")
        return result.get("result", {}).get("cookies", [])

    def take_screenshot(self) -> Optional[str]:
        """
        截取页面截图

        Returns:
            Base64 编码的截图数据
        """
        result = self.send_command("Page.captureScreenshot", {
            "format": "png"
        })
        return result.get("result", {}).get("data")

    def wait_for_navigation(self, timeout: int = 10) -> bool:
        """
        等待页面导航完成

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否导航成功
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = self.evaluate("document.readyState")
            if result == "complete":
                return True
            time.sleep(0.5)
        return False

    def close(self) -> None:
        """关闭连接"""
        try:
            self.ws.close()
        except Exception:
            pass


def find_chrome_executable() -> Optional[str]:
    """
    查找 Chrome 可执行文件路径

    Returns:
        Chrome 可执行文件路径，如果未找到返回 None
    """
    # 检查环境变量
    chrome_path = os.environ.get("CHROME_PATH")
    if chrome_path and os.path.exists(chrome_path):
        return chrome_path

    # 检查常见路径
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path

    # 尝试使用 where 命令查找
    try:
        result = subprocess.run(
            ["where", "chrome"],
            capture_output=True,
            text=True,
            shell=True
        )
        if result.returncode == 0:
            path = result.stdout.strip().split("\n")[0]
            if os.path.exists(path):
                return path
    except Exception:
        pass

    return None


def launch_chrome_with_debugging(port: int = 9222) -> Optional[subprocess.Popen]:
    """
    启动 Chrome 浏览器（带调试端口）

    Args:
        port: 调试端口号

    Returns:
        Chrome 进程对象，如果启动失败返回 None
    """
    chrome_path = find_chrome_executable()
    if not chrome_path:
        logger.error("未找到 Chrome 浏览器，请设置 CHROME_PATH 环境变量")
        return None

    # 创建临时用户数据目录
    user_data_dir = tempfile.mkdtemp(prefix="chrome_debug_")

    # 启动参数
    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "--disable-extensions",
        "--disable-default-apps",
        "--disable-translate",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
    ]

    try:
        logger.info(f"启动 Chrome 浏览器: {chrome_path}")
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # 等待 Chrome 启动
        time.sleep(2)
        return process
    except Exception as e:
        logger.error(f"启动 Chrome 失败: {e}")
        return None


def get_websocket_url(port: int = 9222, use_page: bool = True) -> Optional[str]:
    """
    获取 Chrome DevTools WebSocket URL

    Args:
        port: 调试端口号
        use_page: 是否获取页面的 WebSocket URL（True）还是浏览器的（False）

    Returns:
        WebSocket URL，如果获取失败返回 None
    """
    import urllib.request

    try:
        if use_page:
            # 获取页面列表，使用第一个 type 为 "page" 的 WebSocket URL
            url = f"http://localhost:{port}/json"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                pages = json.loads(response.read().decode())
                for page in pages:
                    if page.get("type") == "page":
                        return page.get("webSocketDebuggerUrl")
        # 获取浏览器的 WebSocket URL
        url = f"http://localhost:{port}/json/version"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return data.get("webSocketDebuggerUrl")
    except Exception as e:
        logger.error(f"获取 WebSocket URL 失败: {e}")
        return None


def get_page_list(port: int = 9222) -> List[Dict]:
    """
    获取 Chrome 页面列表

    Args:
        port: 调试端口号

    Returns:
        页面列表
    """
    import urllib.request

    try:
        url = f"http://localhost:{port}/json"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"获取页面列表失败: {e}")
        return []


def capture_qrcode_from_page(debugger: ChromeDebugger) -> Optional[bytes]:
    """
    从页面捕获二维码图片

    Args:
        debugger: Chrome 调试器实例

    Returns:
        二维码图片数据（Base64 解码后），如果捕获失败返回 None
    """
    try:
        # 方法1: 查找二维码 img 元素并截图
        qr_selectors = [
            'img[src*="qrcode"]',
            'img[src*="qr"]',
            '.qrcode img',
            '.qr-code img',
            '[class*="qr"] img',
            'img[class*="qr"]',
        ]

        for selector in qr_selectors:
            # 检查元素是否存在
            exists = debugger.evaluate(f'''!!document.querySelector("{selector}")''')
            if exists:
                # 获取元素位置和尺寸
                rect = debugger.evaluate(f'''(() => {{
                    const el = document.querySelector("{selector}");
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {{x: r.x, y: r.y, width: r.width, height: r.height}};
                }})()''')

                if rect and rect.get("width", 0) > 50:
                    logger.info(f"找到二维码元素: {selector}")
                    # 截取整个页面，后续可以裁剪
                    screenshot_b64 = debugger.take_screenshot()
                    if screenshot_b64:
                        import base64
                        return base64.b64decode(screenshot_b64)

        # 方法2: 查找 canvas 元素
        canvas_data = debugger.evaluate('''(() => {
            const canvas = document.querySelector('canvas');
            if (canvas) {
                return canvas.toDataURL('image/png');
            }
            return null;
        })()''')

        if canvas_data and canvas_data.startswith('data:image'):
            import base64
            base64_data = canvas_data.split(',')[1]
            return base64.b64decode(base64_data)

        # 方法3: 截取整个页面
        screenshot_b64 = debugger.take_screenshot()
        if screenshot_b64:
            import base64
            return base64.b64decode(screenshot_b64)

        return None

    except Exception as e:
        logger.error(f"捕获二维码失败: {e}")
        return None


def display_qrcode_in_terminal(image_data: bytes) -> bool:
    """
    在终端显示二维码

    使用 ASCII 字符在终端中显示二维码。

    Args:
        image_data: 二维码图片数据

    Returns:
        是否成功显示
    """
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data))
        img = img.convert('L')

        width, height = img.size

        # 缩放图片
        target_size = 25
        ratio = min(target_size / width, target_size / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        pixels = list(img.getdata())

        print("\n" + "=" * 50)
        print("  请使用豆包 APP 扫描下方二维码登录")
        print("=" * 50)
        print()

        for y in range(new_height):
            line = ""
            for x in range(new_width):
                pixel = pixels[y * new_width + x]
                if pixel < 128:
                    line += "██"
                else:
                    line += "  "
            print(f"  {line}")

        print()
        print("=" * 50)
        print(f"  二维码将在 {QR_CODE_TIMEOUT} 秒后过期")
        print("=" * 50)

        return True

    except ImportError:
        logger.warning("Pillow 未安装，无法在终端显示二维码")
        return False
    except Exception as e:
        logger.error(f"显示二维码失败: {e}")
        return False


def qr_login(
    timeout: int = QR_CODE_TIMEOUT,
    port: int = 9222
) -> Tuple[bool, Dict[str, str], Dict[str, str]]:
    """
    扫码登录

    启动 Chrome 浏览器，打开豆包登录页面，等待用户扫码登录。

    Args:
        timeout: 等待扫码超时时间（秒）
        port: Chrome 调试端口号

    Returns:
        (success, cookies, config) 三元组：
        - success: 是否登录成功
        - cookies: Cookie 字典
        - config: 配置信息字典
    """
    cookies: Dict[str, str] = {}
    config_info: Dict[str, str] = {}
    chrome_process = None

    try:
        # 启动 Chrome
        chrome_process = launch_chrome_with_debugging(port)
        if not chrome_process:
            return False, {}, {}

        # 获取 WebSocket URL
        ws_url = get_websocket_url(port)
        if not ws_url:
            logger.error("无法获取 Chrome DevTools WebSocket URL")
            return False, {}, {}

        logger.info(f"连接到 Chrome DevTools: {ws_url}")
        debugger = ChromeDebugger(ws_url)

        try:
            # 启用必要的域
            debugger.send_command("Page.enable")
            debugger.send_command("Network.enable")
            debugger.send_command("Runtime.enable")

            # 打开豆包页面
            logger.info("正在打开豆包登录页面...")
            debugger.navigate(DOUBAO_LOGIN_URL)
            debugger.wait_for_navigation(timeout=30)
            time.sleep(5)  # 增加等待时间，确保页面完全加载

            # 检查当前页面状态
            current_url = debugger.evaluate("window.location.href")
            page_title = debugger.evaluate("document.title")
            logger.info(f"当前页面: {page_title} - {current_url}")

            # 检查是否需要登录 - 使用更严格的检查
            def check_login_status() -> bool:
                """检查登录状态"""
                # 检查是否有聊天输入框
                has_input = debugger.evaluate('''!!(
                    document.querySelector('textarea') ||
                    document.querySelector('[contenteditable="true"]') ||
                    document.querySelector('input[type="text"]')
                )''')

                # 检查是否有登录相关元素
                has_login = debugger.evaluate('''!!(
                    document.querySelector('[class*="login"]') ||
                    document.querySelector('[class*="Login"]') ||
                    document.querySelector('[class*="qrcode"]') ||
                    document.querySelector('[class*="scan"]') ||
                    document.querySelector('button[class*="login"]')
                )''')

                # 检查页面标题
                title = debugger.evaluate("document.title") or ""
                has_login_title = "登录" in title or "login" in title.lower()

                logger.debug(f"登录状态检查: input={has_input}, login={has_login}, title={has_login_title}")

                # 如果有输入框且没有登录元素，认为已登录
                if has_input and not has_login and not has_login_title:
                    return True
                return False

            is_logged_in = check_login_status()

            if is_logged_in:
                logger.info("已登录，直接获取 Cookie")
            else:
                logger.info("未检测到登录状态，等待用户登录...")
                print("\n" + "=" * 60)
                print("  请在浏览器中完成登录")
                print("  登录成功后程序将自动继续")
                print("=" * 60)
                print()

                # 等待用户登录
                start_time = time.time()
                login_check_interval = 2  # 每2秒检查一次

                while time.time() - start_time < timeout:
                    # 检查登录状态
                    is_logged_in = check_login_status()

                    if is_logged_in:
                        logger.info("检测到登录成功！")
                        print("\n✓ 登录成功！正在获取配置...")
                        break

                    # 检查页面URL变化
                    current_url = debugger.evaluate("window.location.href")
                    if '/chat' in str(current_url) and 'login' not in str(current_url):
                        # URL 已跳转到聊天页面，等待加载
                        logger.info("页面已跳转到聊天页面，等待加载...")
                        time.sleep(3)
                        is_logged_in = check_login_status()
                        if is_logged_in:
                            logger.info("登录成功！")
                            print("\n✓ 登录成功！正在获取配置...")
                            break

                    # 显示剩余时间
                    elapsed = int(time.time() - start_time)
                    remaining = timeout - elapsed
                    if remaining > 0 and elapsed % 10 == 0:
                        print(f"  等待登录中... 剩余 {remaining} 秒")

                    time.sleep(login_check_interval)

                if not is_logged_in:
                    logger.error("登录超时")
                    print("\n✗ 登录超时，请重新尝试")
                    return False, {}, {}

            # 登录成功，等待页面完全加载
            logger.info("等待页面完全加载...")
            time.sleep(5)

            # 发送测试消息获取配置
            logger.info("发送测试消息获取配置...")
            try:
                input_exists = debugger.evaluate('''!!(
                    document.querySelector('textarea') ||
                    document.querySelector('[contenteditable="true"]')
                )''')

                if input_exists:
                    # 点击输入框
                    debugger.evaluate('''(() => {
                        const input = document.querySelector('textarea') ||
                                      document.querySelector('[contenteditable="true"]');
                        if (input) input.click();
                    })()''')
                    time.sleep(0.5)

                    # 输入测试消息
                    debugger.evaluate('''(() => {
                        const input = document.querySelector('textarea') ||
                                      document.querySelector('[contenteditable="true"]');
                        if (input) {
                            input.focus();
                            input.textContent = 'test';
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    })()''')
                    time.sleep(0.5)

                    # 发送消息（按 Enter）
                    debugger.send_command("Input.dispatchKeyEvent", {
                        "type": "keyDown",
                        "key": "Enter",
                        "code": "Enter",
                        "windowsVirtualKeyCode": 13,
                        "nativeVirtualKeyCode": 13,
                    })
                    debugger.send_command("Input.dispatchKeyEvent", {
                        "type": "keyUp",
                        "key": "Enter",
                        "code": "Enter",
                        "windowsVirtualKeyCode": 13,
                        "nativeVirtualKeyCode": 13,
                    })
                    time.sleep(5)

            except Exception as e:
                logger.warning(f"发送测试消息失败: {e}")

            # 获取 Cookie
            logger.info("获取 Cookie...")
            cdp_cookies = debugger.get_cookies()
            for cookie in cdp_cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name and value:
                    cookies[name] = value

            # 提取配置信息
            current_url = debugger.evaluate("window.location.href")
            logger.info(f"当前 URL: {current_url}")

            try:
                config_data = debugger.evaluate('''(() => {
                    const result = {};

                    const urlParams = new URLSearchParams(window.location.search);
                    result.device_id = urlParams.get('device_id') || '';
                    result.web_id = urlParams.get('web_id') || '';
                    result.tea_uuid = urlParams.get('tea_uuid') || '';

                    try {
                        const keys = ['device_id', 'web_id', 'tea_uuid', 's_v_web_id'];
                        for (const key of keys) {
                            const value = localStorage.getItem(key);
                            if (value) result[key] = value;
                        }
                    } catch (e) {}

                    return result;
                })()''')

                if config_data:
                    for key, value in config_data.items():
                        if value:
                            config_info[key] = value

            except Exception as e:
                logger.warning(f"提取配置信息失败: {e}")

            if 's_v_web_id' in cookies:
                config_info['fp'] = cookies['s_v_web_id']

            logger.info(f"成功获取 {len(cookies)} 个 Cookie")
            return True, cookies, config_info

        finally:
            debugger.close()

    except Exception as e:
        logger.error(f"扫码登录失败: {e}")
        return False, {}, {}
    finally:
        if chrome_process:
            try:
                chrome_process.terminate()
                chrome_process.wait(timeout=5)
            except Exception:
                pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("豆包扫码登录")
    print("=" * 50)

    success, cookies, config_info = qr_login()

    if success:
        print("\n登录成功！")
        print(f"获取到 {len(cookies)} 个 Cookie")
        print(f"配置信息: {config_info}")
    else:
        print("\n登录失败！")
