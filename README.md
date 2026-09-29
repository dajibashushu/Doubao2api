> 🔧 **本 fork 的改动（二创）**：基于上游 [Hu410/Doubao2api](https://github.com/Hu410/Doubao2api)（基线 `b8f108b`），
> 在 `main.py` 中新增了**图像生成相关功能**（OpenAI 兼容的 `POST /v1/images/generations`、返回无水印原图、
> `size` 自动换算画幅比例、内容审核拒绝可读化、`/v1/*` 错误统一 OpenAI 格式、可选 `DOUBAO_API_KEY` 鉴权等）。
> **clone 本 fork 即可直接运行，无需再打补丁。** 完整说明见 **[IMAGES_PATCH.md](IMAGES_PATCH.md)**。

# Doubao2api

项目使用MIMO模型辅助编写。

将豆包 (doubao.com/chat) 封装为 OpenAI 兼容 API 的代理服务。

> 协议基于豆包网页版 pc_version 3.38.5 (2026-09) 前端逆向适配。

## 功能

- OpenAI Chat Completions API 兼容
- 流式 (SSE) 和非流式响应
- 扫码登录自动获取配置
- 多模型支持（映射豆包 快速 / Turbo / Pro / Lite / Auto）
- **图像生成 API 兼容（`POST /v1/images/generations`，返回无水印原图）**
- **可选 API Key 鉴权（设置环境变量 `DOUBAO_API_KEY` 后生效）**

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Cookie

```bash
python cookie_helper.py
```

自动打开 Chrome 浏览器，在浏览器中完成登录，程序会自动获取 Cookie。

### 3. 启动服务

```bash
python main.py
```

或双击 `start.bat` (Windows)

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/models` | GET | 列出可用模型 |
| `/v1/chat/completions` | POST | 聊天补全 |
| `/v1/images/generations` | POST | **图像生成（OpenAI Images 兼容，返回无水印原图）** |
| `/health` | GET | 健康检查 |
| `/reload-cookies` | POST | 重新加载 Cookie |

## 使用示例

### curl

```bash
curl http://localhost:9876/v1/chat/completions \
    "model": "doubao-pro",
  
```

### curl（图像生成）

```bash
curl http://localhost:9876/v1/images/generations   
"model": "doubao-seedream-5-0-260128"
```

返回 `data[0].url` 为**无水印原图**，`data[0].watermarked_url` 为带水印版本；
`response_format=b64_json` 时直接返回 base64。更多说明见 [IMAGES_PATCH.md](IMAGES_PATCH.md)。

### Python

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:9876/v1", api_key="doubao")

response = client.chat.completions.create(
    model="doubao-pro",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

## 可用模型

| 模型名 | 豆包内部模型 | 说明 |
|--------|-------------|------|
| `doubao-fast` | model_item_key=0 | 豆包 快速（默认，对话模式） |
| `doubao-turbo` | model_item_key=3 | 豆包 2.1 Turbo（对话模式） |
| `doubao-auto` | model_item_key=9 | 工作任务 Auto |
| `doubao-work-turbo` | model_item_key=4 | 工作任务 Turbo |
| `doubao-pro` | model_item_key=5 | 工作任务 Pro |
| `doubao-lite` | seed-lite-7b | 豆包 2.1 Lite |

旧模型名 `doubao-1.5-pro` / `doubao-1.5-lite` 仍兼容，分别映射 Turbo / Lite。
未识别的模型名回退到 `doubao-fast`。

## 项目结构

```
Doubao2api/
├── main.py              # FastAPI 主服务
├── doubao_client.py     # 豆包 API 客户端
├── models.py            # 数据模型
├── config.py            # 配置文件
├── cookie_helper.py     # Cookie 提取助手
├── qr_login.py          # 扫码登录模块
├── cookies.txt          # Cookie 文件
├── requirements.txt     # 依赖列表
├── start.bat            # Windows 启动脚本
├── IMAGES_PATCH.md       # 本 fork 的二创说明与新增功能
├── 0001-images-generations.patch  # 图像生成补丁文件
└── README.md            # 本文档
```

## 常见问题

**Q: 提示 "需要验证码" 怎么办？**

A: 在浏览器中手动完成验证码，然后重新获取 Cookie。

**Q: Cookie 多久过期？**

A: 通常几天到几周。遇到认证错误时重新运行 `python cookie_helper.py`。

**Q: 扫码登录失败？**

A: 确保已安装 Chrome 浏览器，且端口 9222 未被占用。

## 注意

- 仅供学习和研究使用
- 请遵守豆包使用条款
- Cookie 属于敏感信息，勿泄露
