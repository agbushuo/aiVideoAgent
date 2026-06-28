# VideoAgent 项目架构

> 创建日期: 2026-06-22
> 最后更新: 2026-06-28
> 状态: Web 控制台 + CLI 双模式已完成

---

## 一、项目目标

构建一个**视频自动化处理 Agent**，提供 CLI 和 Web 两种使用方式：

```
视频文件
  ↓
[Stage 1] Whisper large-v3 → 带时间戳字幕（长视频自动分段）
  ↓
[Stage 2] Scene Detection → 场景分组
  ↓
[Stage 3] LLM 标注 → 场景类型 + 标签 + 多维评分
  ↓
[Stage 4] Score Engine → 综合分计算
  ↓
[Stage 5] Filter Engine → Diversity 去重 + 约束筛选
  ↓
[Stage 6] Duration Planner → 按目标时长组合（可选）
  ↓
[Stage 7] LLM Final Review → 最终精选（可选）
  ↓
[Stage 8] ffmpeg 剪辑 → 独立片段 + 精华视频
```

---

## 二、技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | 生态丰富、Whisper 原生支持 |
| 字幕引擎 | `openai-whisper large-v3` | 中文效果好、支持长视频分段 |
| LLM | Qwen3.6 27B / Claude / OpenAI | 本地或在线、API 兼容 |
| CLI 框架 | `typer` | 现代、自动生成帮助、子命令支持 |
| Web 后端 | `FastAPI` + `uvicorn` | 异步、自动文档、SSE 支持 |
| Web 前端 | Next.js 16 + TypeScript | App Router、SSR、i18n |
| 状态管理 | Zustand | 轻量、无 boilerplate |
| 可视化 | React Flow (DAG) | 管线编排 |
| 国际化 | next-intl (前端) / 字典 (后端) | 中英双语 |
| 视频处理 | `ffmpeg-python` | 剪辑、转码 |
| 配置管理 | YAML + JSON | config.yaml + settings.json |

---

## 三、项目结构

