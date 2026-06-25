# VideoAgent 项目架构规划

> 创建日期: 2026-06-22  
> 最后更新: 2026-06-25  
> 状态: Phase 1-4 已完成（Smart Clip Engine v2.0 MVP 实现）

---

## 一、项目目标

构建一个**视频自动化处理 Agent**，管线如下：

```
视频文件
  ↓
[Stage 1] Whisper large-v3 → 带时间戳字幕
  ↓
[Stage 2] LLM (Qwen/Ollama) → 内容总结 + 关键片段识别
  ↓
[Stage 3] 输出 SRT + JSON + Markdown 报告
  ↓
[Stage 4] (未来) ffmpeg 自动剪辑 → 精华视频
```

---

## 二、技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | 生态丰富、Whisper 原生支持 |
| 字幕引擎 | `openai-whisper large-v3` | 用户已验证可用、中文效果好 |
| LLM | Qwen3.6 27B via llama.cpp | 本地运行、中文理解强、API 兼容 OpenAI |
| CLI 框架 | `typer` | 现代、自动生成帮助、子命令支持 |
| 视频处理 | `ffmpeg-python` | 后期剪辑用 |
| 配置管理 | `pydantic-settings` + YAML | 类型安全、易维护 |
| 依赖管理 | `pyproject.toml` (uv/pip) | 现代 Python 项目标准 |

---

## 三、项目结构

```
aiVideoAgent/
├── pyproject.toml              # 项目元数据 + 依赖
├── config.yaml                 # 配置 (模型、路径、LLM 端点)
├── .env                        # 敏感信息 (如有)
├── .gitignore
├── README.md
├── ROADMAP.md                  # 实施路线图
├── ARCHITECTURE.md             # 本文档
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI 入口 (typer)
│   ├── pipeline.py             # 单视频全流程接口 (process_video)
│   │
│   ├── transcribe/
│   │   ├── __init__.py
│   │   ├── whisper_engine.py   # Whisper 封装
│   │   │                           #   - load_model()
│   │   │                           #   - transcribe() → TranscriptResult
│   │   │                           #   - unload()
│   │   ├── models.py           # 数据模型 (Segment, TranscriptResult)
│   │   └── merger.py           # 分段转录去重合并
│   │
│   ├── analyze/
│   │   ├── __init__.py
│   │   └── llm_analyzer.py     # LLM 分析引擎
│   │                           #   - analyze() → AnalysisReport (兼容旧版)
│   │                           #   - analyze_scenes() → list[Scene] (新版 Scene 标注)
│   │
│   ├── clip_engine/            # 智能片段筛选引擎 (Smart Clip Engine v2.0 ✅)
│   │   ├── __init__.py
│   │   ├── models.py           # Scene, ClipCandidate, ClipResult 数据模型
│   │   ├── scene_detector.py   # Scene Detection（Whisper segment 分组 + OpenCV 预留）
│   │   ├── scorer.py           # Score Engine（多维评分 + preset 权重计算）
│   │   ├── filter.py           # Filter Engine（Diversity 去重、数量/时长约束）
│   │   └── planner.py          # Duration Planner（目标时长组合规划，待实现）
│   │
│   ├── edit/
│   │   ├── __init__.py
│   │   └── clipper.py          # 视频剪辑模块 (已完成)
│   │                           #   - clips_from_report() → 从 JSON 一键提取
│   │                           #   - extract_segment() → 单个片段裁剪
│   │                           #   - merge_clips() → 拼接精华视频
│   │
│   ├── batch/
│   │   └── __init__.py         # 批量处理模块 (已完成)
│   │                           #   - discover_videos() → 发现视频文件
│   │                           #   - run_batch() → 串行批处理
│   │                           #   - BatchResult → 批处理结果聚合
│   │
│   └── utils/
│       ├── __init__.py
│       ├── video_info.py       # 视频元信息 (时长、分辨率、编码)
│       └── io.py               # 文件 I/O (SRT 读写、JSON 序列化、报告导出)
│
├── prompts/
│   ├── system.md               # LLM system prompt
│   ├── highlight_extract.md    # 亮点提取 prompt 模板 (兼容旧版)
│   └── scene_analysis.md       # Scene 标注 prompt 模板 (Smart Clip v2.0)
│
├── outputs/                    # 输出目录 (gitignore)
│   ├── subtitles/              # SRT + JSON 字幕文件
│   ├── reports/                # JSON + Markdown 报告
│   └── clips/                  # 剪辑后的视频片段 + 精华视频
│
├── logs/
│   └── CHANGELOG.md            # 变更记录
│
└── tests/
    ├── test_transcribe.py
    ├── test_analyze.py
    └── conftest.py
```

