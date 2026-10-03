"""Gọi AI để viết bài - hai cách, chọn trong config.yaml -> ai.backend:

- claude_code: dùng Claude Code CLI đăng nhập bằng gói Pro/Max (CLAUDE_CODE_OAUTH_TOKEN trên GitHub,
               hoặc `claude` đã đăng nhập trên máy). Không tốn thêm phí.
- api:         dùng Anthropic API (ANTHROPIC_API_KEY), tính phí theo lượng dùng.

Cả hai đều trả về dict JSON theo schema truyền vào.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

from src.config import CONFIG, env


class LLMError(RuntimeError):
    pass


def available() -> bool:
    if CONFIG["ai"]["backend"] == "api":
        return bool(env("ANTHROPIC_API_KEY"))
    return shutil.which("claude") is not None


def generate_json(system: str, user: str, schema: dict, web: bool = False) -> dict:
    """web=True: cho AI tự tìm tin tức trên mạng (WebSearch/WebFetch) trước khi viết."""
    if CONFIG["ai"]["backend"] == "api":
        return _via_api(system, user, schema, web)
    return _via_claude_code(system, user, schema, web)


# ------------------------------------------------------------------ Claude Code

# Bài viết chỉ cần suy nghĩ + trả chữ: tắt hết công cụ để AI không đọc/ghi file hay lên mạng.
_BLOCKED_TOOLS = "Bash Edit Write Read Glob Grep WebFetch WebSearch NotebookEdit Task TodoWrite"


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise LLMError(f"AI không trả về JSON: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def _via_claude_code(system: str, user: str, schema: dict, web: bool = False) -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise LLMError("Chưa cài Claude Code CLI (npm install -g @anthropic-ai/claude-code)")

    # Đưa toàn bộ hướng dẫn vào nội dung yêu cầu (một số phiên bản CLI bỏ qua --system-prompt).
    prompt = (
        f"<huong_dan>\n{system}\n</huong_dan>\n\n{user}\n\n"
        f"YÊU CẦU ĐẦU RA: chỉ trả về đúng MỘT object JSON hợp lệ theo JSON Schema dưới đây. "
        f"Không thêm lời dẫn, không bọc trong ```, không dùng markdown trong nội dung.\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    blocked = _BLOCKED_TOOLS.split()
    cmd = [exe, "-p", "--output-format", "json", "--model", CONFIG["ai"]["claude_code_model"]]
    if web:
        blocked = [t for t in blocked if t not in ("WebFetch", "WebSearch")]
        cmd += ["--allowedTools", "WebSearch", "WebFetch"]
    cmd += ["--disallowed-tools", *blocked]
    # Chạy trong thư mục trống để Claude Code không nạp CLAUDE.md / file của project.
    with tempfile.TemporaryDirectory() as cwd:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                              cwd=cwd, timeout=900, env={**os.environ})
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise LLMError(f"Claude Code lỗi: {(proc.stderr or proc.stdout)[:300]}")
    if out.get("is_error"):
        raise LLMError(f"Claude Code lỗi: {out.get('result', '')[:300]}")
    return _extract_json(out["result"])


# ------------------------------------------------------------------ API

def _via_api(system: str, user: str, schema: dict, web: bool = False) -> dict:
    import anthropic

    try:
        response = anthropic.Anthropic().beta.messages.create(
            model=CONFIG["ai"]["model"],
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": CONFIG["ai"]["effort"],
                           "format": {"type": "json_schema", "schema": schema}},
            system=system,
            messages=[{"role": "user", "content": user}],
            **({"tools": [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]} if web else {}),
        )
    except anthropic.APIError as exc:
        raise LLMError(f"API lỗi: {exc}") from exc
    if response.stop_reason == "refusal":
        raise LLMError("Model từ chối viết bài này")
    if response.stop_reason == "max_tokens":
        raise LLMError("Bài bị cắt do vượt max_tokens")
    return json.loads([b.text for b in response.content if b.type == "text"][-1])


# ------------------------------------------------------------------ xem ảnh (duyệt video trước khi đăng)

def review_image(system: str, image, user: str, schema: dict) -> dict:
    """Cho AI xem 1 ảnh (vd. ảnh ghép các khung hình video) rồi trả JSON theo schema."""
    from pathlib import Path
    image = Path(image)
    if CONFIG["ai"]["backend"] == "api":
        import anthropic
        import base64
        data = base64.b64encode(image.read_bytes()).decode()
        r = anthropic.Anthropic().messages.create(
            model=CONFIG["ai"]["model"], max_tokens=4000, system=system,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
                {"type": "text", "text": user}]}])
        return json.loads([b.text for b in r.content if b.type == "text"][-1])
    exe = shutil.which("claude")
    if not exe:
        raise LLMError("Chưa cài Claude Code CLI")
    with tempfile.TemporaryDirectory() as cwd:
        shutil.copy(image, Path(cwd) / "frames.jpg")
        prompt = (f"<huong_dan>\n{system}\n</huong_dan>\n\nDùng công cụ Read mở file ảnh frames.jpg trong thư mục hiện tại "
                  f"và xem kỹ.\n{user}\n\nYÊU CẦU ĐẦU RA: chỉ trả về đúng MỘT object JSON hợp lệ theo JSON Schema:\n"
                  f"{json.dumps(schema, ensure_ascii=False)}")
        blocked = [t for t in _BLOCKED_TOOLS.split() if t != "Read"]
        cmd = [exe, "-p", "--output-format", "json", "--model", CONFIG["ai"]["claude_code_model"],
               "--allowedTools", "Read", "--disallowed-tools", *blocked]
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                              cwd=cwd, timeout=600, env={**os.environ})
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise LLMError(f"Claude Code lỗi: {(proc.stderr or proc.stdout)[:300]}")
    if out.get("is_error"):
        raise LLMError(f"Claude Code lỗi: {out.get('result', '')[:300]}")
    return _extract_json(out["result"])