```
aiVideoAgent/
├── pyproject.toml              # 项目元数据 + 依赖
├── config.yaml                 # 配置 (Whisper/LLM/ffmpeg)
├── README.md
├── ROADMAP.md                  # 实施路线图
├── ARCHITECTURE.md             # 本文档
│
├── frontend/                   # Next.js Web 前端
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx          # 根布局（ClientProvider）
│   │   │   ├── page.tsx            # Dashboard 主页
│   │   │   ├── tasks/page.tsx      # 任务列表页
│   │   │   ├── tasks/[id]/page.tsx # 任务详情页
│   │   │   ├── presets/page.tsx    # 预设管理页
│   │   │   └── settings/page.tsx   # 设置页
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Layout.tsx          # 全局布局（SSE 连接）
│   │   │   │   ├── TopBar.tsx          # 顶部栏（运行/停止/语言切换）
│   │   │   │   ├── Sidebar.tsx         # 侧边栏导航
│   │   │   │   └── MainCanvas.tsx      # 主画布（Workflow/场景切换）
│   │   │   ├── workflow/
│   │   │   │   ├── WorkflowBuilder.tsx     # 管线编排根组件
│   │   │   │   ├── ReactFlowCanvas.tsx     # DAG 画布
│   │   │   │   ├── PipelineNode.tsx        # 自定义节点
│   │   │   │   ├── ConfigPanel.tsx         # schema 驱动参数面板
│   │   │   │   └── StageFormField.tsx      # 表单字段组件
│   │   │   ├── scenes/
│   │   │   │   ├── SceneExplorer.tsx    # 场景浏览主组件
│   │   │   │   ├── SceneTable.tsx       # TanStack Table 表格
│   │   │   │   ├── SceneFiltersBar.tsx  # 筛选工具栏
│   │   │   │   ├── SceneEditModal.tsx   # 场景编辑弹窗
│   │   │   │   └── EmptyState.tsx       # 空状态
│   │   │   ├── console/
│   │   │   │   ├── RunConsole.tsx         # 控制台主组件
│   │   │   │   ├── StageStatusPanel.tsx   # 阶段状态面板
│   │   │   │   └── LogPanel.tsx           # 实时日志面板
│   │   │   ├── presets/
│   │   │   │   ├── PresetList.tsx     # 预设列表
│   │   │   │   ├── PresetEditor.tsx   # 预设编辑器
│   │   │   │   └── PromptEditor.tsx   # Prompt 编辑器
│   │   │   ├── FileBrowser.tsx        # 文件浏览器模态框
│   │   │   ├── StatusBadge.tsx        # 状态徽章
│   │   │   └── ProgressBar.tsx        # 进度条
│   │   ├── stores/
│   │   │   ├── taskStore.ts      # 任务状态 + SSE
│   │   │   ├── sceneStore.ts     # 场景状态
│   │   │   ├── workflowStore.ts  # Workflow DAG 状态
│   │   │   └── configStore.ts    # 配置引用数据
│   │   ├── lib/
│   │   │   ├── api.ts          # API 客户端（含 localStorage 回退）
│   │   │   └── sceneUtils.ts   # 场景工具函数
│   │   └── types/
│   │       ├── api.ts           # API 类型
│   │       ├── config.ts        # 配置/预设类型
│   │       ├── workflow.ts      # Workflow schema
│   │       ├── scene.ts         # 场景类型
│   │       ├── transcript.ts    # 字幕类型
│   │       └── sse.ts           # SSE 事件类型
│   ├── messages/
│   │   ├── zh.json              # 中文翻译
│   │   └── en.json              # 英文翻译
│   └── i18n/
│       ├── request.ts           # next-intl 请求配置
│       └── ClientProvider.tsx   # 客户端 Provider
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI 入口 (typer)
│   ├── pipeline.py             # 单视频全流程接口 (process_video)
│   │
│   ├── transcribe/
│   │   ├── __init__.py
│   │   ├── whisper_engine.py   # Whisper 封装（含分段转录）
│   │   ├── models.py           # Segment, TranscriptResult
│   │   └── merger.py           # 分段转录去重合并
│   │
│   ├── analyze/
│   │   ├── __init__.py
│   │   └── llm_analyzer.py     # LLM 分析引擎
│   │                           #   - analyze() → AnalysisReport
│   │                           #   - analyze_scenes() → list[Scene]
│   │
│   ├── clip_engine/            # 智能片段筛选引擎 v2.0
│   │   ├── __init__.py
│   │   ├── models.py           # Scene, ClipCandidate, ClipResult
│   │   ├── scene_detector.py   # Scene Detection
│   │   ├── scorer.py           # Score Engine（多维评分 + preset 权重）
│   │   ├── filter.py           # Filter Engine（Diversity 去重）
│   │   ├── planner.py          # Duration Planner（目标时长组合）
│   │   └── reviewer.py         # Final Reviewer（LLM 二阶段筛选）
│   │
│   ├── edit/
│   │   ├── __init__.py
│   │   └── clipper.py          # ffmpeg 剪辑模块
│   │                           #   - clips_from_report()
│   │                           #   - extract_segment()
│   │                           #   - merge_clips()
│   │
│   ├── batch/
│   │   └── __init__.py         # 批量处理模块
│   │                           #   - discover_videos()
│   │                           #   - run_batch()
│   │
│   ├── web/                    # FastAPI Web 后端
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI 应用 + 34+ REST 端点
│   │   ├── api_schemas.py      # Pydantic 请求/响应模型
│   │   ├── task_manager.py     # 任务生命周期 + 持久化
│   │   ├── pipeline_runner.py  # 管线执行器（8 阶段）
│   │   ├── stage_executor.py   # 阶段执行器
│   │   ├── sse.py              # SSE 事件流系统
│   │   ├── preset_manager.py   # 预设管理（data/presets.json）
│   │   └── settings_manager.py # 用户设置管理（data/settings.json）
│   │
│   └── utils/
│       ├── __init__.py
│       ├── i18n.py             # 后端国际化（zh/en 字典）
│       ├── video_info.py       # 视频元信息
│       ├── audio_preprocess.py # 音频预处理（分段转录）
│       └── io.py               # 文件 I/O
│
├── prompts/
│   ├── system.md               # LLM system prompt
│   ├── highlight_extract.md    # 亮点提取 prompt（兼容旧版）
│   ├── scene_analysis.md       # Scene 标注 prompt
│   └── final_review.md         # Final Review prompt
│
├── data/                       # 持久化数据
│   ├── tasks.json              # 任务状态（后端重启不丢失）
│   ├── presets.json            # 预设配置
│   └── settings.json           # 用户设置（LLM 配置、外观）
│
├── logs/
│   └── CHANGELOG.md            # 变更记录
│
└── outputs/                    # 输出目录 (gitignore)
    ├── {video_stem}/
    │   ├── subtitles/          # SRT + JSON 字幕
    │   ├── reports/            # JSON + Markdown 报告
    │   └── artifacts/          # scenes_annotated.json, candidates.json
```