---

## 四、核心数据流

### 4.1 转录阶段

```python
# 输入: video_path (str)
# 输出: TranscriptResult (dataclass)

@dataclass
class Segment:
    start: float        # 开始时间 (秒)
    end: float          # 结束时间 (秒)
    text: str           # 字幕文本
    words: list[dict]   # 词级时间戳 (可选)

@dataclass
class TranscriptResult:
    language: str       # 检测到的语言
    segments: list[Segment]
    text: str           # 完整文本
```

### 4.2 分析阶段

```python
# 输入: TranscriptResult
# 输出: AnalysisReport (dataclass)

@dataclass
class Highlight:
    segment_id: int           # 对应字幕片段索引
    start: float              # 开始时间
    end: float                # 结束时间
    title: str                # 亮点标题
    reason: str               # 为什么值得剪
    score: float              # 重要度评分 (0-1)

@dataclass
class AnalysisReport:
    summary: str              # 视频整体总结
    highlights: list[Highlight]  # 亮点片段列表
    metadata: dict            # 分析元信息 (模型、耗时等)
```

### 4.3 输出格式

**JSON 报告** (`outputs/reports/video_20260622.json`):
```json
{
  "video": "input.mkv",
  "duration": 180.5,
  "language": "zh",
  "summary": "这是一个关于...的视频",
  "highlights": [
    {
      "segment_id": 12,
      "start": 45.2,
      "end": 78.5,
      "title": "核心观点阐述",
      "reason": "讲者在此处提出了全文最重要的论点...",
      "score": 0.95
    }
  ],
  "analysis_by": "Qwen/Ollama",
  "analyzed_at": "2026-06-22T10:30:00+08:00"
}
```

**SRT 字幕** (`outputs/subtitles/video_20260622.srt`):
```
1
00:00:00,000 --> 00:00:05,500
大家好，欢迎来到今天的视频

2
00:00:05,500 --> 00:00:12,000
今天我们来讲一讲...
```

**Markdown 报告** (`outputs/reports/video_20260622.md`):
```markdown
# 视频分析报告

## 概要
视频整体总结内容...

## 亮点片段

### 1. 核心观点阐述 (00:45 - 01:18) ⭐ 0.95
**为什么值得剪:** 讲者在此处提出了...

### 2. 案例演示 (02:30 - 03:15) ⭐ 0.88
**为什么值得剪:** 这段演示非常直观...
```

### 4.4 Smart Clip Engine 数据流

#### 4.4.1 Scene 模型

```python
# 输入: TranscriptResult
# 输出: list[Scene]

@dataclass
class Scene:
    """场景 — 由多个 Whisper segment 逻辑分组而成"""
    scene_id: int                  # 场景编号
    start: float                   # 开始时间（秒）
    end: float                     # 结束时间（秒）
    segment_ids: list[int]         # 包含的 Whisper segment 索引
    text: str                      # 场景完整文本

    # LLM 标注结果
    scene_type: str                # Dialogue / Comedy / Fight / Romance / ...
    tags: list[str]                # [搞笑, 情绪爆发, 冲突, 高能]
    summary: str                   # 场景简短描述

    # 多维评分（0-10 分制）
    multi_score: dict[str, float]  # {hook, emotion, comedy, action, ...}
```

#### 4.4.2 ClipCandidate 模型

