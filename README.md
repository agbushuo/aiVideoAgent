# VideoAgent

视频自动化处理 Agent：**视频 → 字幕 → 总结 → 亮点分析 → 自动剪辑**

## 功能

- **Whisper 转录**: 使用 `large-v3` 模型生成高精度带时间戳字幕
- **LLM 分析**: 通过 llama.cpp (Qwen) 分析视频内容，识别亮点片段
- **多格式输出**: SRT 字幕 + JSON 结构化报告 + Markdown 可读报告
- **自动剪辑**: 根据分析结果自动裁剪亮点片段并拼接精华视频（交叉淡入淡出转场）
- **批量处理**: 串行处理多个视频，支持目录递归和 glob 模式，生成 CSV 汇总报告

## 快速开始

### 环境准备

```bash
# 激活 conda 环境
conda activate ai-video

# 安装依赖
pip install -e .

# 确保 llama.cpp 服务正在运行
# llama-server -m your_model.gguf --port 8080
```

### 单视频处理

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

### 批量处理

```bash
# 批量处理目录下所有视频
videoagent batch "D:/videos/"

# 批量处理 + 自动剪辑
videoagent batch "D:/videos/" --clip

# glob 模式 + 评分过滤
videoagent batch "D:/videos/*.mp4" --clip --min-score 0.7

# 不拼接精华视频（只输出独立片段）
videoagent batch "D:/videos/" --clip --no-merge
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
print(f"汇总 CSV: {result.summary_csv_path}")
```

## 项目结构

```
aiVideoAgent/
├── pyproject.toml          # 项目配置
├── config.yaml             # 应用配置
├── src/
│   ├── main.py             # CLI 入口
│   ├── pipeline.py         # 单视频全流程接口 (process_video)
│   ├── transcribe/         # Whisper 转录模块
│   ├── analyze/            # LLM 分析模块
│   ├── edit/               # 视频剪辑模块
│   ├── batch/              # 批量处理模块
│   └── utils/              # 工具函数
├── prompts/                # LLM Prompt 模板
└── outputs/                # 输出目录
```

## 配置

编辑 `config.yaml` 修改：
- Whisper 模型路径
- LLM API 端点
- ffmpeg 路径
- 输出格式

## 技术栈

- Python 3.10+
- openai-whisper (large-v3)
- llama.cpp (Qwen3.6 27B)
- typer (CLI)
- ffmpeg
