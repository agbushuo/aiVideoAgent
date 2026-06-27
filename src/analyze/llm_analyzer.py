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
        self._scene_prompt = self._load_prompt("scene_analysis.md")
        self._final_review_prompt = self._load_prompt("final_review.md")

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
    def _default_scene_prompt() -> str:
        return (
            "对以下视频场景进行标注。每个场景输出 scene_type, tags, multi_score, summary。\n"
            "multi_score 包含 hook, emotion, comedy, action, information, suspense, climax, viral（0-10 分）。\n"
            "输出严格 JSON 数组格式。\n\n"
            "场景列表:\n{scenes_text}"
        )

    @staticmethod
    def _default_final_review_prompt() -> str:
        return (
            "从以下候选片段中精选最适合的片段并排序。\n"
            "输出 JSON 格式: {\"selected\": [{\"scene_id\": N, \"role\": \"...\", \"reason\": \"...\"}], "
            "\"rejected\": [...], \"overall_comment\": \"...\"}\n\n"
            "候选片段:\n{candidates_text}\n\n"
            "用户指令: {user_prompt}\n"
            "选出 {num_to_select} 个片段，目标平台: {platform}，目标时长: {target_duration} 秒"
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

    # ================================================================= #
    # Scene 标注（Smart Clip Engine v2.0）
    # ================================================================= #

    def _build_scenes_text(
        self, scenes: list  # list[Scene]
        ) -> str:
        """构建场景文本 — 用于 LLM 标注

        每个场景包含编号、时间范围、文本内容。
        """
        lines = []
        for s in scenes:
            lines.append(
                f"--- 场景 #{s.scene_id} "
                f"[{s.start:.1f}s - {s.end:.1f}s] "
                f"({s.duration:.1f}s) ---"
            )
            lines.append(s.text)
            lines.append("")
        return "\n".join(lines)

    def _parse_scene_response(self, response: str) -> list[dict[str, Any]]:
        """解析 LLM 场景标注响应

        期望 JSON 数组格式，每个元素包含 scene_id, scene_type, tags,
        multi_score, summary。
        """
        cleaned = response.strip()

        # 移除 markdown 代码块标记
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        # 尝试提取 JSON 数组
        start_bracket = cleaned.find("[")
        end_bracket = cleaned.rfind("]")
        if start_bracket >= 0 and end_bracket > start_bracket:
            cleaned = cleaned[start_bracket:end_bracket + 1]

        # 尝试直接解析
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            # 如果是对象且包含 scenes 键
            if isinstance(data, dict) and "scenes" in data:
                return data["scenes"]
        except json.JSONDecodeError:
            pass

        # 修复后重试
        try:
            fixed = self._repair_json(cleaned)
            data = json.loads(fixed)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "scenes" in data:
                return data["scenes"]
        except json.JSONDecodeError:
            pass

        console.print("[yellow]! Scene 标注 JSON 解析失败，返回空列表[/yellow]")
        return []

    def analyze_scenes(
        self,
        scenes: list,  # list[Scene] from clip_engine.models
        user_prompt: str | None = None,
        max_scenes_per_batch: int = 50,
    ) -> list:  # list[Scene] with annotations
        """对场景列表进行 LLM 标注

        流程:
        1. 将场景分批（避免超过上下文窗口）
        2. 每批调用 LLM 获取标注
        3. 将标注结果写回 Scene 对象

        Args:
            scenes: 待标注的 Scene 列表
            user_prompt: 用户自定义指令（注入到 system prompt 中）
            max_scenes_per_batch: 每批最大场景数

        Returns:
            标注后的 Scene 列表（原地修改）
        """
        if not scenes:
            return scenes

        console.print(
            f"[dim]待标注 {len(scenes)} 个场景, "
            f"每批最多 {max_scenes_per_batch} 个[/dim]"
        )

        # 分批处理
        for batch_start in range(0, len(scenes), max_scenes_per_batch):
            batch_end = min(batch_start + max_scenes_per_batch, len(scenes))
            batch = scenes[batch_start:batch_end]

            batch_num = batch_start // max_scenes_per_batch + 1
            total_batches = (len(scenes) + max_scenes_per_batch - 1) // max_scenes_per_batch

            console.print(
                f"[bold]标注批次 {batch_num}/{total_batches}[/bold] "
                f"({len(batch)} 个场景)"
            )

            # 构建场景文本
            scenes_text = self._build_scenes_text(batch)

            # 构建 prompt（支持用户指令注入）
            prompt = self._scene_prompt
            if user_prompt:
                # 在 prompt 末尾追加用户指令
                prompt = (
                    prompt
                    + f"\n\n## 用户额外指令\n\n{user_prompt}\n\n"
                    + "请根据以上用户指令调整标签选择和评分倾向。\n"
                    + "例如：如果用户要求'切情侣吵架片段'，"
                    + "则对包含争吵、情感冲突的场景提高 emotion 和 action 评分。"
                )
            prompt = re.sub(
                r'\{scenes_text\}', scenes_text, prompt
            )

            # 构建 system prompt
            system = self._system_prompt

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]

            # 调用 LLM
            response = self._call_llm(messages)
            parsed = self._parse_scene_response(response)

            # 将标注结果写回 Scene 对象
            annotated_count = 0
            for item in parsed:
                scene_id = item.get("scene_id")
                if scene_id is None:
                    continue

                # Find matching Scene
                scene = None
                for s in batch:
                    if s.scene_id == scene_id:
                        scene = s
                        break

                if scene is None:
                    continue

                # Write annotations
                scene.scene_type = item.get("scene_type", scene.scene_type)
                scene.tags = item.get("tags", scene.tags)
                scene.summary = item.get("summary", scene.summary)
                scene.multi_score = item.get("multi_score", scene.multi_score)
                annotated_count += 1

            console.print(
                f"[green]OK[/green] Batch {batch_num} done: "
                f"{annotated_count}/{len(batch)} scenes"
            )

        console.print(
            f"[green]OK[/green] Scene annotation complete ({len(scenes)} scenes)"
        )

        return scenes

    # ================================================================= #
    # Final Review (Smart Clip Engine v2.0 - Stage 2 filtering)
    # ================================================================= #

    def _build_candidates_text(self, candidates: list) -> str:
        """Build candidate text for LLM Final Review"""
        lines = []
        for i, c in enumerate(candidates):
            scene = c.scene
            lines.append(
                f"[{i+1}] Scene #{scene.scene_id} "
                f"[{scene.start:.1f}s - {scene.end:.1f}s] "
                f"({scene.duration:.1f}s) | "
                f"Score: {c.composite_score:.2f} | "
                f"Type: {scene.scene_type} | "
                f"Tags: {', '.join(scene.tags) if scene.tags else 'none'}"
            )
            if scene.summary:
                lines.append(f"    Summary: {scene.summary}")
            ms = scene.multi_score
            if ms:
                dims = ", ".join(
                    f"{k}={v:.1f}" for k, v in ms.items() if v > 3.0
                )
                lines.append(f"    Scores: {dims}")
            lines.append("")
        return "\n".join(lines)

    def _parse_final_review_response(self, response: str) -> dict[str, Any]:
        """Parse LLM Final Review response"""
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        start_brace = cleaned.find("{")
        end_brace = cleaned.rfind("}")
        if start_brace >= 0 and end_brace > start_brace:
            cleaned = cleaned[start_brace:end_brace + 1]

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        try:
            fixed = self._repair_json(cleaned)
            data = json.loads(fixed)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        console.print("[yellow]Final Review JSON parse failed, returning empty[/yellow]")
        return {"selected": [], "rejected": [], "overall_comment": ""}

    def final_review(
        self,
        candidates: list,
        num_to_select: int | None = None,
        platform: str = "douyin",
        target_duration: float = 0.0,
        user_prompt: str | None = None,
    ) -> list:
        """LLM Final Review - Stage 2 filtering

        Performs LLM-based final selection and re-ranking of candidates
        after rule engine filtering.
        """
        if not candidates:
            return candidates

        if num_to_select is None or num_to_select >= len(candidates):
            num_to_select = len(candidates)

        console.print(
            f"[bold]LLM Final Review[/bold]: "
            f"Select {num_to_select} from {len(candidates)} candidates"
        )
        if platform:
            console.print(f"[dim]Platform: {platform}[/dim]")
        if target_duration > 0:
            console.print(f"[dim]Target duration: {target_duration:.0f}s[/dim]")
        if user_prompt:
            console.print(f"[dim]User prompt: {user_prompt}[/dim]")

        candidates_text = self._build_candidates_text(candidates)

        prompt = self._final_review_prompt.format(
            candidates_text=candidates_text,
            user_prompt=user_prompt or "No special requirements",
            num_to_select=num_to_select,
            platform=platform,
            target_duration=target_duration,
        )

        system = (
            "You are a professional short video editor and content strategist. "
            "Select the best clips and rank them for playback order. "
            "Output must be strict JSON format."
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        response = self._call_llm(messages)
        parsed = self._parse_final_review_response(response)

        selected_items = parsed.get("selected", [])
        rejected_items = parsed.get("rejected", [])
        comment = parsed.get("overall_comment", "")

        if comment:
            console.print(f"[dim]Review: {comment}[/dim]")

        if not selected_items:
            console.print(
                "[yellow]Final Review returned no selection, using original order[/yellow]"
            )
            return candidates

        candidate_map = {c.scene_id: c for c in candidates}

        result = []
        for item in selected_items:
            scene_id = item.get("scene_id")
            if scene_id is not None and scene_id in candidate_map:
                c = candidate_map[scene_id]
                c._review_role = item.get("role", "auto")
                c._review_reason = item.get("reason", "")
                result.append(c)

        console.print(
            f"[green]OK[/green] Final Review done: "
            f"{len(result)} clips selected"
            + (f", {len(rejected_items)} rejected" if rejected_items else "")
        )

        return result if result else candidates
