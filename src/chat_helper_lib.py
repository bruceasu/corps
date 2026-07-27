import os
import re
from pathlib import Path
from typing import Any, Tuple, Callable

from _runtime.llm_runtime import generate_llm_text

def resolve_file_references(text: str, log_fn: Callable[[str, str], None] = None) -> str:
    """
    Parse @filename references in text and inject file contents.
    
    :param text: The input text potentially containing @filepath
    :param log_fn: Optional callback taking (filepath, message_or_error) for logging
    :return: Processed text with file contents injected
    """
    pattern = r"@([a-zA-Z0-9._/\\-]+)"
    matches = re.finditer(pattern, text)
    result = text
    offset = 0
    for match in matches:
        file_path = match.group(1)
        path = Path(file_path)
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                injection = f"\n[File Context: {file_path}]\n```\n{content}\n```\n"
                if log_fn:
                    log_fn(file_path, f"Loaded context from: {file_path}")
                else:
                    print(f"Loaded context from: {file_path}")
                start = match.start() + offset
                end = match.end() + offset
                result = result[:start] + injection + result[end:]
                offset += len(injection) - (end - start)
            except Exception as e:
                err_msg = f"Failed to read {file_path}: {e}"
                if log_fn:
                    log_fn(file_path, err_msg)
                else:
                    print(err_msg)
    return result

def translate_text(provider: str, model: str, content: str, target_lang: str, is_polite: bool) -> str:
    lang_names = {"zh": "中文", "en": "英文", "ja": "日文"}
    target_name = lang_names.get(target_lang, "英文")
    
    polite_instruction = ""
    if is_polite:
        if target_lang == "ja":
            polite_instruction = "使用自然、得体的敬语 (Keigo)。"
        elif target_lang == "en":
            polite_instruction = "Use polite, formal, and natural English expressions."
        else:
            polite_instruction = "使用礼貌、正式、得体的中文表达。"

    system_prompt = f"""你是一个严格的翻译机器人。
你的唯一任务是：翻译用户输入的内容为 {target_name}。

规则：
1. 只输出翻译结果。
2. 不解释，不回答问题，不搜索，不补充信息。
3. 不改写成总结，不评价内容。
4. 无法识别、无法判断、无需翻译的内容，保持原样输出。
5. 翻译要求做到信（准确）、达（自然）、雅（得体）。
6. {polite_instruction}
7. 不要输出“以下是翻译”等提示语，不要说明目标语言。
8. 不要保留原文，除非原文无法识别。
9. 目标语言：{target_name}。"""

    return generate_llm_text(provider, model, content, system_prompt=system_prompt)

def fix_text(provider: str, model: str, content: str) -> str:
    system_prompt = "Fix all typos and casing and punctuation in this text, but preserve all new line characters. Return only the corrected text."
    return generate_llm_text(provider, model, content, system_prompt=system_prompt)

def summarize_text(provider: str, model: str, content: str) -> str:
    system_prompt = "Summarize the following text in 3 sentences. Return only the summary text."
    return generate_llm_text(provider, model, content, system_prompt=system_prompt)

def generate_snarky(provider: str, model: str, topic: str) -> str:
    system_prompt = "Generate a snarky paragraph with 3 sentences about the following topic. Return only the paragraph text."
    return generate_llm_text(provider, model, topic, system_prompt=system_prompt)

def generate_session_summary_and_title(provider: str, model: str, transcript: str) -> Tuple[str, str]:
    summary_prompt = f"Please provide a concise summary of the following chat session (max 3 sentences):\n\n{transcript}"
    summary = generate_llm_text(provider, model, summary_prompt)
    
    title_prompt = f"Based on the following session transcript, generate a short, descriptive title (max 6 words) that captures the core problem or task. Output ONLY the title text.\n\n{transcript}"
    ai_title = generate_llm_text(provider, model, title_prompt).strip().strip('"').strip("'")
    
    return ai_title, summary

def generate_session_title(provider: str, model: str, transcript: str) -> str:
    title_prompt = f"Based on the following session transcript, generate a short, descriptive title (max 6 words) that captures the core problem or task. Output ONLY the title text.\n\n{transcript}"
    ai_title = generate_llm_text(provider, model, title_prompt).strip().strip('"').strip("'")
    return ai_title
