"""LLM Final Review — 二阶段筛选（最终评审）

在规则引擎（Score + Filter + Duration Planner）筛选后，
可选地调用 LLM 对候选片段做最终精选和重排序。

核心思路：
- Stage 1（程序）：Scene 标注 → 评分 → 去重 → 时长规划
- Stage 2（LLM）：从候选集中精选 N 个 + 按叙事节奏排序

数据流:
    ClipCandidate[] (规则筛选后) → FinalReviewer.review()
        → 精选并排序的 ClipCandidate[]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.clip_engine.models import ClipCandidate


# ===================================================================== #
# Final Review 结果
# ===================================================================== #

@dataclass
class ReviewSelection:
    """LLM Final Review 的单条选中记录

    Attributes:
        scene_id: 场景编号
        role: 在成片中的角色（hook/buildup/climax/transition/ending）
        reason: 选中理由
    """
    scene_id: int
    role: str = "auto"
    reason: str = ""


@dataclass
class ReviewResult:
    """LLM Final Review 的完整结果

    Attributes:
        selected: 选中的场景 ID 列表（按播放顺序）
        rejected: 被拒绝的场景及理由
        overall_comment: LLM 对整体选择的评论
        candidates: 精选并排序后的候选片段列表
    """
    selected: list[ReviewSelection] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    overall_comment: str = ""
    candidates: list[Any] = field(default_factory=list)  # list[ClipCandidate]

    @property
    def selected_count(self) -> int:
        return len(self.candidates)

    @property
    def selected_scene_ids(self) -> list[int]:
        return [s.scene_id for s in self.selected]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": [
                {"scene_id": s.scene_id, "role": s.role, "reason": s.reason}
                for s in self.selected
            ],
            "rejected": self.rejected,
            "overall_comment": self.overall_comment,
            "selected_count": self.selected_count,
        }


# ===================================================================== #
# Final Reviewer
# ===================================================================== #

class FinalReviewer:
    """LLM Final Reviewer — 二阶段筛选

    对规则引擎筛选后的候选片段进行 LLM 最终精选和重排序。

    用法:
        reviewer = FinalReviewer(
            llm_analyzer=analyzer,
            num_to_select=5,
            platform="douyin",
        )
        result = reviewer.review(candidates)
        # result.candidates 包含精选并排序后的片段

    注意:
        - 需要 LLMAnalyzer 实例作为后端
        - 如果 LLM 调用失败，返回原始候选列表（降级策略）
    """

    def __init__(
        self,
        llm_analyzer: Any,  # LLMAnalyzer — 避免循环导入
        num_to_select: int | None = None,
        platform: str = "douyin",
        target_duration: float = 0.0,
        user_prompt: str | None = None,
    ):
        """
        Args:
            llm_analyzer: LLMAnalyzer 实例（用于调用 LLM）
            num_to_select: 需要精选的片段数量（None 则不限制）
            platform: 目标平台（douyin/youtube/bilibili）
            target_duration: 目标总时长（秒）
            user_prompt: 用户自定义指令
        """
        self.llm = llm_analyzer
        self.num_to_select = num_to_select
        self.platform = platform
        self.target_duration = target_duration
        self.user_prompt = user_prompt

    def review(
        self,
        candidates: list[Any],  # list[ClipCandidate]
    ) -> ReviewResult:
        """执行 LLM Final Review

        Args:
            candidates: 候选片段列表（已按综合分排序）

        Returns:
            ReviewResult: 包含精选结果和排序后的候选列表
        """
        if not candidates:
            return ReviewResult()

        # 调用 LLM 进行最终评审
        reviewed = self.llm.final_review(
            candidates=candidates,
            num_to_select=self.num_to_select,
            platform=self.platform,
            target_duration=self.target_duration,
            user_prompt=self.user_prompt,
        )

        # 构建结果对象
        result = ReviewResult(candidates=reviewed)

        # 提取每个候选的评审信息
        for c in reviewed:
            role = getattr(c, "_review_role", "auto")
            reason = getattr(c, "_review_reason", "")
            result.selected.append(
                ReviewSelection(
                    scene_id=c.scene_id,
                    role=role,
                    reason=reason,
                )
            )

        return result


# ===================================================================== #
# 便捷函数
# ===================================================================== #

def final_review(
    candidates: list[Any],  # list[ClipCandidate]
    llm_analyzer: Any,  # LLMAnalyzer
    num_to_select: int | None = None,
    platform: str = "douyin",
    target_duration: float = 0.0,
    user_prompt: str | None = None,
) -> ReviewResult:
    """便捷函数：执行 LLM Final Review

    Args:
        candidates: 候选片段列表
        llm_analyzer: LLMAnalyzer 实例
        num_to_select: 精选数量
        platform: 目标平台
        target_duration: 目标时长
        user_prompt: 用户自定义指令

    Returns:
        ReviewResult: 评审结果
    """
    reviewer = FinalReviewer(
        llm_analyzer=llm_analyzer,
        num_to_select=num_to_select,
        platform=platform,
        target_duration=target_duration,
        user_prompt=user_prompt,
    )
    return reviewer.review(candidates)
