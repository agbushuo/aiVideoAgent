"""LLM 分析引擎

通过 llama.cpp (OpenAI 兼容 API) 分析视频字幕，提取亮点片段。
支持长上下文 (100k+) 和自动截断重试。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from src.transcribe.models import TranscriptResult

console = Console()


@dataclass
class Highlight:
    """亮点片段"""
    segment_id: int
    start: float
    end: float
    title: str
    reason: str
    score: float


@dataclass
class AnalysisReport:
    """分析报告"""
    summary: str
    highlights: list[Highlight] = field(default_factory=list)
    video_path: str = ""
    duration: float = 0.0
    language: str = ""
    model: str = ""
    analyzed_at: str = ""


class LLMAnalyzer:
    """LLM 分析引擎 (OpenAI 兼容 API)"""

    def __init__(
        self,
        provider: str = "llama_cpp",
        model: str = "Qwen3.6-27B-Q4_K_M.gguf",
        endpoint: str = "http://localhost:8080/v1",
        api_key: str = "",
        temperature: float = 0.3,
        max_tokens: int = 16384,
        timeout: int = 600,
        context_size: int = 131072,
    ):
        self.provider = provider
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.context_size = context_size
        self._system_prompt = self._load_prompt("system.md")
        self._highlight_prompt = self._load_prompt("highlight_extract.md")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / filename
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        if filename == "system.md":
            return self._default_system_prompt()
        elif filename == "highlight_extract.md":
            return self._default_highlight_prompt()
        return ""

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "你是一个专业的视频内容分析专家。你的任务是分析视频字幕文本，"
            "理解视频内容，识别出最有价值的片段，并解释为什么这些片段值得保留。"
            "输出必须是严格的 JSON 格式，不要包含任何其他文字。"
        )

    @staticmethod
    def _default_highlight_prompt() -> str:
        return (
            "基于以下视频字幕，请完成两个任务：\n\n"
            "1. 视频总结: 用 2-3 句话概括视频的核心内容\n"
            "2. 亮点提取: 选出 3-8 个最值得保留的精彩片段\n\n"
            "每个亮点必须包含 segment_id, start, end, title, reason, score。\n"
            "输出严格 JSON 格式。\n\n"
            "字幕内容:\n{transcript_text}"
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算 token 数量 (中文约 1.5 字/token, 英文约 4 字/token)"""
        chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.5)

    def _build_transcript_text(self, transcript: TranscriptResult) -> str:
        """构建字幕文本 — 每个片段带 segment_id 和时间戳，方便 LLM 映射"""
        lines = []
        for i, seg in enumerate(transcript.segments):
            lines.append(
                f"[{seg.start:.1f}s-{seg.end:.1f}s] #{i}: {seg.text}"
            )
        return "\n".join(lines)

    def _build_transcript_text_compact(
        self, transcript: TranscriptResult, max_segments: int
    ) -> str:
        """构建截断版字幕文本 — 保留头部和尾部，中间用省略号替代"""
        total = len(transcript.segments)
        if total <= max_segments:
            return self._build_transcript_text(transcript)

        half = max_segments // 2
        lines = []
        for i, seg in enumerate(transcript.segments[:half]):
            lines.append(
                f"[{seg.start:.1f}s-{seg.end:.1f}s] #{i}: {seg.text}"
            )
        skipped_start = transcript.segments[half].start
        skipped_end = transcript.segments[-half].end
        lines.append(
            f"[{skipped_start:.1f}s - {skipped_end:.1f}s] "
            f"#(省略了 {total - max_segments} 个片段...)"
        )
        for i, seg in enumerate(
            transcript.segments[-half:], start=total - half
        ):
            lines.append(
                f"[{seg.start:.1f}s-{seg.end:.1f}s] #{i}: {seg.text}"
            )
        return "\n".join(lines)

    @staticmethod
    def _strip_thinking_tags(text: str) -> str:
        """移除 LLM 响应中的 <thinking> 推理标签内容

        Qwen 等推理模型在 --reasoning on 模式下会输出:
        <thinking>...推理过程...</thinking>
        我们需要提取 thinking 标签之后的实际回答。
        """
        # 移除 <thinking>...</thinking> 块
        cleaned = re.sub(
            r'<thinking>.*?</thinking>',
            '',
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # 移除 <think>...</think> 块 (部分模型的变体)
        cleaned = re.sub(
            r'<think>.*?</think>',
            '',
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        return cleaned.strip()

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        url = f"{self.endpoint}/chat/completions"
        console.print(
            f"[dim]调用 LLM: {self.model} "
            f"(max_tokens={self.max_tokens})[/dim]"
        )

        # 估算输入 token 数
        input_text = "\n".join(m["content"] for m in messages)
        input_tokens = self._estimate_tokens(input_text)
        console.print(
            f"[dim]输入约 {input_tokens} tokens "
            f"(上下文限制 {self.context_size})[/dim]"
        )

        start = time.time()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()

            elapsed = time.time() - start
            content = data["choices"][0]["message"]["content"]

            # 移除 thinking 标签
            had_thinking = "<thinking>" in content or "<think>" in content
            content = self._strip_thinking_tags(content)

            output_tokens = self._estimate_tokens(content)
            console.print(
                f"[green]✓[/green] LLM 响应完成 "
                f"({elapsed:.1f}秒, 输出约 {output_tokens} tokens)"
            )
            if had_thinking:
                console.print(
                    "[dim]已移除 <thinking> 推理标签内容[/dim]"
                )

            # 调试: 打印响应前/后片段
            if len(content) > 400:
                console.print(f"[dim]响应开头: {content[:200]}[/dim]")
                console.print(
                    f"[dim]响应结尾: ...{content[-200:]}[/dim]"
                )
            else:
                console.print(f"[dim]完整响应: {content}[/dim]")

            return content.strip()

        except httpx.ConnectError:
            console.print(
                f"[red]✗[/red] 无法连接到 LLM 服务: {self.endpoint}"
            )
            console.print("[dim]请确保 llama.cpp 服务正在运行[/dim]")
            raise
        except httpx.HTTPStatusError as e:
            console.print(
                f"[red]✗[/red] LLM API 错误: {e.response.status_code}"
            )
            console.print(f"[dim]响应: {e.response.text[:500]}[/dim]")
            raise
        except httpx.TimeoutException:
            elapsed = time.time() - start
            console.print(
                f"[red]✗[/red] LLM 请求超时 "
                f"({elapsed:.1f}秒 > {self.timeout}秒)"
            )
            console.print(
                "[dim]长视频分析可能需要更长时间，"
                "建议增加 timeout 配置[/dim]"
            )
            raise
        except KeyError as e:
            console.print(f"[red]✗[/red] LLM 响应格式异常: {e}")
            console.print(f"[dim]原始响应: {data}[/dim]")
            raise

    def _repair_json(self, text: str) -> str:
        """修复 LLM 返回的常见 JSON 格式错误"""
        text = text.replace("“", "\"").replace("”", "\"")
        text = text.replace("‘", "'").replace("’", "'")

        result = []
        in_string = False
        escaped = False

        for char in text:
            if escaped:
                result.append(char)
                escaped = False
                continue

            if char == "\\" and in_string:
                result.append(char)
                escaped = True
                continue

            if char == '"':
                in_string = not in_string
                result.append(char)
                continue

            if char == "\n" and in_string:
                result.append(" ")
                continue

            result.append(char)

        text = "".join(result)

        # 修复对象属性之间缺失的逗号
        text = re.sub(r'("|\d|}|\])\s*(")', r'\1, \2', text)
        # 修复数组中对象之间缺失的逗号
        text = re.sub(r'\}\s*\{', '}, {', text)
        # 移除尾部逗号
        text = re.sub(r',\s*([}\]])', r'\1', text)

        return text

    def _check_response_truncated(self, text: str) -> bool:
        """检查响应是否被截断 (未闭合的 JSON)"""
        open_braces = text.count("{")
        close_braces = text.count("}")
        open_brackets = text.count("[")
        close_brackets = text.count("]")

        if text.strip().startswith("{") and open_braces > close_braces:
            return True
        if "[" in text and open_brackets > close_brackets:
            return True
        return False

    def _extract_fallback(self, text: str) -> dict[str, Any]:
        """JSON 解析彻底失败时的正则兜底提取"""
        result: dict[str, Any] = {"summary": "", "highlights": []}

        summary_match = re.search(
            r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL
        )
        if summary_match:
            result["summary"] = summary_match.group(1).replace(
                "\\n", "\n"
            ).strip()

        highlight_pattern = re.compile(
            r'"?\s*segment_id\s*"?[:\s]+\s*(\d+)'
            r'[^}]*?"?\s*start\s*"?[:\s]+\s*([\d.]+)'
            r'[^}]*?"?\s*end\s*"?[:\s]+\s*([\d.]+)'
            r'[^}]*?"?\s*title\s*"?[:\s]+"\s*([^"]*)'
            r'[^}]*?"?\s*reason\s*"?[:\s]+"\s*([^"]*)'
            r'[^}]*?"?\s*score\s*"?[:\s]+\s*([\d.]+)',
            re.DOTALL,
        )
        for m in highlight_pattern.finditer(text):
            result["highlights"].append({
                "segment_id": int(m.group(1)),
                "start": float(m.group(2)),
                "end": float(m.group(3)),
                "title": m.group(4).strip(),
                "reason": m.group(5).strip(),
                "score": float(m.group(6)),
            })

        return result

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """解析 LLM 响应为 JSON（多级容错）"""
        cleaned = response.strip()

        # 移除 markdown 代码块标记
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [
                l for l in lines
                if not l.strip().startswith("```")
            ]
            cleaned = "\n".join(lines)

        # 检查是否被截断，尝试修复
        if self._check_response_truncated(cleaned):
            console.print(
                "[yellow]! LLM 响应可能被截断，尝试修复...[/yellow]"
            )
            open_b = cleaned.count("{") - cleaned.count("}")
            close_b = cleaned.count("[") - cleaned.count("]")
            if open_b > 0:
                cleaned = cleaned + (
                    "}" * open_b + "]" * max(0, close_b)
                )
            elif close_b > 0:
                cleaned = cleaned + (
                    "]" * close_b + "}" * max(0, open_b)
                )

        # 1. 尝试直接解析
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 2. 提取 JSON 对象范围（找第一个 { 和最后一个 }）
        start_brace = cleaned.find("{")
        end_brace = cleaned.rfind("}")
        if start_brace >= 0 and end_brace > start_brace:
            cleaned = cleaned[start_brace:end_brace + 1]

        # 3. 修复常见格式错误后重试
        try:
            fixed = self._repair_json(cleaned)
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            console.print(
                f"[yellow]! JSON 修复后解析仍失败: {e.msg}[/yellow]"
            )

        # 4. 正则兜底提取
        console.print("[yellow]! 启用正则兜底提取...[/yellow]")
        data = self._extract_fallback(cleaned)
        console.print(
            f"[dim]兜底提取到 {len(data.get('highlights', []))} 个亮点, "
            f"summary 长度: {len(data.get('summary', ''))}[/dim]"
        )
        return data

    def analyze(self, transcript: TranscriptResult) -> AnalysisReport:
        """分析字幕，生成报告

        流程:
        1. 估算字幕文本大小
        2. 如果超过上下文窗口，自动截断
        3. 调用 LLM 分析
        4. 解析响应，提取 highlights
        5. 验证结果不为空
        """
        # Step 1: 构建完整字幕文本
        transcript_text = self._build_transcript_text(transcript)
        text_tokens = self._estimate_tokens(transcript_text)

        console.print(
            f"[dim]字幕共 {len(transcript.segments)} 个片段, "
            f"约 {text_tokens} tokens[/dim]"
        )

        # Step 2: 检查是否需要截断
        # 预留 max_tokens 给 LLM 输出，system prompt 约 200 tokens
        available_for_input = self.context_size - self.max_tokens - 200

        if text_tokens > available_for_input:
            console.print(
                f"[yellow]! 字幕文本 ({text_tokens} tokens) "
                f"超过可用上下文 ({available_for_input} tokens)，"
                f"将截断处理[/yellow]"
            )
            max_segments = int(
                available_for_input
                / (text_tokens / len(transcript.segments))
            )
            max_segments = max(max_segments, 50)
            console.print(
                f"[dim]保留最多 {max_segments} 个片段 "
                f"(头部 + 尾部)[/dim]"
            )
            transcript_text = self._build_transcript_text_compact(
                transcript, max_segments
            )

        # Step 3: 构建 prompt 并调用 LLM
        prompt = self._highlight_prompt.format(
            transcript_text=transcript_text
        )

        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = self._call_llm(messages)
        data = self._parse_llm_response(response)

        # Step 4: 提取 highlights
        highlights = []
        for h in data.get("highlights", []):
            seg_id = h.get("segment_id", 0)
            start = h.get("start", 0.0)
            end = h.get("end", 0.0)

            # 验证 segment_id 是否在有效范围内
            if transcript.segments and seg_id >= len(
                transcript.segments
            ):
                console.print(
                    f"[yellow]! 亮点 segment_id={seg_id} 超出范围 "
                    f"(0-{len(transcript.segments) - 1})，跳过[/yellow]"
                )
                continue

            if transcript.segments:
                max_time = transcript.segments[-1].end
                start = min(start, max_time)
                end = min(end, max_time)

            highlights.append(
                Highlight(
                    segment_id=seg_id,
                    start=start,
                    end=end,
                    title=h.get("title", ""),
                    reason=h.get("reason", ""),
                    score=float(h.get("score", 0.5)),
                )
            )

        highlights.sort(key=lambda x: x.score, reverse=True)

        summary = data.get("summary", "")

        # Step 5: 验证结果
        if not summary and not highlights:
            console.print("[red]✗ LLM 分析结果为空！可能的原因:[/red]")
            console.print(
                "[dim]  1. LLM 响应被截断 (增加 max_tokens)[/dim]"
            )
            console.print(
                "[dim]  2. LLM 返回了非 JSON 内容 "
                "(检查 reasoning/thinking 标签)[/dim]"
            )
            console.print("[dim]  3. LLM 服务未正常运行[/dim]")
        else:
            console.print(
                f"[green]✓[/green] 提取到 {len(highlights)} 个亮点, "
                f"summary {len(summary)} 字"
            )

        from datetime import datetime

        return AnalysisReport(
            summary=summary,
            highlights=highlights,
            language=transcript.language,
            duration=transcript.duration,
            model=self.model,
            analyzed_at=datetime.now().isoformat(),
        )
