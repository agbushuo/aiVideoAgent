# 变更记录

## 2026-06-23

### 单视频全流程接口 + 批处理模块
- **新增** `src/pipeline.py`：`process_video()` 函数，封装 转录→分析→(可选)剪辑 完整管线
  - 每次调用独立创建和释放 Whisper/LLM/Clipper 实例
  - 返回 `VideoProcessResult` 数据结构（包含状态、输出路径、耗时等）
  - 所有配置参数可覆盖（whisper_*、llm_*、ffmpeg_*）
- **重写** `src/batch/__init__.py`：基于 `process_video()` 实现批处理
  - `discover_videos()` — 支持文件/目录递归/glob 模式发现视频
  - `run_batch()` — 串行调用 `process_video()`，生成 CSV 汇总报告
  - `BatchResult` — 批量处理结果聚合，包含 success_count/fail_count 等统计
- **更新** `src/main.py`：新增 `batch` CLI 命令
  - `videoagent batch <input>` — 支持文件/目录/glob 输入
  - `--clip` / `--min-score` / `--merge` / `--transition` 参数
- **更新** `ROADMAP.md`：
  - 版本升至 v0.2.0
  - "已完成" 增加全流程接口和批量处理模块
  - "批量处理模式" 标记为已完成，保留并发控制等待增强项
- **更新** `README.md`：
  - 新增批量处理使用说明（CLI + Python API）
  - 更新项目结构（增加 pipeline.py 和 batch/ 模块）
  - 剪辑功能状态从"开发中"改为已完成
- **更新** `ARCHITECTURE.md`：
  - 项目结构增加 pipeline.py、batch/、logs/ 目录
  - CLI 命令增加 clip 和 batch
  - 实施路线图更新 Phase 1-3.5 为已完成

### ffmpeg 剪辑模块实现
- **新增** `src/edit/clipper.py`：完整的 ffmpeg 剪辑引擎
  - `clips_from_report()` — 从报告 JSON 一键提取亮点片段（主入口）
  - `extract_segment()` — 单个片段裁剪
  - `clip_highlights()` — 批量裁剪独立片段
  - `merge_clips()` — 拼接精华视频（支持交叉淡入淡出转场 / concat 直拼）
  - 输出 MP4 (H.264 + AAC)，CRF 23 质量
- **新增** `ClipResult` / `ClipBatchResult` 数据类
- **更新** `src/edit/__init__.py`：导出新数据类
- **更新** `src/utils/io.py`：
  - 新增 `load_analysis_json()` — 从 JSON 加载分析报告
  - `export_analysis_json()` 增加 `video_path` 持久化
- **更新** `src/main.py`：
  - 新增 `clip` 子命令（`--video`, `--merge/--no-merge`, `--transition`, `--min-score`）
  - `pipeline` 命令增加 `--clip` 和 `--min-score` 参数
  - `analyze` 命令增加 `--video` 参数（记录源视频路径到报告）

### 项目规划文档
- **新增** `ROADMAP.md`：完整实施路线图
  - 近期目标：批量处理、剪辑后处理、长视频分段转录
  - 中期目标：智能片段筛选、多语言混合支持
  - 远期目标：FastAPI 服务化、可视化界面（NiceGUI → Tauri）
  - Viral Engine v2.0 规划：注意力扫描、故事模板、Viral Score、渲染增强
