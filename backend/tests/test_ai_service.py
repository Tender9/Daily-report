import pytest
from app.services.ai_service import ai_service


def test_parse_json_pure():
    raw = '{"summary": "测试摘要", "hot_topics": []}'
    result = ai_service._parse_json_response(raw, "", "2026-09-08")
    assert result["summary"] == "测试摘要"
    assert result["raw_llm_output"] == raw


def test_parse_json_group_name_placeholder_fallback():
    raw = '{"group_name": "根据聊天记录提取的真实群名或实际主题归纳", "summary": "测试摘要", "hot_topics": []}'
    result = ai_service._parse_json_response(raw, "2026年9月9日前端框架讨论小组聊天记录", "2026-09-08")
    assert result["group_name"] == "前端框架讨论小组"


def test_parse_json_group_name_custom():
    raw = '{"group_name": "户外徒步爱好者交流群", "summary": "测试摘要", "hot_topics": []}'
    result = ai_service._parse_json_response(raw, "", "2026-09-08")
    assert result["group_name"] == "户外徒步爱好者交流群"



def test_parse_json_with_code_block():
    raw = """```json
{
  "summary": "代码块摘要",
  "hot_topics": []
}
```"""
    result = ai_service._parse_json_response(raw, "", "2026-09-08")
    assert result["summary"] == "代码块摘要"


def test_parse_json_with_preamble_reasoning():
    raw = """好的，用户让我根据群聊记录整理《群聊日报》，要按指定结构来。首先得看用户给的例子。
首先看聊天记录，时间是从早上到晚上...

```json
{
  "summary": "带前言推理的摘要",
  "hot_topics": []
}
```"""
    result = ai_service._parse_json_response(raw, "", "2026-09-08")
    assert result["summary"] == "带前言推理的摘要"


def test_parse_json_with_think_tags():
    raw = """<think>
分析聊天记录：阿强说了元气满满，老李说项目上线。
</think>
{
  "summary": "Think标签摘要",
  "hot_topics": []
}"""
    result = ai_service._parse_json_response(raw, "", "2026-09-08")
    assert result["summary"] == "Think标签摘要"


def test_parse_json_with_trailing_comma():
    raw = """{
  "summary": "尾随逗号测试",
  "hot_topics": [],
}"""
    result = ai_service._parse_json_response(raw, "", "2026-09-08")
    assert result["summary"] == "尾随逗号测试"


def test_parse_json_invalid():
    raw = "这是完全无法解析的文本..."
    with pytest.raises(ValueError, match="大模型未输出合法的 JSON 结构"):
        ai_service._parse_json_response(raw, "", "2026-09-08")


def test_extract_cloud_response_text():
    volcengine_resp = {
        "output": [
            {
                "choices": [
                    {
                        "message": {
                            "content": [{"type": "output_text", "text": '{"summary": "云端测试", "hot_topics": []}'}]
                        }
                    }
                ]
            }
        ]
    }
    extracted = ai_service._extract_cloud_response_text(volcengine_resp)
    assert extracted == '{"summary": "云端测试", "hot_topics": []}'
