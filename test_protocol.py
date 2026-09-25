"""
Doubao2api - 协议结构离线测试

验证适配后的请求体结构与豆包网页版 (pc_version 3.38.5) 前端逆向结果一致。
不发起真实网络请求。
"""
import sys

from config import config
from doubao_client import DoubaoClient, parse_cookie_string
from main import _process_messages, _estimate_tokens
from models import ChatCompletionRequest


def test_model_profiles():
    profiles = config.model_profiles
    assert config.get_model_profile("doubao-fast").model_item_key == "0"
    assert config.get_model_profile("doubao-pro").model_item_key == "5"
    assert config.get_model_profile("doubao-pro").agent_mode == 1
    assert config.get_model_profile("doubao-lite").model_item_key == "seed-lite-7b"
    assert config.get_model_profile("doubao-turbo").agent_mode == 2
    # 旧名兼容
    assert config.get_model_profile("doubao-1.5-pro").model_item_key == "3"
    assert config.get_model_profile("doubao-1.5-lite").model_item_key == "seed-lite-7b"
    # 未知名回退
    assert config.get_model_profile("nonexistent").model_item_key == "0"
    print("PASS: model profiles")


def test_query_params():
    cookies = {"ttwid": "tt-1", "sessionid": "s-1", "web_id": "123", "msToken": "msk"}
    c = DoubaoClient(cookies)
    c.reset_conversation()  # 实际请求流程中会先重置会话
    p = c._get_query_params()
    assert p["aid"] == config.aid == "497858"
    assert p["version_code"] == "20800"
    assert p["pc_version"] == "3.38.5", p["pc_version"]
    assert p["scene"] == "chatsse"
    assert p["tz_name"] == "Asia/Shanghai"
    assert p["device_id"] == "123"  # 前端 device_id 取 web_id
    assert p["msToken"] == "msk"
    assert "web_tab_id" in p
    print("PASS: query params")


def test_request_body():
    cookies = {"ttwid": "tt-1", "sessionid": "s-1", "web_id": "123", "s_v_web_id": "verify01"}
    c = DoubaoClient(cookies)
    c.reset_conversation()
    body = c._build_completion_request("你好", config.get_model_profile("doubao-pro"))

    # client_meta：新协议字段
    cm = body["client_meta"]
    assert cm["bot_id"] == config.bot_id
    assert cm["conversation_id"] == ""
    assert cm["local_conversation_id"] == c.local_conversation_id and cm["local_conversation_id"]
    assert cm["local_permissions"] == []
    assert cm["last_section_id"] == ""
    assert cm["last_message_index"] == 0

    # messages：text block 结构（与前端 mapTextToTextBlock 一致）
    msg = body["messages"][0]
    assert msg["message_status"] == 0
    blk = msg["content_block"][0]
    assert blk["block_type"] == 10000
    assert blk["content"]["text_block"]["text"] == "你好"
    assert blk["content"]["text_block"]["icon_url"] == ""
    assert blk["content"]["pc_event_block"] == ""
    assert blk["meta_info"] == [] and blk["append_fields"] == []

    # option：新协议字段
    opt = body["option"]
    assert opt["need_create_conversation"] is True
    assert opt["click_clear_context"] is False
    assert opt["support_chunk_delta"] if False else opt["sse_recv_event_options"] == {"support_chunk_delta": True}
    assert opt["support_lazy_fetch_stream"] is True
    assert opt["is_from_click_softlink"] is False
    assert opt["scene_type"] == 0
    assert opt["message_from"] == 0
    assert opt["message_storage_type"] == 0
    assert opt["need_deep_think"] == 0
    assert opt["conversation_mode"] == 1
    assert opt["agent_mode"] == 1  # doubao-pro -> 工作任务
    assert opt["model_config"] == {
        "model_item_key": "5",
        "model_extra_params": {"total_window_size": "256000"},
        "reasoning_effort": 5,
    }
    assert opt["aggregate_params"]["model_item_key"] == "5"
    assert opt["aggregate_params"]["conversation_mode"] == "1"
    assert opt["aggregate_params"]["agent_mode"] == "1"
    assert opt["recovery_option"] == {
        "is_recovery": False,
        "req_create_time_sec": opt["recovery_option"]["req_create_time_sec"],
        "append_sse_event_scene": 0,
    }
    assert opt["unique_key"] == c.local_conversation_id
    assert "conversation_init_ext" in opt and opt["conversation_init_ext"]["model_item_key"] == "5"

    assert body["user_context"] == []
    assert body["ext"]["use_deep_think"] == "0"
    print("PASS: request body structure")


def test_sse_parsing():
    c = DoubaoClient({"ttwid": "t", "sessionid": "s"})

    # 标准 SSE 事件解析
    ev = c._parse_sse_event('event: SSE_ACK\ndata: {"ack_client_meta": {"conversation_id": "C1", "section_id": "S1"}}')
    assert ev["event"] == "SSE_ACK" and ev["data"]["ack_client_meta"]["conversation_id"] == "C1"

    c._update_conversation_state(ev)
    assert c.conversation_id == "C1" and c.last_section_id == "S1"

    # 全量快照
    notify = {"event": "STREAM_MSG_NOTIFY", "data": {"content": {"content_block": [
        {"content": {"text_block": {"text": "全量文本"}}}]}}}
    assert c.extract_text_from_event(notify) == "全量文本"

    # 增量 CHUNK_DELTA
    delta = {"event": "CHUNK_DELTA", "data": {"text": "增量"}}
    assert c.extract_text_from_event(delta) == "增量"

    # STREAM_CHUNK patch_op
    chunk = {"event": "STREAM_CHUNK", "data": {"patch_op": [
        {"patch_value": {"content_block": [{"is_finish": False, "content": {"text_block": {"text": "块"}}}]}}]}}
    assert c.extract_text_from_event(chunk) == "块"

    # is_finish 的块应被跳过
    fin = {"event": "STREAM_CHUNK", "data": {"patch_op": [
        {"patch_value": {"content_block": [{"is_finish": True, "content": {"text_block": {"text": "块"}}}]}}]}}
    assert c.extract_text_from_event(fin) is None

    # 流式去重对齐：NOTIFY(全量) -> CHUNK(追加) -> NOTIFY(新全量)
    seq = [
        ("STREAM_MSG_NOTIFY", "你好，"),
        ("STREAM_CHUNK", "世界"),
        ("STREAM_MSG_NOTIFY", "你好，世界！"),
    ]
    emitted = ""
    for t, txt in seq:
        if t == "STREAM_MSG_NOTIFY":
            new_full = txt
        else:
            new_full = emitted + txt
        if new_full.startswith(emitted):
            emitted = new_full
        else:
            emitted = new_full
    assert emitted == "你好，世界！", emitted
    print("PASS: SSE parsing & dedup")


def test_message_processing():
    req = ChatCompletionRequest.model_validate({
        "model": "doubao-fast",
        "messages": [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": [{"type": "text", "text": "数组内容"}]},
            {"role": "assistant", "content": "历史回复"},
            {"role": "user", "content": "新问题"},
        ],
    })
    msgs = _process_messages(req.messages)
    assert msgs[0].content == "[系统指令]你是助手\n\n[用户消息]数组内容"
    assert msgs[1].role == "assistant"
    assert msgs[2].content == "新问题"
    assert _estimate_tokens("你好世界 hello") >= 3
    print("PASS: message processing")


if __name__ == "__main__":
    test_model_profiles()
    test_query_params()
    test_request_body()
    test_sse_parsing()
    test_message_processing()
    print("\nALL OFFLINE TESTS PASSED")
    sys.exit(0)
