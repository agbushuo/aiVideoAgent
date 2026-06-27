"""Scene Detection — 场景切分引擎

将连续的 Whisper segment 按语义分组为 Scene。

当前方案（MVP）：基于 Whisper segment 时间间隔分组
- 时间间隔 > 阈值（默认 5 秒静音）→ 新 Scene
- 每个 Scene 包含多个 segment，形成独立的内容块

预留接口：
- OpenCVSceneDetector — 基于帧差异的场景检测（未来）
- 说话人变化检测（未来通过 VAD 或音频特征）
- 话题变化检测（LLM 判断，未来）
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from src.clip_engine.models import Scene

if TYPE_CHECKING:
    from src.transcribe.models import Segment


# ===================================================================== #
# 抽象基类
# ===================================================================== #

class SceneDetector(abc.ABC):
    """场景检测器抽象基类

    定义了场景检测的统一接口，支持不同的检测策略：
    - WhisperSegmentDetector: 基于字幕时间间隔（MVP）
    - OpenCVSceneDetector: 基于视频帧差异（未来）
    """

    @abc.abstractmethod
    def detect_scenes(
        self,
        segments: list[Segment],
        video_path: str | None = None,
    ) -> list[Scene]:
        """检测场景

        Args:
            segments: Whisper 转录的 segment 列表
            video_path: 源视频路径（OpenCV 方案需要）

        Returns:
            检测到的 Scene 列表
        """
        ...


# ===================================================================== #
# Whisper Segment 分组检测器（MVP）
# ===================================================================== #

class WhisperSegmentDetector(SceneDetector):
    """基于 Whisper segment 时间间隔的场景检测器

    核心逻辑：
    1. 按时间顺序遍历 segment
    2. 当相邻 segment 之间的间隔超过阈值时，认为是新 Scene 的开始
    3. 将连续的 segment 分组为一个 Scene

    参数调优建议：
    - gap_threshold: 默认 5 秒。对话类视频可设为 3-5s，
      演讲类可设为 8-10s，游戏录播可设为 10-15s
    - min_scene_duration: 默认 3 秒。过滤掉过短的片段
    - max_scene_duration: 默认 120 秒。过长的 Scene 会被强制拆分
    """

    def __init__(
        self,
        gap_threshold: float = 5.0,
        min_scene_duration: float = 3.0,
        max_scene_duration: float = 120.0,
    ):
        """
        Args:
            gap_threshold: 场景间隔阈值（秒），超过此间隔视为新场景
            min_scene_duration: 最小场景时长（秒），短于此值的场景会被合并到前一个场景
            max_scene_duration: 最大场景时长（秒），长于此值的场景会被强制拆分
        """
        self.gap_threshold = gap_threshold
        self.min_scene_duration = min_scene_duration
        self.max_scene_duration = max_scene_duration

    def detect_scenes(
        self,
        segments: list[Segment],
        video_path: str | None = None,
    ) -> list[Scene]:
        """基于时间间隔将 segment 分组为 Scene

        流程：
        1. 按时间排序 segment（Whisper 通常已排序，但做防御性处理）
        2. 遍历 segment，间隔 > gap_threshold 时分新组
        3. 合并过短的 Scene（< min_scene_duration）
        4. 拆分过长的 Scene（> max_scene_duration）
        5. 构建 Scene 对象
        """
        if not segments:
            return []

        # 按开始时间排序
        sorted_segs = sorted(segments, key=lambda s: s.start)

        # Step 1: 按时间间隔分组
        groups: list[list[Segment]] = []
        current_group: list[Segment] = [sorted_segs[0]]

        for i in range(1, len(sorted_segs)):
            prev_end = sorted_segs[i - 1].end
            curr_start = sorted_segs[i].start
            gap = curr_start - prev_end

            if gap > self.gap_threshold:
                # 间隔超过阈值，开始新组
                groups.append(current_group)
                current_group = []

            current_group.append(sorted_segs[i])

        # 最后一组
        if current_group:
            groups.append(current_group)

        # Step 2: 合并过短的 Scene
        groups = self._merge_short_scenes(groups)

        # Step 3: 拆分过长的 Scene
        groups = self._split_long_scenes(groups)

        # Step 4: 构建 Scene 对象
        scenes = []
        for idx, group in enumerate(groups):
            scene = Scene.from_segments(group, scene_id=idx)
            scenes.append(scene)

        return scenes

    def _merge_short_scenes(
        self, groups: list[list[Segment]]
    ) -> list[list[Segment]]:
        """合并时长过短的 Scene 到相邻 Scene"""
        if len(groups) <= 1:
            return groups

        merged: list[list[Segment]] = [groups[0]]

        for i in range(1, len(groups)):
            prev_group = merged[-1]
            curr_group = groups[i]

            # 计算当前组的时长
            curr_start = curr_group[0].start
            curr_end = curr_group[-1].end
            curr_duration = curr_end - curr_start

            if curr_duration < self.min_scene_duration:
                # 合并到前一个组
                merged[-1] = prev_group + curr_group
            else:
                merged.append(curr_group)

        return merged

    def _split_long_scenes(
        self, groups: list[list[Segment]]
    ) -> list[list[Segment]]:
        """拆分时长过长的 Scene

        策略：在最长 gap 处拆分，确保拆分点在自然停顿处
        """
        result: list[list[Segment]] = []

        for group in groups:
            start = group[0].start
            end = group[-1].end
            duration = end - start

            if duration <= self.max_scene_duration:
                result.append(group)
                continue

            # 找到组内最大的时间间隔作为拆分点
            gaps = []
            for j in range(1, len(group)):
                gap = group[j].start - group[j - 1].end
                gaps.append((gap, j))

            # No gaps to split on (single segment or contiguous) — keep as-is
            if not gaps:
                result.append(group)
                continue

            # 按 gap 大小降序排序
            gaps.sort(reverse=True)

            # 在最大 gap 处拆分
            _, split_idx = gaps[0]
            left = group[:split_idx]
            right = group[split_idx:]

            # 递归拆分（处理拆分后仍然过长的情况）
            left_split = self._split_long_scenes([left])[0] if left else []
            right_split = self._split_long_scenes([right])[0] if right else []

            result.extend([g for g in [left_split, right_split] if g])

        return result


# ===================================================================== #
# OpenCV 场景检测器（预留接口）
# ===================================================================== #

class OpenCVSceneDetector(SceneDetector):
    """基于 OpenCV 帧差异的场景检测器

    使用帧间差异检测视频中的场景切换点。
    当前为预留接口，具体实现待后续添加。

    实现计划：
    1. 使用 cv2 读取视频帧
    2. 计算相邻帧之间的差异（MSE / SSIM）
    3. 差异超过阈值时标记为场景切换点
    4. 与 Whisper segment 时间对齐
    """

    def __init__(
        self,
        threshold: float = 30.0,
        min_scene_duration: float = 2.0,
        fps: int = 1,  # 采样帧率，1fps 足够检测场景切换
    ):
        """
        Args:
            threshold: 帧差异阈值（0-255），超过此值视为场景切换
            min_scene_duration: 最小场景时长（秒）
            fps: 采样帧率
        """
        self.threshold = threshold
        self.min_scene_duration = min_scene_duration
        self.fps = fps

    def detect_scenes(
        self,
        segments: list[Segment],
        video_path: str | None = None,
    ) -> list[Scene]:
        """OpenCV 场景检测（预留接口）

        TODO: 实现基于帧差异的场景检测
        - 需要 video_path 参数
        - 需要 cv2 / numpy 依赖
        - 检测结果需与 Whisper segment 时间对齐
        """
        if video_path is None:
            raise ValueError(
                "OpenCVSceneDetector 需要 video_path 参数"
            )

        raise NotImplementedError(
            "OpenCVSceneDetector 尚未实现。"
            "当前请使用 WhisperSegmentDetector。"
            "实现计划: 使用 cv2 读取帧，计算帧间差异，"
            "与 Whisper segment 时间对齐。"
        )