---

## 四、核心数据流

### 4.1 转录阶段

```
视频文件 → WhisperEngine.transcribe() → TranscriptResult
                                    ↓
                    （>30min 自动分段 → chunk → 去重合并）
```

```python
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
    duration: float     # 总时长
```

### 4.2 Smart Clip Engine 数据流

```
TranscriptResult (Whisper segments)
    │
    ▼  SceneDetector.detect_scenes()
list[Scene] (场景列表)
    │
    ▼  LLMAnalyzer.analyze_scenes() — 分批标注
list[Scene] (含 scene_type, tags, multi_score, summary)
    │
    ▼  ScoreEngine.compute() — preset 权重计算综合分
list[ClipCandidate] (含 composite_score)
    │
    ▼  ClipFilter.filter() — Diversity 去重 + 约束
list[ClipCandidate] (筛选后的候选)
    │
    ▼  DurationPlanner.plan() — 按目标时长组合（可选）
ClipPlan (最终剪辑方案)
    │
    ▼  FinalReviewer.review() — LLM 最终精选（可选）
list[ClipCandidate] (精选后)
    │
    ▼  Clipper.extract_segment() + merge_clips()
输出视频文件
```

### 4.3 Web 后端数据流

```
浏览器 → Next.js rewrites → FastAPI (:8501)

用户操作
    │
    ▼
POST /api/tasks          → 创建 PipelineTask，保存到 data/tasks.json
    │
    ▼
pipeline_runner.run_pipeline()
    │
    ├── Stage 1: transcribe     → WhisperEngine
    ├── Stage 2: scene_detection → WhisperSegmentDetector
    ├── Stage 3: scene_annotation → LLMAnalyzer.analyze_scenes()
    ├── Stage 4: scoring        → ScoreEngine
    ├── Stage 5: filtering      → ClipFilter
    ├── Stage 6: planning       → DurationPlanner（可选）
    ├── Stage 7: review         → FinalReviewer（可选）
    └── Stage 8: clipping       → Clipper
    │
    ▼
SSE broadcast → 浏览器实时更新（日志、进度、状态）
    │
    ▼
data/tasks.json 持久化（关键节点自动保存）
```

### 4.4 设置优先级

```
config.yaml (默认值)
    └── 被 data/settings.json 覆盖（用户 Web 设置）
            └── 保存时同步写回 config.yaml llm 段
            └── 浏览器 localStorage 缓存（离线回退）

优先级: 用户设置 > config.yaml 默认值
```

---

## 五、CLI 命令

```bash
# 转录
videoagent transcribe input.mkv --language zh

# 分析
videoagent analyze outputs/subtitles/input.json --video input.mp4

# 传统剪辑
videoagent clip outputs/reports/input.json --merge --min-score 0.7

# Smart Clip v2.0
videoagent clip report.json -v input.mp4 --smart-clip \
    --transcript subtitles.json --mode comedy --clips 5 --preset douyin

# 全流程
videoagent pipeline input.mp4 --smart-clip --mode viral --preset douyin

# 批量处理
videoagent batch "D:/videos/" --clip

# Web 服务
videoagent serve --host 0.0.0.0 --port 8501

# 版本
videoagent version
```

