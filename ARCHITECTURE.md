# VideoAgent 项目架构规划

> 创建日期: 2026-06-22  
> 状态: 规划阶段

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
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI 入口 (typer)
│   │
│   ├── transcribe/
│   │   ├── __init__.py
│   │   └── whisper_engine.py   # Whisper 封装
│   │                           #   - load_model()
│   │                           #   - transcribe_video() → TranscriptResult
│   │                           #   - export_srt()
│   │
│   ├── analyze/
│   │   ├── __init__.py
│   │   └── llm_analyzer.py     # LLM 分析引擎
│   │                           #   - summarize() → 视频总结
│   │                           #   - extract_highlights() → 亮点片段列表
│   │                           #   - build_report() → Markdown 报告
│   │
│   ├── edit/
│   │   ├── __init__.py
│   │   └── clipper.py          # (TODO) 视频剪辑模块
│   │                           #   - clip_segments() → 根据 JSON 剪辑
│   │
│   └── utils/
│       ├── __init__.py
│       ├── video_info.py       # 视频元信息 (时长、分辨率、编码)
│       ├── io.py               # 文件 I/O (SRT 读写、JSON 序列化)
│       └── prompts.py          # LLM prompt 管理
│
├── prompts/
│   ├── system.md               # LLM system prompt
│   └── highlight_extract.md    # 亮点提取 prompt 模板
│
├── outputs/                    # 输出目录 (gitignore)
│   ├── subtitles/              # SRT 文件
│   ├── reports/                # JSON + Markdown 报告
│   └── clips/                  # (未来) 剪辑后的视频
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

---

## 五、CLI 命令设计 (typer)

```bash
# 转录视频 → 字幕
videoagent transcribe input.mkv --language zh --output-dir ./outputs

# 分析字幕 → 报告
videoagent analyze ./outputs/subtitles/input.json --output-dir ./outputs

# 一键全流程
videoagent pipeline input.mkv --language zh --output-dir ./outputs

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

### Phase 1: 基础管线 (当前)
- [ ] 项目脚手架 (pyproject.toml, 目录结构)
- [ ] Whisper 转录模块封装
- [ ] CLI 入口 (typer)
- [ ] SRT 导出

### Phase 2: LLM 分析
- [ ] Ollama/Qwen 接入
- [ ] Prompt 工程
- [ ] JSON 报告生成
- [ ] Markdown 报告生成

### Phase 3: 自动剪辑 (未来)
- [ ] ffmpeg 剪辑模块
- [ ] 根据 JSON 自动裁剪 + 拼接
- [ ] 转场效果

### Phase 4: Web 服务 (未来)
- [ ] FastAPI 服务化
- [ ] Web UI
- [ ] 批量处理队列

---

## 十、注意事项

1. **Whisper large-v3 模型较大** (~6GB)，首次加载需要时间，建议模型缓存
2. **Ollama 需要本地运行**，确保 `http://localhost:11434` 可达
3. **长视频处理**：考虑分段转录策略，避免 OOM
4. **中文支持**：Whisper large-v3 中文效果较好，但标点可能不完美
5. **输出目录**：按视频文件名 + 时间戳组织，避免覆盖
