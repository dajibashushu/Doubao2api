# Doubao2api

项目使用MIMO模型辅助编写。

将豆包 (doubao.com/chat) 封装为 OpenAI 兼容 API 的代理服务。

## 功能

- OpenAI Chat Completions API 兼容
- 流式 (SSE) 和非流式响应
- 扫码登录自动获取配置
- 多模型支持

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

### 4. 配置客户端

```
base_url: http://localhost:9876/v1
api_key:  doubao
model:    doubao-pro
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/models` | GET | 列出可用模型 |
| `/v1/chat/completions` | POST | 聊天补全 |
| `/health` | GET | 健康检查 |
| `/reload-cookies` | POST | 重新加载 Cookie |

## 使用示例

### curl

```bash
curl http://localhost:9876/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-pro",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

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

- `doubao-pro` - 专业版
- `doubao-lite` - 轻量版
- `doubao-1.5-pro` - 1.5 专业版
- `doubao-1.5-lite` - 1.5 轻量版

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
