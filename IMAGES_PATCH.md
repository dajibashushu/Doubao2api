# doubao2api 图像生成补丁（二创）

> **二创来源**：本项目基于 [**Hu410/Doubao2api**](https://github.com/Hu410/Doubao2api)（作者 **Hu410**）二次开发，
> 基线版本 `main`/`master` @ `b8f108b`。上游提供了豆包 Web 转 OpenAI Chat Completions 的全部基础能力
> （Cookie 扫码登录、模型映射、流式响应等），本 fork 只在其之上**新增图像生成相关功能**。
>
> clone 本 fork 即可直接运行（补丁已内置），不需要再打补丁。

---

## 一、新增了哪些功能

| # | 功能 | 说明 |
|---|------|------|
| 1 | **`POST /v1/images/generations`** | 新增 OpenAI Images 兼容的图像生成接口（上游只有文本对话，调这个会 404） |
| 2 | **返回无水印原图** | 生成结果里优先返回无水印的原始图；同时在响应里额外给一个 `watermarked_url` 字段保留带水印版本 |
| 3 | **`size` 自动换算比例** | 客户端传 OpenAI 风格的 `size`（如 `1024x1792`）会自动换算成上游需要的画幅比例；认不出的尺寸取最接近的比例；不传则用 `auto` |
| 4 | **`n` 与 `response_format`** | 支持一次要 1–4 张；`response_format` 支持 `url`（默认，直接给图片直链）与 `b64_json`（服务端下载后 base64 返回） |
| 5 | **内容审核被拒时给可读错误** | 被上游内容审核拦截时不再只回一个"没有图片"的 502，而是返回 `400` 并带上拒绝原因 |
| 6 | **`/v1/*` 错误统一成 OpenAI 格式** | 错误体统一为 `{"error": {"message", "type", "code"}}`，修掉部分客户端（实测 iOS 应用）因解析不了 `{"detail": ...}` 而报「未能读取数据，因为它的格式不正确」的问题 |
| 7 | **可选 API Key 鉴权** | 上游默认**没有任何鉴权**，挂到公网等于把自己的豆包账号送人。新增一层可选闸门：设置环境变量 `DOUBAO_API_KEY` 才启用，接受 `Authorization: Bearer <key>`、`x-api-key: <key>`、`?key=<key>` 三种传法，`/health` 永远放行（探活） |
| 8 | **兼容客户端多余参数** | `image_size` / `guidance_scale` / `batch_size` 等第三方客户端会带的非标准字段直接忽略，不影响调用 |

改动集中在 `main.py`（另有同目录 `0001-*.patch` 供对比查看）。

---

## 二、安装与运行

```bash
git clone https://github.com/dajibashushu/Doubao2api.git
cd Doubao2api
pip install -r requirements.txt
python main.py          # 默认监听 9876
```

- 首次使用仍需按上游 README 的说明获取并填入豆包登录 Cookie（扫码登录流程与上游完全一致）。
- 要对外暴露时，强烈建议设置 API Key：

```bash
# Linux/macOS
export DOUBAO_API_KEY=你的key
# Windows (PowerShell)
$env:DOUBAO_API_KEY="你的key"
```

---

## 三、调用示例

```bash
curl http://127.0.0.1:9876/v1/images/generations \
  -H "Authorization: Bearer $DOUBAO_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"doubao","prompt":"一只穿西装的柯基在办公室开会","n":1,"size":"1024x1024"}'
```

返回：

```json
{
  "created": 1790670000,
  "model": "doubao",
  "data": [
    { "url": "https://.../rc_gen_image/....jpeg", "watermarked_url": "https://.../rc_gen_image/....png" }
  ]
}
```

> **Windows 上的注意事项**：用 `curl -d "...中文 JSON..."` 内联传中文时，服务端可能收到乱码并判 `invalid JSON body`。
> 建议先把请求体写进文件，再 `curl --data-binary @req.json`。

---

## 四、实测数据（2026-09-29）

| 场景 | 结果 |
|------|------|
| 单张生图（`1024x1792`） | 本地约 **17 s**；经反向代理/隧道约 **30 s** |
| 返回图 | PNG，约 3.6 MB，确认为无水印版本 |
| 未带 API Key 调用 | `401` |
| 短 prompt（`1024x1024`） | `200`，正常出图 |

---

## 五、已知限制与风险

- **依赖有效登录 Cookie**：Cookie 失效后所有接口不可用，需重新登录（同上游）。
- **生图比文本更容易触发上游风控**：失败请等待一段时间再试，**不要连续重试**，严重时可能触发验证码。
- **内容审核在上游**：本补丁无法绕过，命中时只能修改提示词（长文本、敏感话题的命中率较高）。
- **无水印原图取决于上游当前行为**：上游策略变化后可能拿不到，届时回退为带水印版本。
- **未实现** `/v1/images/edits`（图片编辑）。
- `size` 只用于换算画幅比例，**不保证输出像素与请求完全一致**。

---

## 六、致谢与许可

- **上游项目**：[Hu410/Doubao2api](https://github.com/Hu410/Doubao2api)（作者 **Hu410**）。本 fork 的全部基础能力来自上游。
- **免责声明**：仅供个人自托管研究与学习使用。请遵守豆包/字节跳动的服务条款与所在地法律法规，
  不要用于批量账号、转卖 API、绕过付费等滥用场景。
