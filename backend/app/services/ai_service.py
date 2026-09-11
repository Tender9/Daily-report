import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.prompts.daily_report import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

REPORT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "important_notices": {"type": "array", "items": {"type": "string"}},
        "hot_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "heat": {"type": "string"},
                    "time_period": {"type": "string"},
                    "content_summary": {"type": "string"},
                    "comment": {"type": "string"},
                },
                "required": ["title", "time_period", "content_summary"],
            },
        },
        "tools_table_markdown": {"type": "string"},
        "insights": {"type": "array", "items": {"type": "string"}},
        "related_links": {"type": "array", "items": {"type": "string"}},
        "other_topics": {"type": "array", "items": {"type": "string"}},
        "funny_quotes": {"type": "array", "items": {"type": "string"}},
        "ending_quote": {"type": "string"},
    },
    "required": ["summary", "hot_topics", "funny_quotes", "ending_quote"],
}


class AIService:
    def __init__(self) -> None:
        self.model: Any = None
        self.is_loaded: bool = False
        self.load_error: Optional[str] = None
        if settings.AI_PROVIDER == "cloud":
            self.is_loaded = True
            logger.info(f"使用云端 API 引擎: {settings.CLOUD_API_URL} (模型: {settings.CLOUD_MODEL})")
        else:
            self._init_local_model()

    def _init_local_model(self) -> None:
        model_path = settings.MODEL_PATH
        if not model_path.exists():
            self.load_error = f"未找到本地 GGUF 模型文件: {model_path}"
            logger.warning(self.load_error)
            return

        try:
            from llama_cpp import Llama

            logger.info(
                f"正在加载本地 GGUF 模型: {model_path} (n_ctx={settings.N_CTX}, n_gpu_layers={settings.N_GPU_LAYERS})"
            )

            self.model = Llama(
                model_path=str(model_path), n_ctx=settings.N_CTX, n_gpu_layers=settings.N_GPU_LAYERS, verbose=False
            )
            self.is_loaded = True
            logger.info("本地 GGUF 模型加载完毕，就绪！")
        except Exception as e:
            self.load_error = f"加载 GGUF 引擎异常 ({type(e).__name__}): {e}"
            logger.error(self.load_error)

    def generate_report(self, text_content: str, report_date: str) -> Dict[str, Any]:
        """Generate structured daily report using either local GGUF model or Volcengine Ark Cloud API."""
        import time
        from app.services.parser_service import clean_and_sample_chat_log

        start_time = time.time()
        sampled_content = clean_and_sample_chat_log(text_content, max_chars=3800)

        res = None
        current_provider = settings.AI_PROVIDER

        if current_provider == "cloud":
            try:
                res = self._generate_report_cloud(sampled_content, report_date)
                res["ai_provider"] = "cloud"
                res["ai_model"] = settings.CLOUD_MODEL
            except Exception as cloud_err:
                logger.warning(f"云端 API 调用失败 ({cloud_err})，自动降级切换至本地 GGUF 模型处理...")
                if not self.is_loaded or self.model is None:
                    self._init_local_model()
                res = self._generate_report_local(sampled_content, report_date)
                res["ai_provider"] = "local"
                res["ai_model"] = "MiniCPM-V (本地降级)"
        else:
            if not self.is_loaded or self.model is None:
                self._init_local_model()
            res = self._generate_report_local(sampled_content, report_date)
            res["ai_provider"] = "local"
            res["ai_model"] = "MiniCPM-V (Local GGUF)"

        elapsed = round(time.time() - start_time, 2)
        res["elapsed_seconds"] = elapsed
        return res

    def _generate_report_cloud(self, text_content: str, report_date: str) -> Dict[str, Any]:
        user_prompt = USER_PROMPT_TEMPLATE.format(date=report_date, content=text_content[:3500])
        full_text = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

        headers = {"Authorization": f"Bearer {settings.CLOUD_API_KEY}", "Content-Type": "application/json"}

        import urllib.request

        url = settings.CLOUD_API_URL
        is_chat_endpoint = "/chat/completions" in url

        if is_chat_endpoint:
            payload = {
                "model": settings.CLOUD_MODEL,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
            }
        else:
            payload = {
                "model": settings.CLOUD_MODEL,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": full_text}]}],
            }

        try:
            logger.info(f"发送云端 API 请求 ({settings.CLOUD_MODEL}) -> {url}")
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_body = resp.read().decode("utf-8")
                raw_json = json.loads(resp_body)
                raw_text = self._extract_cloud_response_text(raw_json)
                return self._parse_json_response(raw_text, text_content, report_date)
        except Exception as primary_error:
            logger.warning(f"首选 API 接口请求失败 ({primary_error})，尝试备用接口模式...")

            if is_chat_endpoint:
                fallback_url = url.replace("/chat/completions", "/responses")
                fallback_payload = {
                    "model": settings.CLOUD_MODEL,
                    "input": [{"role": "user", "content": [{"type": "input_text", "text": full_text}]}],
                }
            else:
                fallback_url = url.replace("/responses", "/chat/completions")
                fallback_payload = {
                    "model": settings.CLOUD_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                }

            try:
                req_fallback = urllib.request.Request(
                    fallback_url, data=json.dumps(fallback_payload).encode("utf-8"), headers=headers, method="POST"
                )
                with urllib.request.urlopen(req_fallback, timeout=120) as resp:
                    resp_body = resp.read().decode("utf-8")
                    raw_json = json.loads(resp_body)
                    raw_text = self._extract_cloud_response_text(raw_json)
                    return self._parse_json_response(raw_text, text_content, report_date)
            except Exception as secondary_error:
                logger.error(f"云端 API 兼容请求亦失败: {secondary_error}")
                raise RuntimeError(f"云端 API 请求失败: {primary_error}")

    def _extract_cloud_response_text(self, raw_json: Dict[str, Any]) -> str:
        choices = raw_json.get("choices")
        if choices and isinstance(choices, list) and len(choices) > 0:
            msg = choices[0].get("message", {})
            content = msg.get("content")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                texts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
                if texts:
                    return "".join(texts)

        output = raw_json.get("output")
        if isinstance(output, list) and len(output) > 0:
            item = output[0]
            if isinstance(item, dict):
                choices = item.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    msg = choices[0].get("message", {})
                    content = msg.get("content")
                    if isinstance(content, str):
                        return content
                    elif isinstance(content, list):
                        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
                        if texts:
                            return "".join(texts)

        if isinstance(output, str):
            return output
        if isinstance(raw_json.get("text"), str):
            return raw_json["text"]

        return json.dumps(raw_json, ensure_ascii=False)

    def _generate_report_local(self, text_content: str, report_date: str) -> Dict[str, Any]:
        if not self.is_loaded or self.model is None:
            raise RuntimeError(f"本地 GGUF 模型未就绪: {self.load_error or '模型初始化中，请稍后'}")

        user_prompt = USER_PROMPT_TEMPLATE.format(date=report_date, content=text_content[:3500])

        try:
            from llama_cpp import LlamaGrammar

            grammar = LlamaGrammar.from_json_schema(json.dumps(REPORT_JSON_SCHEMA))

            response = self.model.create_chat_completion(
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
                max_tokens=None,
                temperature=0.2,
                grammar=grammar,
                stream=True,
            )
            chunks = []
            for chunk in response:
                delta = chunk["choices"][0].get("delta", {}).get("content", "")
                if delta:
                    chunks.append(delta)
            raw_result = "".join(chunks)
            return self._parse_json_response(raw_result, text_content, report_date)
        except Exception as e:
            logger.warning(f"Grammar 模式遇到异常，重发未受限请求: {e}")
            response = self.model.create_chat_completion(
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
                max_tokens=None,
                temperature=0.2,
                stream=True,
            )
            chunks = []
            for chunk in response:
                delta = chunk["choices"][0].get("delta", {}).get("content", "")
                if delta:
                    chunks.append(delta)
            raw_result = "".join(chunks)
            return self._parse_json_response(raw_result, text_content, report_date)

    def _parse_json_response(self, raw_text: str, text_content: str, report_date: str) -> Dict[str, Any]:
        clean_text = raw_text.strip()
        clean_text = re.sub(
            r"<(?:think|thought)>[\s\S]*?</(?:think|thought)>", "", clean_text, flags=re.IGNORECASE
        ).strip()

        code_block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", clean_text)
        if code_block_match:
            json_str = code_block_match.group(1).strip()
        else:
            first_brace = clean_text.find("{")
            last_brace = clean_text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = clean_text[first_brace : last_brace + 1].strip()
            else:
                json_str = clean_text

        parsed_data = None

        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                parsed_data = parsed
        except json.JSONDecodeError:
            pass

        if parsed_data is None:
            try:
                fixed_str = re.sub(r",\s*([\}\]])", r"\1", json_str)
                parsed = json.loads(fixed_str)
                if isinstance(parsed, dict):
                    parsed_data = parsed
            except json.JSONDecodeError:
                pass

        if parsed_data is not None:
            from app.services.parser_service import extract_chat_metadata

            meta = extract_chat_metadata(text_content)

            current_group_name = str(parsed_data.get("group_name", "")).strip()
            placeholder_names = {
                "AI 开发者与打工老哥交流群",
                "根据聊天记录提取的真实群名或实际主题归纳",
                "根据聊天提取的真实群名或主题归纳",
            }
            if not current_group_name or current_group_name in placeholder_names:
                parsed_data["group_name"] = meta["group_name"]


            if not parsed_data.get("member_count"):
                parsed_data["member_count"] = meta["member_count"]

            parsed_data.setdefault("summary", "今日群聊讨论积极，多位群友分享了各自的经验与见解。")
            parsed_data.setdefault("important_notices", [])
            parsed_data.setdefault("hot_topics", [])

            for topic in parsed_data.get("hot_topics", []):
                if isinstance(topic, dict):
                    if not topic.get("time_period"):
                        topic["time_period"] = "全天交流"
                    if not topic.get("heat"):
                        topic["heat"] = "⭐⭐⭐⭐⭐"
                    if not topic.get("comment"):
                        topic["comment"] = "群友热烈交流并达成共识"

            parsed_data.setdefault("funny_quotes", [])
            parsed_data.setdefault("tools_table_markdown", "")
            parsed_data.setdefault("insights", [])
            parsed_data.setdefault("related_links", [])
            parsed_data.setdefault("other_topics", [])
            parsed_data.setdefault("ending_quote", "🌙 沟通有据，落地有声！愿各位老哥工作顺利，晚安！")
            parsed_data["raw_llm_output"] = raw_text
            return parsed_data

        logger.error(f"JSON 解析失败. Raw output:\n{raw_text[:500]}")
        raise ValueError(f"大模型未输出合法的 JSON 结构: {raw_text[:200]}")

    def refine_section(
        self,
        section_key: str,
        current_section_data: Any,
        instruction: str,
        raw_text: str = "",
        history_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Refine a specific section of the report based on user feedback and instructions."""
        from app.prompts.refine_report import REFINE_SYSTEM_PROMPT, REFINE_USER_PROMPT_TEMPLATE

        section_names = {
            "summary": "氛围总结",
            "important_notices": "重要提醒/规则提炼",
            "hot_topics": "今日热门话题",
            "funny_quotes": "趣味互动",
            "tools_table_markdown": "工具及观点表格",
            "insights": "核心观点/避坑指南",
            "related_links": "相关链接/参考资源",
            "other_topics": "其他讨论话题",
            "ending_quote": "结语",
        }

        section_name = section_names.get(section_key, section_key)
        current_data_json = json.dumps(current_section_data, ensure_ascii=False, indent=2)
        raw_text_snippet = (raw_text[:2000] + "...") if len(raw_text) > 2000 else (raw_text or "无额外上下文")

        history_str_list = []
        if history_records:
            for idx, h in enumerate(history_records, 1):
                sec_name = h.get("section_name", h.get("section_key", "未知板块"))
                rating = f"{h.get('rating')}星" if h.get("rating") else "未评分"
                inst = h.get("instruction", "")
                time_str = h.get("timestamp", "")
                history_str_list.append(f"- [历史轮次 {idx} | {time_str}] 板块【{sec_name}】 (评分: {rating}): “{inst}”")

        history_context = "\n".join(history_str_list) if history_str_list else "无（本次为首次增量微调）"

        user_prompt = REFINE_USER_PROMPT_TEMPLATE.format(
            section_name=section_name,
            section_key=section_key,
            current_data_json=current_data_json,
            history_context=history_context,
            instruction=instruction,
            raw_text_snippet=raw_text_snippet,
        )

        full_prompt = f"{REFINE_SYSTEM_PROMPT}\n\n{user_prompt}"

        if settings.AI_PROVIDER == "cloud":
            try:
                headers = {"Authorization": f"Bearer {settings.CLOUD_API_KEY}", "Content-Type": "application/json"}
                url = settings.CLOUD_API_URL
                is_chat_endpoint = "/chat/completions" in url

                if is_chat_endpoint:
                    payload = {
                        "model": settings.CLOUD_MODEL,
                        "messages": [
                            {"role": "system", "content": REFINE_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                    }
                else:
                    payload = {
                        "model": settings.CLOUD_MODEL,
                        "input": [{"role": "user", "content": [{"type": "input_text", "text": full_prompt}]}],
                    }

                import urllib.request

                req = urllib.request.Request(
                    url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    resp_body = resp.read().decode("utf-8")
                    raw_json = json.loads(resp_body)
                    raw_text_resp = self._extract_cloud_response_text(raw_json)
                    return self._parse_refined_section(raw_text_resp, current_section_data)
            except Exception as e:
                logger.warning(f"云端 API 增量微调失败: {e}，备用逻辑模式...")

        if self.is_loaded and self.model is not None:
            try:
                response = self.model.create_chat_completion(
                    messages=[
                        {"role": "system", "content": REFINE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=1024,
                    temperature=0.3,
                )
                raw_text_resp = response["choices"][0]["message"]["content"]
                return self._parse_refined_section(raw_text_resp, current_section_data)
            except Exception as e:
                logger.error(f"本地 GGUF 增量微调失败: {e}")

        return current_section_data

    def _parse_refined_section(self, raw_text: str, default_fallback: Any) -> Any:
        clean_text = raw_text.strip()
        clean_text = re.sub(
            r"<(?:think|thought)>[\s\S]*?</(?:think|thought)>", "", clean_text, flags=re.IGNORECASE
        ).strip()

        code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text)
        if code_block_match:
            json_str = code_block_match.group(1).strip()
        else:
            first_char = (
                clean_text.find("[")
                if "[" in clean_text and (clean_text.find("[") < clean_text.find("{") or "{" not in clean_text)
                else clean_text.find("{")
            )
            last_char = (
                clean_text.rfind("]")
                if "]" in clean_text and clean_text.rfind("]") > clean_text.rfind("}")
                else clean_text.rfind("}")
            )
            if first_char != -1 and last_char != -1 and last_char > first_char:
                json_str = clean_text[first_char : last_char + 1].strip()
            else:
                json_str = clean_text

        parsed = None
        try:
            parsed = json.loads(json_str)
        except Exception:
            try:
                fixed_str = re.sub(r",\s*([\}\]])", r"\1", json_str)
                parsed = json.loads(fixed_str)
            except Exception:
                logger.warning(f"微调 JSON 解析失败，保留原结构: {raw_text[:200]}")
                return default_fallback

        # 解包针对性字典格式，例如对于字符串板块解包 {"summary": "..."}
        if isinstance(parsed, dict):
            if isinstance(default_fallback, str):
                for k in ["summary", "content", "text", "ending_quote", "result"]:
                    if k in parsed and isinstance(parsed[k], str):
                        return parsed[k]
            elif isinstance(default_fallback, list):
                for k in [
                    "items",
                    "list",
                    "notices",
                    "hot_topics",
                    "funny_quotes",
                    "insights",
                    "related_links",
                    "other_topics",
                ]:
                    if k in parsed and isinstance(parsed[k], list):
                        return parsed[k]

        return parsed


# Global singleton
ai_service = AIService()
