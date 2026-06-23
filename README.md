# VideoAgent

视频自动化处理 Agent：**视频 → 字幕 → 总结 → 亮点分析 → 自动剪辑**

## 功能

- **Whisper 转录**: 使用 `large-v3` 模型生成高精度带时间戳字幕
- **LLM 分析**: 通过 llama.cpp (Qwen) 分析视频内容，识别亮点片段
- **多格式输出**: SRT 字幕 + JSON 结构化报告 + Markdown 可读报告
- **自动剪辑**: (开发中) 根据分析结果自动剪辑精华片段

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

### 使用

```bash
# 一键全流程
videoagent pipeline input_video.mkv --language zh

# 仅转录
videoagent transcribe input_video.mkv --language zh

# 仅分析 (需要已有字幕 JSON)
videoagent analyze outputs/subtitles/video.json

# 查看帮助
videoagent --help
```

## 项目结构

```
aiVideoAgent/
├── pyproject.toml          # 项目配置
├── config.yaml             # 应用配置
├── src/
│   ├── main.py             # CLI 入口
│   ├── transcribe/         # Whisper 转录模块
│   ├── analyze/            # LLM 分析模块
│   ├── edit/               # 视频剪辑模块
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