```python
@dataclass
class ClipCandidate:
    """剪辑候选 — 由 Scene 经规则引擎筛选后生成"""
    scene: Scene
    composite_score: float         # 根据 preset 权重计算的综合分
    rank: int                      # 排序位置
    selected: bool                 # 是否被最终选中
```

#### 4.4.3 数据流

```
TranscriptResult (Whisper segment 列表)
    │
    ▼  [SceneDetector.detect_scenes()]
list[Scene] (场景列表，含时间边界和文本)
    │
    ▼  [LLMAnalyzer.scene_analysis()] — 分批调用
list[Scene] (每个 Scene 填充 scene_type, tags, multi_score, summary)
    │
    ▼  [Scorer.compute()] — 根据 preset 权重计算综合分
list[ClipCandidate] (含 composite_score)
    │
    ▼  [FilterEngine.filter()] — Diversity 去重 + 数量/时长约束
list[ClipCandidate] (筛选后的候选)
    │
    ▼  [DurationPlanner.plan()] — 按目标时长组合
ClipPlan (最终的剪辑方案，含片段顺序和时长分配)
    │
    ▼  [LLMAnalyzer.final_review()] — 可选，最终精选
ClipPlan (LLM 重排序后的最终方案)
    │
    ▼  [Clipper.clips_from_report()] — ffmpeg 裁剪 + 拼接
输出视频文件
```

#### 4.4.4 Scene Detection 接口设计

```python
class SceneDetector(ABC):
    """场景检测器抽象基类 — 预留多种检测方案"""

    @abstractmethod
    def detect_scenes(
        self,
        segments: list[Segment],
        video_path: str | None = None,
    ) -> list[Scene]:
        ...

class WhisperSegmentDetector(SceneDetector):
    """基于 Whisper segment 逻辑分组（MVP 方案）

    分组规则：
    - 时间间隔 > threshold（默认 5 秒）→ 新 Scene
    - 纯文本分析，无需视频文件
    """
    ...

class OpenCVSceneDetector(SceneDetector):
    """基于 OpenCV 帧差异的场景检测（未来方案）

    需要视频文件输入，使用 cv2.scene.detect() 或自定义帧差异算法。
    """
    ...
```

---

## 五、CLI 命令设计 (typer)

```bash
# 转录视频 → 字幕
videoagent transcribe input.mkv --language zh --output-dir ./outputs

# 分析字幕 → 报告
videoagent analyze ./outputs/subtitles/input.json --output-dir ./outputs

# 从报告提取亮点片段（兼容旧版）
videoagent clip ./outputs/reports/input.json --merge --min-score 0.7

# 智能片段筛选（新版 Smart Clip Engine v2.0）
videoagent clip report.json --video input.mp4 --smart-clip \
    --transcript subtitles.json --mode comedy --clips 5
videoagent clip report.json --video input.mp4 --smart-clip \
    --transcript subtitles.json --preset douyin --duration 60s
videoagent clip report.json --video input.mp4 --smart-clip \
    --transcript subtitles.json --prompt "切情侣吵架片段"

# 一键全流程 (转录 + 分析)
videoagent pipeline input.mkv --language zh

# 一键全流程 + 传统剪辑
videoagent pipeline input.mkv --clip --min-score 0.7

# 一键全流程 + 智能剪辑 (Smart Clip Engine v2.0)
videoagent pipeline input.mkv --smart-clip --mode viral --preset douyin --clips 10
videoagent pipeline input.mkv --smart-clip --mode comedy --duration 180s

# 批量处理多个视频
videoagent batch "D:/videos/" --clip --min-score 0.7
videoagent batch "D:/videos/*.mp4" --clip --no-merge

# 查看帮助
videoagent --help
videoagent transcribe --help
```

---

## 六、LLM Prompt 设计

### System Prompt (核心分析)
```
你是一个视频内容分析专家。你的任务是分析视频字幕，
识别出最有价值的片段，并解释为什么这些片段值得保留。

输出必须是严格的 JSON 格式，包含 summary 和 highlights 两个字段。
每个 highlight 包含: segment_id, start, end, title, reason, score。
```