---

## 六、Web API 端点

### 任务管理
- `GET /api/tasks` — 任务列表
- `POST /api/tasks` — 创建任务
- `GET /api/tasks/{id}` — 任务详情
- `DELETE /api/tasks/{id}` — 删除任务
- `DELETE /api/tasks/bulk-delete` — 批量删除
- `POST /api/tasks/{id}/resume` — 恢复任务
- `POST /api/tasks/{id}/cancel` — 取消任务
- `POST /api/tasks/{id}/rerun-stage` — 重跑阶段

### 阶段执行
- `GET /api/tasks/{id}/stages` — 阶段列表
- `GET /api/tasks/{id}/stages/{stage}` — 阶段详情
- `POST /api/tasks/{id}/stages/{stage}/run` — 执行阶段

### 场景 / 候选
- `GET /api/tasks/{id}/scenes` — 场景列表（tag/score/search 筛选）
- `GET /api/tasks/{id}/scenes/{id}` — 单个场景
- `PUT /api/tasks/{id}/scenes/{id}` — 修改场景
- `GET /api/tasks/{id}/candidates` — 候选列表
- `PATCH /api/tasks/{id}/candidates/bulk-select` — 批量选中

### 字幕
- `GET /api/tasks/{id}/transcript` — 获取字幕
- `PUT /api/tasks/{id}/transcript` — 保存修改
- `PUT /api/tasks/{id}/transcript/segments/{idx}` — 更新片段

### 配置参考
- `GET /api/config/presets` — 预设权重
- `GET /api/config/clip-modes` — 剪辑模式
- `GET /api/config/scene-types` — 场景类型
- `GET /api/config/score-dimensions` — 评分维度
- `GET /api/config/pipeline-stages` — DAG 定义
- `GET /api/config/weights` — 完整权重
- `GET /api/config/duration-templates` — 时长模板

### 预设管理
- `GET /api/presets` — 预设列表
- `GET /api/presets/{name}` — 预设详情
- `PUT /api/presets/{name}` — 保存预设
- `DELETE /api/presets/{name}` — 删除预设
- `POST /api/presets/{name}/duplicate` — 复制预设

### Prompt 管理
- `GET /api/prompts` — Prompt 列表
- `GET /api/prompts/{name}` — Prompt 内容
- `PUT /api/prompts/{name}` — 保存 Prompt

### 用户设置
- `GET /api/settings` — 获取设置
- `PUT /api/settings` — 保存设置（同步 config.yaml）

### 文件系统
- `GET /api/fs/drives` — 列出驱动器
- `GET /api/fs/list?path=...` — 列出目录

### 文件操作
- `GET /api/files/{path}` — 下载文件
- `GET /api/files/{path}/thumbnail` — 生成缩略图

### 实时推送
- `GET /api/events` — SSE 全局事件流
- `GET /api/tasks/{id}/events` — 特定任务 SSE 流

---

## 七、依赖清单

```toml
[project]
dependencies = [
    "openai-whisper>=20231117",
    "torch>=2.0",
    "typer>=0.9",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "rich>=13.0",
    "ffmpeg-python>=0.2",
    "httpx>=0.27",
    "fastapi>=0.104",
    "uvicorn>=0.24",
]
```

---

## 八、注意事项

1. **Whisper large-v3 模型较大** (~6GB)，首次加载需要时间
2. **LLM 支持本地和在线**：通过 Web 设置页面切换，配置自动同步
3. **长视频处理**：>30min 自动分段转录，10 分钟 chunk + 10 秒重叠
4. **中文支持**：Whisper large-v3 中文效果好，前后端完整 i18n
5. **任务持久化**：`data/tasks.json` 自动保存，后端重启不丢失
6. **输出目录**：按 `outputs/{video_stem}/` 组织，避免覆盖
