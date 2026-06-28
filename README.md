# VideoAgent

视频自动化处理 Agent：**视频 → 字幕 → 总结 → 亮点分析 → 自动剪辑**

提供 CLI 命令行和 Web 控制台两种使用方式。

## 功能

- **Whisper 转录**: 使用 `large-v3` 模型生成高精度带时间戳字幕，支持长视频分段转录（>30min 自动启用）
- **LLM 分析**: 通过 LLM（Qwen/Claude/OpenAI 兼容）分析视频内容，识别亮点片段
- **Smart Clip Engine v2.0**: 四层智能剪辑架构 — Scene Detection → LLM 标注 → 多维评分/筛选 → ffmpeg 剪辑
- **多格式输出**: SRT 字幕 + JSON 结构化报告 + Markdown 可读报告
- **自动剪辑**: 根据分析结果自动裁剪亮点片段并拼接精华视频（交叉淡入淡出转场）
- **批量处理**: 串行处理多个视频，支持目录递归和 glob 模式，生成 CSV 汇总报告
- **Web 控制台**: Next.js + React Flow 前端，支持 DAG 管线编排、场景编辑、实时日志
- **国际化**: 前后端完整中英双语支持

## 快速开始

### 环境准备

```bash
# 激活 conda 环境
conda activate ai-video

# 安装依赖
pip install -e .
```

### Web 控制台（推荐）

```bash
# 启动 Web 服务（前端 3000 端口，后端 8501 端口）
videoagent serve

# 浏览器访问 http://localhost:3000
```

Web 控制台功能：
- **Dashboard** — 任务概览、快速创建任务
- **Workflow 编排** — React Flow DAG 画布，可视化配置 8 个管线阶段
- **场景浏览器** — AI 分析结果表格，支持筛选、搜索、行内编辑
- **预设管理** — 创建/编辑/删除预设，自定义评分权重和 Prompt 模板
- **设置页面** — 模型配置（本地/在线 LLM 切换）、外观主题
- **实时日志** — SSE 推送，CI/CD 风格执行日志

### CLI 命令行

```bash
# 一键全流程: 转录 + 分析 + 剪辑
videoagent pipeline input.mp4 --clip

# 仅转录 + 分析（不剪辑）
videoagent pipeline input.mp4

# 仅转录
videoagent transcribe input.mp4

# 仅分析 (需要已有字幕 JSON)
videoagent analyze outputs/subtitles/video.json

# 仅剪辑 (需要已有报告 JSON)
videoagent clip outputs/reports/video.json
```

### Smart Clip Engine v2.0

```bash
# 智能剪辑: 按模式 + 平台预设
videoagent pipeline input.mp4 --smart-clip --mode comedy --preset douyin --clips 5

# 按目标时长
videoagent pipeline input.mp4 --smart-clip --duration 180s --duration-planner

# 启用 LLM 最终评审
videoagent pipeline input.mp4 --smart-clip --final-review --clips 3
```

### 批量处理

```bash
# 批量处理目录下所有视频
videoagent batch "D:/videos/"

# 批量处理 + 自动剪辑
videoagent batch "D:/videos/" --clip

# glob 模式 + 评分过滤
videoagent batch "D:/videos/*.mp4" --clip --min-score 0.7
```

### Python API

```python
from src.pipeline import process_video
from src.batch import run_batch

# 处理单个视频
result = process_video("input.mp4", clip=True, min_score=0.7)
print(f"亮点数: {result.highlight_count}")
print(f"精华视频: {result.merged_clip_path}")

# 批量处理
result = run_batch("D:/videos/*.mp4", clip=True)
print(f"成功: {result.success_count}/{len(result.items)}")
```

## 项目结构

```
aiVideoAgent/
├── pyproject.toml          # 项目配置
├── config.yaml             # 应用配置（Whisper/LLM/ffmpeg）
├── frontend/               # Next.js Web 前端
│   ├── src/
│   │   ├── app/            # 页面（Dashboard, 任务列表, 预设, 设置）
│   │   ├── components/     # 组件（Workflow, 场景, 控制台, 预设编辑器）
│   │   ├── stores/         # Zustand 状态管理
│   │   ├── lib/            # API 客户端
│   │   └── types/          # TypeScript 类型定义
│   └── messages/           # i18n 翻译文件（zh.json, en.json）
├── src/
│   ├── main.py             # CLI 入口（typer）
│   ├── pipeline.py         # 单视频全流程接口
│   ├── transcribe/         # Whisper 转录模块
│   ├── analyze/            # LLM 分析模块
│   ├── clip_engine/        # 智能片段筛选引擎 v2.0
│   ├── edit/               # ffmpeg 剪辑模块
│   ├── batch/              # 批量处理模块
│   ├── web/                # FastAPI Web 后端
│   │   ├── app.py              # 34+ REST 端点
│   │   ├── task_manager.py     # 任务生命周期管理
│   │   ├── pipeline_runner.py  # 管线执行器
│   │   ├── preset_manager.py   # 预设管理
│   │   ├── settings_manager.py # 用户设置管理
│   │   ├── sse.py              # SSE 事件流
│   │   └── stage_executor.py   # 阶段执行器
│   └── utils/              # 工具函数（i18n, 音频预处理）
├── prompts/                # LLM Prompt 模板
├── data/                   # 持久化数据（tasks.json, presets.json, settings.json）
├── logs/                   # 变更记录
└── outputs/                # 输出目录
```

## 配置

编辑 `config.yaml` 或通过 Web 设置页面修改：
- Whisper 模型路径、分段转录参数
- LLM API 端点（支持 OpenAI/Anthropic/本地模型）
- ffmpeg 路径
- 输出格式

## 技术栈

**后端:**
- Python 3.10+ / FastAPI / uvicorn
- openai-whisper (large-v3)
- typer (CLI) / pydantic (数据验证)
- ffmpeg (视频剪辑)

**前端:**
- Next.js 16 (App Router) / TypeScript / TailwindCSS
- Zustand (状态管理) / React Flow (DAG 画布)
- next-intl (国际化) / TanStack Table (场景表格)
- lucide-react (图标)
