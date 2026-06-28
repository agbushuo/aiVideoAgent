"""预设管理器

管理 data/presets.json 中的预设数据，以及 prompts/ 目录下的 Prompt 模板文件。
每个预设包含管线参数、评分权重和 Prompt 覆盖。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 预设数据文件
PRESETS_FILE = Path(__file__).parents[2] / "data" / "presets.json"
# Prompt 模板目录
PROMPTS_DIR = Path(__file__).parents[2] / "prompts"
# 权重文件
WEIGHTS_FILE = Path(__file__).parents[2] / "src" / "clip_engine" / "weights.json"

# 可编辑的 Prompt 模板（排除 system.md 和 legacy 文件）
EDITABLE_PROMPTS = ["scene_analysis", "final_review"]

# 默认显示名称映射
DISPLAY_NAMES = {
    "douyin": "抖音爆款",
    "youtube": "YouTube 长视频",
    "bilibili": "B 站风格",
    "viral": "病毒传播",
    "all": "均衡模式",
}

DESCRIPTIONS = {
    "douyin": "适合抖音平台的短视频剪辑，强调开头吸引力和情绪爆发",
    "youtube": "适合 YouTube 平台，侧重信息密度和高潮内容",
    "bilibili": "适合 B 站风格，平衡知识性和娱乐性",
    "viral": "追求病毒式传播，强调开头和搞笑元素",
    "all": "均衡评分，所有维度权重相等",
}


def _load_weights() -> dict[str, Any]:
    """加载权重配置"""
    if WEIGHTS_FILE.exists():
        with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _generate_default_presets() -> list[dict[str, Any]]:
    """从 weights.json 生成默认预设"""
    weights_data = _load_weights()
    preset_weights = weights_data.get("preset", {})
    presets = []

    for name, weights in preset_weights.items():
        presets.append({
            "name": name,
            "displayName": DISPLAY_NAMES.get(name, name),
            "description": DESCRIPTIONS.get(name, ""),
            "stageParams": {
                "transcribe": {"language": "zh", "model_name": "whisper-large-v3", "device": "cuda"},
                "scene_detection": {"gap_threshold": 10, "min_scene_duration": 3, "max_scene_duration": 120},
                "llm_annotation": {"user_prompt": ""},
                "scoring": {"preset": name, "clip_mode": "all"},
                "filtering": {"max_clips": 0, "min_gap": 0, "target_duration": 0},
                "duration_planning": {"target_duration": 0},
                "final_review": {"num_to_select": None},
                "clipping": {"merge": True, "transition": 0.5},
            },
            "weights": weights,
            "prompts": {},  # 默认不覆盖 prompt
        })

    return presets


class PresetManager:
    """预设管理单例"""

    _instance: PresetManager | None = None
    _presets: list[dict[str, Any]]

    def __new__(cls) -> PresetManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._presets = []
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """加载预设数据，文件不存在时从 weights.json 生成默认预设"""
        if PRESETS_FILE.exists():
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                self._presets = json.load(f)
        else:
            # 首次加载，生成默认预设
            self._presets = _generate_default_presets()
            self._save_now()

    def _save_now(self) -> None:
        """立即保存预设数据到文件"""
        PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._presets, f, ensure_ascii=False, indent=2)

    def list(self) -> list[dict[str, Any]]:
        """列出所有预设"""
        return self._presets

    def get(self, name: str) -> dict[str, Any] | None:
        """获取指定预设"""
        for p in self._presets:
            if p["name"] == name:
                return p
        return None

    def save(self, preset: dict[str, Any]) -> dict[str, Any]:
        """创建或更新预设"""
        name = preset["name"]
        existing = self.get(name)
        if existing:
            # 更新
            idx = self._presets.index(existing)
            self._presets[idx] = preset
        else:
            # 新增
            self._presets.append(preset)
        self._save_now()
        return preset

    def delete(self, name: str) -> bool:
        """删除预设"""
        for i, p in enumerate(self._presets):
            if p["name"] == name:
                self._presets.pop(i)
                self._save_now()
                return True
        return False

    def duplicate(self, name: str, new_name: str) -> dict[str, Any] | None:
        """复制预设"""
        preset = self.get(name)
        if not preset:
            return None
        new_preset = dict(preset)
        new_preset["name"] = new_name
        new_preset["displayName"] = f"{preset['displayName']} (副本)"
        new_preset["stageParams"] = {k: dict(v) if isinstance(v, dict) else v for k, v in preset["stageParams"].items()}
        new_preset["weights"] = dict(preset["weights"])
        new_preset["prompts"] = dict(preset["prompts"])
        self.save(new_preset)
        return new_preset

    # ── Prompt 管理 ──

    def list_prompts(self) -> list[str]:
        """列出可用的 Prompt 模板名称"""
        return list(EDITABLE_PROMPTS)

    def get_prompt(self, name: str) -> str | None:
        """读取 Prompt 模板内容"""
        prompt_file = PROMPTS_DIR / f"{name}.md"
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def save_prompt(self, name: str, content: str) -> bool:
        """保存 Prompt 模板文件（写入 prompts/ 目录，影响所有预设共享的默认模板）"""
        prompt_file = PROMPTS_DIR / f"{name}.md"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(content)
        return True
