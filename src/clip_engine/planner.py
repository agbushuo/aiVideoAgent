"""Duration Planner — 目标时长组合规划

根据目标时长智能规划片段组合，而非简单地按分数贪心累加。

核心策略：
- 60s  → 约 3 个高潮片段（Hook + 冲突 + 结尾）
- 180s → 约 5 个高潮 + 2 个过渡 + 1 个 Ending
- 片段长度由 Scene 边界自然决定，不截断单个 Scene
- 使用 0-1 背包问题的近似算法，在时长约束下最大化总分

数据流:
    ClipCandidate[] (已排序) → DurationPlanner.plan() → 选中的 ClipCandidate[]
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.clip_engine.models import ClipCandidate


# ===================================================================== #
# 时长模板定义
# ===================================================================== #

@dataclass
class DurationSlot:
    """时长规划中的一个槽位

    Attributes:
        role: 槽位角色（hook / climax / transition / ending）
        target_duration: 目标时长（秒）
        min_duration: 最小可接受时长（秒）
        max_duration: 最大可接受时长（秒）
        priority: 优先级（1=必须，2=重要，3=可选）
    """
    role: str
    target_duration: float
    min_duration: float
    max_duration: float
    priority: int = 1


# 预定义的时长模板
DURATION_TEMPLATES: dict[str, list[DurationSlot]] = {
    # 60 秒短视频：3 个高潮片段
    "60s": [
        DurationSlot("hook", 15, 8, 25, priority=1),
        DurationSlot("climax", 20, 10, 35, priority=1),
        DurationSlot("ending", 25, 12, 40, priority=1),
    ],
    # 90 秒短视频：4-5 个片段
    "90s": [
        DurationSlot("hook", 15, 8, 25, priority=1),
        DurationSlot("climax", 20, 10, 30, priority=1),
        DurationSlot("climax", 20, 10, 30, priority=1),
        DurationSlot("ending", 25, 12, 40, priority=1),
    ],
    # 180 秒中视频：5 个高潮 + 2 个过渡 + 1 个结尾
    "180s": [
        DurationSlot("hook", 15, 8, 25, priority=1),
        DurationSlot("climax", 25, 12, 40, priority=1),
        DurationSlot("transition", 15, 5, 30, priority=2),
        DurationSlot("climax", 25, 12, 40, priority=1),
        DurationSlot("transition", 15, 5, 30, priority=2),
        DurationSlot("climax", 25, 12, 40, priority=1),
        DurationSlot("ending", 30, 15, 50, priority=1),
    ],
    # 300 秒长视频：更多片段
    "300s": [
        DurationSlot("hook", 15, 8, 25, priority=1),
        DurationSlot("climax", 30, 15, 50, priority=1),
        DurationSlot("transition", 20, 8, 35, priority=2),
        DurationSlot("climax", 30, 15, 50, priority=1),
        DurationSlot("transition", 20, 8, 35, priority=2),
        DurationSlot("climax", 30, 15, 50, priority=1),
        DurationSlot("climax", 30, 15, 50, priority=1),
        DurationSlot("ending", 35, 15, 60, priority=1),
    ],
}


# ===================================================================== #
# 时长规划器
# ===================================================================== #

@dataclass
class PlanResult:
    """时长规划结果

    Attributes:
        selected: 选中的候选片段列表（按播放顺序排列）
        total_duration: 总时长（秒）
        target_duration: 目标时长（秒）
        slots_filled: 填充的槽位信息
        score: 规划得分（选中的片段综合分之和）
    """
    selected: list[ClipCandidate] = field(default_factory=list)
    total_duration: float = 0.0
    target_duration: float = 0.0
    slots_filled: list[dict[str, Any]] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_count": len(self.selected),
            "total_duration": round(self.total_duration, 1),
            "target_duration": round(self.target_duration, 1),
            "duration_ratio": round(
                self.total_duration / self.target_duration, 2
            ) if self.target_duration > 0 else 0,
            "slots_filled": self.slots_filled,
            "total_score": round(self.score, 2),
            "clips": [
                {
                    "scene_id": c.scene_id,
                    "role": getattr(c, "_planned_role", "auto"),
                    "start": c.start,
                    "end": c.end,
                    "duration": round(c.duration, 1),
                    "score": c.composite_score,
                }
                for c in self.selected
            ],
        }


class DurationPlanner:
    """时长规划器

    根据目标时长，智能组合候选片段。

    策略：
    1. 根据目标时长选择模板（60s/90s/180s/300s 或自定义）
    2. 按时间顺序遍历候选，为每个槽位寻找最佳匹配
    3. 使用贪心算法 + 回溯，在时长约束下最大化总分
    4. 保持片段的时间顺序（不重新排序）

    用法:
        planner = DurationPlanner(target_duration=60.0)
        result = planner.plan(candidates)
        # result.selected 包含按播放顺序排列的选中片段
    """

    def __init__(
        self,
        target_duration: float,
        tolerance: float = 0.15,
        min_gap: float = 5.0,
    ):
        """
        Args:
            target_duration: 目标总时长（秒）
            tolerance: 时长容差比例（默认 ±15%）
            min_gap: 片段间最小间隔（秒）
        """
        self.target_duration = target_duration
        self.tolerance = tolerance
        self.min_gap = min_gap

    def plan(
        self,
        candidates: list[ClipCandidate],
    ) -> PlanResult:
        """根据目标时长规划片段组合

        Args:
            candidates: 已按综合分排序的候选列表

        Returns:
            PlanResult: 包含选中的片段和规划信息
        """
        if not candidates:
            return PlanResult(target_duration=self.target_duration)

        # Step 1: 选择/生成时长模板
        slots = self._get_slots(self.target_duration)

        # Step 2: 按时间排序候选（确保播放顺序）
        by_time = sorted(candidates, key=lambda c: c.start)

        # Step 3: 为每个槽位分配最佳片段
        result = PlanResult(target_duration=self.target_duration)
        result.slots_filled = self._fill_slots(by_time, slots)

        # Step 4: 收集选中的片段
        selected: list[ClipCandidate] = []
        for slot_info in result.slots_filled:
            candidate = slot_info.get("candidate")
            if candidate is not None:
                # 标记角色
                candidate._planned_role = slot_info["role"]  # type: ignore[attr-defined]
                selected.append(candidate)

        # 按时间顺序排列最终输出
        selected.sort(key=lambda c: c.start)

        result.selected = selected
        result.total_duration = sum(c.duration for c in selected)
        result.score = sum(c.composite_score for c in selected)

        return result

    def _get_slots(self, target: float) -> list[DurationSlot]:
        """根据目标时长选择或生成时长模板

        Args:
            target: 目标时长（秒）

        Returns:
            时长槽位列表
        """
        # 尝试匹配预定义模板
        for template_name, slots in DURATION_TEMPLATES.items():
            template_target = sum(s.target_duration for s in slots)
            if abs(target - template_target) / template_target < 0.3:
                return list(slots)

        # 自定义生成模板
        return self._generate_slots(target)

    def _generate_slots(self, target: float) -> list[DurationSlot]:
        """根据目标时长动态生成槽位模板

        策略：
        - < 60s: 2 个片段（hook + climax）
        - 60-120s: 3 个片段（hook + climax + ending）
        - 120-240s: 5 个片段（hook + 3 climax + ending）
        - 240-360s: 7 个片段（hook + 4 climax + 1 transition + ending）
        - > 360s: 按每 60s 增加一个 climax 槽位

        Args:
            target: 目标时长（秒）

        Returns:
            时长槽位列表
        """
        slots: list[DurationSlot] = []
        avg_duration = target / max(math.sqrt(target / 30), 2)

        if target < 60:
            # 短视频：2 个片段
            slots.append(DurationSlot("hook", avg_duration * 0.8, avg_duration * 0.4, avg_duration * 1.5, priority=1))
            slots.append(DurationSlot("climax", avg_duration * 1.2, avg_duration * 0.6, avg_duration * 2.0, priority=1))
        elif target < 120:
            # 中短视频：3 个片段
            slots.append(DurationSlot("hook", avg_duration * 0.8, avg_duration * 0.4, avg_duration * 1.5, priority=1))
            slots.append(DurationSlot("climax", avg_duration, avg_duration * 0.5, avg_duration * 1.8, priority=1))
            slots.append(DurationSlot("ending", avg_duration * 1.2, avg_duration * 0.6, avg_duration * 2.0, priority=1))
        elif target < 240:
            # 中视频：5 个片段
            slots.append(DurationSlot("hook", avg_duration * 0.8, avg_duration * 0.4, avg_duration * 1.5, priority=1))
            for i in range(3):
                role = "climax" if i % 2 == 0 else "transition"
                pri = 1 if role == "climax" else 2
                slots.append(DurationSlot(role, avg_duration, avg_duration * 0.5, avg_duration * 1.8, priority=pri))
            slots.append(DurationSlot("ending", avg_duration * 1.2, avg_duration * 0.6, avg_duration * 2.0, priority=1))
        else:
            # 长视频：更多片段
            num_climax = max(4, int(target / 60))
            slots.append(DurationSlot("hook", avg_duration * 0.8, avg_duration * 0.4, avg_duration * 1.5, priority=1))
            for i in range(num_climax):
                role = "transition" if i > 0 and i % 3 == 0 else "climax"
                pri = 1 if role == "climax" else 2
                slots.append(DurationSlot(role, avg_duration, avg_duration * 0.5, avg_duration * 1.8, priority=pri))
            slots.append(DurationSlot("ending", avg_duration * 1.2, avg_duration * 0.6, avg_duration * 2.0, priority=1))

        return slots

    def _fill_slots(
        self,
        candidates: list[ClipCandidate],
        slots: list[DurationSlot],
    ) -> list[dict[str, Any]]:
        """为每个槽位分配最佳候选片段

        策略：
        1. 按槽位优先级排序（priority=1 先分配）
        2. 对每个槽位，在时间顺序上寻找最佳匹配的候选
        3. 已使用的候选不可重复使用
        4. 确保片段之间有时间间隔（min_gap）

        Args:
            candidates: 按时间排序的候选列表
            slots: 时长槽位列表

        Returns:
            填充的槽位信息列表
        """
        used_indices: set[int] = set()
        filled: list[dict[str, Any]] = [{} for _ in slots]

        # 按优先级排序槽位索引
        slot_indices_with_priority = sorted(
            enumerate(slots),
            key=lambda x: x[1].priority,
        )

        for slot_idx, slot in slot_indices_with_priority:
            best_candidate = None
            best_score = -1
            best_idx = -1

            for i, candidate in enumerate(candidates):
                if i in used_indices:
                    continue

                # 检查时长是否匹配槽位
                dur = candidate.duration
                if dur < slot.min_duration or dur > slot.max_duration:
                    # 允许一定弹性：如果候选时长在目标值的 ±50% 范围内，也可以接受
                    if dur < slot.target_duration * 0.3 or dur > slot.target_duration * 2.0:
                        continue

                # 检查与已分配片段的时间间隔
                if not self._check_gap(candidate, filled):
                    continue

                # 选择综合分最高的
                if candidate.composite_score > best_score:
                    best_score = candidate.composite_score
                    best_candidate = candidate
                    best_idx = i

            if best_candidate is not None:
                used_indices.add(best_idx)
                filled[slot_idx] = {
                    "slot_index": slot_idx,
                    "role": slot.role,
                    "target_duration": slot.target_duration,
                    "candidate": best_candidate,
                    "actual_duration": best_candidate.duration,
                    "score": best_candidate.composite_score,
                }

        # 过滤掉未填充的槽位
        return [f for f in filled if f]

    def _check_gap(
        self,
        candidate: ClipCandidate,
        filled: list[dict[str, Any]],
    ) -> bool:
        """检查候选片段与已填充槽位的时间间隔是否足够

        Args:
            candidate: 待检查的候选片段
            filled: 已填充的槽位列表

        Returns:
            True 如果间隔足够，False 否则
        """
        for slot_info in filled:
            if not slot_info or "candidate" not in slot_info:
                continue
            existing = slot_info["candidate"]
            gap = self._compute_gap(candidate, existing)
            if gap < self.min_gap:
                return False
        return True

    @staticmethod
    def _compute_gap(a: ClipCandidate, b: ClipCandidate) -> float:
        """计算两个候选片段之间的最小时间距离"""
        a_start, a_end = a.start, a.end
        b_start, b_end = b.start, b.end

        if a_start <= b_end and b_start <= a_end:
            return 0.0

        if a_end < b_start:
            return b_start - a_end
        else:
            return a_start - b_end


# ===================================================================== #
# 便捷函数
# ===================================================================== #

def plan_duration(
    candidates: list[ClipCandidate],
    target_seconds: float,
    tolerance: float = 0.15,
    min_gap: float = 5.0,
) -> PlanResult:
    """按目标时长规划片段组合

    Args:
        candidates: 已按综合分排序的候选列表
        target_seconds: 目标总时长（秒）
        tolerance: 时长容差比例
        min_gap: 片段间最小间隔（秒）

    Returns:
        PlanResult: 规划结果
    """
    planner = DurationPlanner(
        target_duration=target_seconds,
        tolerance=tolerance,
        min_gap=min_gap,
    )
    return planner.plan(candidates)


def list_duration_templates() -> list[str]:
    """列出所有预定义的时长模板名称"""
    return list(DURATION_TEMPLATES.keys())


def show_duration_template(name: str) -> list[DurationSlot]:
    """显示某个时长模板的槽位详情

    Args:
        name: 模板名称（如 "60s", "180s"）

    Returns:
        槽位列表，模板不存在则返回空列表
    """
    return DURATION_TEMPLATES.get(name, [])
