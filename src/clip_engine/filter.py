"""Filter Engine — 去重合并、Diversity 最小间隔、时长约束、数量控制

对 Score Engine 输出的 ClipCandidate 列表进行筛选：
1. Diversity 去重：同一时间区域内只保留最高分的片段
2. 数量控制：限制输出片段数量（--clips N）
3. 时长约束：控制总时长不超过目标值（--duration）

数据流:
    ClipCandidate[] (已排序) → ClipFilter.filter() → 选中的 ClipCandidate[]
"""

from __future__ import annotations

from src.clip_engine.models import ClipCandidate


class ClipFilter:
    """剪辑过滤器

    对评分后的候选片段进行多样性去重、数量控制和时长约束。

    用法:
        filter = ClipFilter(min_gap=120.0, max_clips=5, target_duration=60.0)
        selected = filter.filter(candidates)
        # selected 中的 candidate.selected = True
    """

    def __init__(
        self,
        min_gap: float = 120.0,
        max_clips: int = 0,
        target_duration: float = 0.0,
    ):
        """
        Args:
            min_gap: 最小间隔（秒），默认 120 秒（2 分钟）。
                     与已选中片段距离 < min_gap 的候选中，只保留最高分。
            max_clips: 最大片段数量。0 表示不限制。
            target_duration: 目标总时长（秒）。0 表示不限制。
                            当设置时，筛选的片段总时长尽量接近此值。
        """
        self.min_gap = min_gap
        self.max_clips = max_clips
        self.target_duration = target_duration

    def filter(
        self, candidates: list[ClipCandidate]
    ) -> list[ClipCandidate]:
        """执行完整的筛选流程

        流程:
        1. Diversity 去重（min_gap 滑动窗口）
        2. 数量控制（max_clips）
        3. 时长约束（target_duration）
        4. 标记选中状态

        Args:
            candidates: 已按综合分排序的 ClipCandidate 列表

        Returns:
            筛选后的 ClipCandidate 列表（selected=True）
        """
        if not candidates:
            return []

        # Step 1: Diversity 去重
        diversified = self._diversify(candidates)

        # Step 2: 数量控制
        if self.max_clips > 0:
            diversified = diversified[: self.max_clips]

        # Step 3: 时长约束
        if self.target_duration > 0:
            diversified = self._fit_duration(diversified)

        # Step 4: 标记选中状态
        for candidate in diversified:
            candidate.selected = True

        return diversified

    def _diversify(
        self, candidates: list[ClipCandidate]
    ) -> list[ClipCandidate]:
        """Diversity 去重 — 同一时间区域内只保留最高分的片段

        算法:
        1. 按时间排序候选片段
        2. 贪心选择：从最高分开始，如果与已选片段的最小距离 >= min_gap，则选中
        3. 确保输出的片段分布在视频的不同区域

        Args:
            candidates: 按综合分降序的候选列表

        Returns:
            去重后的候选列表
        """
        if self.min_gap <= 0:
            return candidates

        # 按开始时间排序
        by_time = sorted(candidates, key=lambda c: c.start)

        selected: list[ClipCandidate] = []

        for candidate in by_time:
            # 检查与已选片段的距离
            too_close = False
            for s in selected:
                # 计算两个片段的时间距离
                gap = self._compute_gap(candidate, s)
                if gap < self.min_gap:
                    too_close = True
                    break

            if not too_close:
                selected.append(candidate)

        # 保持原始排序（按综合分降序）
        selected.sort(key=lambda c: c.composite_score, reverse=True)

        return selected

    @staticmethod
    def _compute_gap(a: ClipCandidate, b: ClipCandidate) -> float:
        """计算两个候选片段之间的最小时间距离

        距离定义为两个片段时间区间之间的最小间隔。
        如果两个片段重叠，距离为 0。

        Args:
            a, b: 两个候选片段

        Returns:
            最小时间距离（秒）
        """
        # 片段的时间区间
        a_start, a_end = a.start, a.end
        b_start, b_end = b.start, b.end

        # 检查是否重叠
        if a_start <= b_end and b_start <= a_end:
            return 0.0

        # 不重叠时的距离
        if a_end < b_start:
            return b_start - a_end
        else:
            return a_start - b_end

    def _fit_duration(
        self, candidates: list[ClipCandidate]
    ) -> list[ClipCandidate]:
        """根据目标时长筛选片段

        策略:
        1. 按综合分从高到低累加片段
        2. 当总时长接近目标时停止
        3. 允许轻微超出目标（不超过 10%）

        Args:
            candidates: 按综合分降序的候选列表

        Returns:
            符合时长约束的候选列表
        """
        if not candidates:
            return []

        max_duration = self.target_duration * 1.1  # 允许 10% 超出
        total = 0.0
        result: list[ClipCandidate] = []

        for candidate in candidates:
            # 至少保留一个片段
            if not result and candidate.duration <= max_duration:
                result.append(candidate)
                total += candidate.duration
                continue

            if total + candidate.duration <= max_duration:
                result.append(candidate)
                total += candidate.duration
            elif total + candidate.duration <= self.target_duration * 1.15:
                # 如果只轻微超出，也接受
                result.append(candidate)
                total += candidate.duration

        return result


# ===================================================================== #
# 便捷函数
# ===================================================================== #

def diversify(
    candidates: list[ClipCandidate],
    min_gap: float = 120.0,
) -> list[ClipCandidate]:
    """同一时间区域内只保留最高分的片段

    便捷函数，等价于 ClipFilter(min_gap=min_gap).filter(candidates)

    Args:
        candidates: 按综合分降序的候选列表
        min_gap: 最小间隔（秒），默认 120 秒

    Returns:
        去重后的候选列表
    """
    return ClipFilter(min_gap=min_gap).filter(candidates)


def select_top(
    candidates: list[ClipCandidate],
    n: int = 5,
    min_gap: float = 120.0,
) -> list[ClipCandidate]:
    """选择 Top N 个片段（含 Diversity 去重）

    Args:
        candidates: 按综合分降序的候选列表
        n: 选择数量
        min_gap: 最小间隔（秒）

    Returns:
        选中的候选列表
    """
    return ClipFilter(min_gap=min_gap, max_clips=n).filter(candidates)


def select_by_duration(
    candidates: list[ClipCandidate],
    target_seconds: float = 60.0,
    min_gap: float = 120.0,
) -> list[ClipCandidate]:
    """按目标时长选择片段

    Args:
        candidates: 按综合分降序的候选列表
        target_seconds: 目标总时长（秒）
        min_gap: 最小间隔（秒）

    Returns:
        选中的候选列表
    """
    return ClipFilter(
        min_gap=min_gap,
        target_duration=target_seconds,
    ).filter(candidates)