### Highlight Extract Prompt
```
基于以下视频字幕，请识别出最值得保留的精彩片段：

[字幕内容]

要求：
1. 选出 3-5 个最重要的片段
2. 每个片段给出标题和理由
3. 评分标准: 信息密度、观点新颖性、实用性
4. 输出 JSON 格式
```

---

## 七、配置设计 (config.yaml)

```yaml
whisper:
  model: "large-v3"
  device: "auto"            # auto / cuda / cpu
  fp16: true
  default_language: "zh"

llm:
  provider: "ollama"        # ollama / openai_compatible
  model: "qwen2.5-7b"
  endpoint: "http://localhost:11434"
  timeout: 120

output:
  default_dir: "./outputs"
  formats:
    - srt
    - json
    - markdown

ffmpeg:
  path: "ffmpeg"            # ffmpeg 可执行文件路径
```

---

## 八、依赖清单

```toml
[project]
dependencies = [
    "openai-whisper>=20231117",
    "torch>=2.0",
    "typer>=0.9",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "rich>=13.0",           # CLI 美化输出
    "ffmpeg-python>=0.2",   # 后期剪辑用
    "httpx>=0.27",          # Ollama API 调用
]

[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-asyncio"]
```

---

## 九、实施路线图

### Phase 1: 基础管线 ✅ 已完成
- [x] 项目脚手架 (pyproject.toml, 目录结构)
- [x] Whisper 转录模块封装
- [x] CLI 入口 (typer)
- [x] SRT + JSON + Markdown 导出

### Phase 2: LLM 分析 ✅ 已完成
- [x] llama.cpp/Qwen 接入 (OpenAI 兼容 API)
- [x] Prompt 工程
- [x] JSON 报告生成
- [x] Markdown 报告生成
- [x] 长上下文自动截断
- [x] JSON 多级容错解析

### Phase 3: 自动剪辑 ✅ 已完成
- [x] ffmpeg 剪辑模块 (`src/edit/clipper.py`)
- [x] 根据 JSON 自动裁剪 + 拼接
- [x] 交叉淡入淡出转场
- [x] concat 直拼模式
- [x] `clips_from_report()` 一键提取接口

### Phase 3.5: 全流程接口 + 批量处理 ✅ 已完成
- [x] `process_video()` 单视频全流程接口 (`src/pipeline.py`)
- [x] 独立资源管理（每次调用创建/释放实例）
- [x] 批量处理模块 (`src/batch/`)
- [x] 视频发现（文件/目录/glob）
- [x] CSV 汇总报告
- [x] CLI `batch` 命令

### Phase 4: 功能增强 (进行中)
- [ ] 并发控制 (`--workers N`)
- [ ] 剪辑后处理增强（字幕烧录、封面生成、元数据嵌入）
- [ ] Smart Clip Engine v2.0（智能片段筛选引擎）
  - [ ] Scene Detection（Whisper segment 分组 MVP）
  - [ ] 多维评分数据结构（Scene, ClipCandidate）
  - [ ] LLM Scene 标注（分段调用）
  - [ ] Score Engine（preset 权重计算）
  - [ ] Filter Engine（Diversity 去重）
  - [ ] Clip Mode + Clip Count（CLI 参数）
  - [ ] Duration Planner（目标时长组合）
  - [ ] Category Weight（平台预设）
  - [ ] 用户自定义 Prompt
  - [ ] LLM Final Review（二阶段筛选）

### Phase 5: Web 服务 (未来)
- [ ] FastAPI 服务化
- [ ] Web UI (NiceGUI → Tauri)
- [ ] 批量处理队列
- [ ] 任务进度实时推送

---

## 十、注意事项

1. **Whisper large-v3 模型较大** (~6GB)，首次加载需要时间，建议模型缓存
2. **Ollama 需要本地运行**，确保 `http://localhost:11434` 可达
3. **长视频处理**：考虑分段转录策略，避免 OOM
4. **中文支持**：Whisper large-v3 中文效果较好，但标点可能不完美
5. **输出目录**：按视频文件名 + 时间戳组织，避免覆盖