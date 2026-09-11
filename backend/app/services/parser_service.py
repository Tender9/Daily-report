import io
from pathlib import Path


def parse_file_content(filename: str, content: bytes) -> str:
    """Extract plain text from uploaded bytes based on file format."""
    suffix = Path(filename).suffix.lower().lstrip(".")

    if suffix in ("txt", "log", "md"):
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("gbk", errors="ignore")

    elif suffix == "pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages_text)
        except Exception as e:
            return f"[PDF 解析限制]: {str(e)}\n\n" + content.decode("utf-8", errors="ignore")

    elif suffix in ("html", "htm"):
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(content, "html.parser")
            return soup.get_text(separator="\n")
        except Exception:
            return content.decode("utf-8", errors="ignore")

    elif suffix == "docx":
        try:
            from docx import Document

            doc = Document(io.BytesIO(content))
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            return f"[DOCX 解析提示]: {str(e)}"

    elif suffix == "doc":
        # Raw text fallback for legacy doc files
        return content.decode("utf-8", errors="ignore")

    return content.decode("utf-8", errors="ignore")


def clean_and_sample_chat_log(text: str, max_chars: int = 3800) -> str:
    """Pre-filter system noise and sample large chat logs evenly to guarantee fixed LLM processing speed."""
    lines = text.splitlines()
    filtered_lines = []

    # System noise keywords to filter out
    noise_keywords = [
        "撤回了一条消息",
        "加入了群聊",
        "移出了群聊",
        "拍了拍",
        "戳了一戳",
        "签到成功",
        "[表情]",
        "[图片]",
    ]

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        if any(k in line_str for k in noise_keywords):
            continue
        # Skip trivial single-word noise lines like "ok", "1", "对"
        if len(line_str) <= 3 and not (":" in line_str or "：" in line_str):
            continue
        filtered_lines.append(line_str)

    cleaned_text = "\n".join(filtered_lines)

    if len(cleaned_text) <= max_chars:
        return cleaned_text

    # If chat log is huge (e.g. 5,000 messages), sample head, middle, and tail evenly
    part_len = max_chars // 3
    head = cleaned_text[:part_len]
    mid_start = len(cleaned_text) // 2 - (part_len // 2)
    mid = cleaned_text[mid_start : mid_start + part_len]
    tail = cleaned_text[-part_len:]

    return f"{head}\n\n... (中途讨论记录精简) ...\n\n{mid}\n\n... (晚间讨论记录精简) ...\n\n{tail}"


def extract_chat_metadata(text: str) -> dict:
    group_name = ""
    import re

    # Pattern 1: 2026年9月9日Astra-GPT6-开发讨论小组聊天记录如下：
    m1 = re.search(r"\d{4}年\d{1,2}月\d{1,2}日\s*([^\n\(\（]+?)\s*聊天记录", text)
    if m1:
        group_name = m1.group(1).strip()

    # Pattern 2: （Astra-GPT6-开发讨论小组） or (Astra-GPT6-开发讨论小组)
    if not group_name:
        m2 = re.search(r"[（\(]([^\n）\)]+?)[）\)]", text)
        if m2:
            candidate = m2.group(1).strip()
            if len(candidate) >= 2 and not "202" in candidate:
                group_name = candidate

    # Pattern 3: 群聊名称：xxx or 群名：xxx
    if not group_name:
        m3 = re.search(r"群(?:聊)?(?:名称|名)[:：]\s*([^\n\(\（]+)", text)
        if m3:
            group_name = m3.group(1).strip()

    if not group_name:
        group_name = "微信交流群"

    # Count unique senders across different timestamp formats
    senders = set(re.findall(r"(?:\[\d{2}:\d{2}(?::\d{2})?\]|\d{2}:\d{2}(?::\d{2})?)\s*([^:\n\s\d]+)[:：]", text))
    count = len(senders) if senders else 8

    return {"group_name": group_name, "member_count": count}
