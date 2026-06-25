# 变更记录

## 2026-06-25

### Smart Clip Engine v2.0 架构规划 + ROADMAP 结构调整（文档更新）
- **更新** `ROADMAP.md`：
  - 将"3. 长视频分段转录策略"标记为 ✅ 已完成（完成日期 2026-06-24）
  - 所有子步骤（3.1-3.5）标记为已完成，实施顺序表增加"状态"列
  - 新增真实验证记录（140 分钟电影全流程测试数据）
  - "已完成"汇总新增分段转录策略条目（含音频预处理、overlap 去重、参数优化等细节）
  - 将"4. 智能片段筛选"升级为完整的 Smart Clip Engine v2.0 规划
    - 新增四层架构：AI 内容理解 → 规则引擎 → 策略引擎 → 最终优化
    - 新增十个功能模块详细设计
    - 新增 CLI 命令设计、数据结构、preset 权重、实施顺序
- **更新** `ARCHITECTURE.md`：
  - 新增十个功能模块详细设计：Scene Detection、Clip Mode、Clip Count、Duration Planner、Dynamic Clip、Scene Type、Quality Score、Auto Diversity、Category Weight、二阶段筛选
  - 新增 CLI 命令设计（`--mode`, `--preset`, `--clips`, `--duration`, `--prompt`）
  - 新增实施顺序表（11 个步骤，MVP 优先 4.1-4.6）
  - 新增数据结构设计（Scene, ClipCandidate 模型）
  - 新增 preset 权重配置表（douyin/youtube/bilibili）
  - 新增 Scene Detection 接口设计（抽象基类 + Whisper segment MVP + OpenCV 预留）
- **更新** `ARCHITECTURE.md`：
  - 项目结构新增 `src/clip_engine/` 模块（models.py, scene_detector.py, scorer.py, filter.py, planner.py）
  - 核心数据流新增 4.4 节（Scene 模型、ClipCandidate 模型、完整数据流图、Scene Detection 接口设计）
  - CLI 命令设计新增智能片段筛选参数
  - 实施路线图 Phase 4 细化 Smart Clip Engine v2.0 的子任务清单
- **设计决策**：
  - Scene Detection MVP 完全依赖 Whisper segment 逻辑分组，不依赖视频文件
  - 保留 `SceneDetector` 抽象基类接口，后续可切换 OpenCV 帧差异方案
  - preset 权重配置支持 JSON 文件扩展，用户可自定义平台权重
  - LLM 调用复用分段转录策略，长视频分批处理，避免上下文截断
  - 优先实现规则引擎（4.4/4.5）和策略引擎（4.6），成本最低、效果最明显

### 修复分段转录时方言场景语言检测不一致
- **修复** `src/transcribe/whisper_engine.py`：`_transcribe_segmented()` 中第一个 chunk 检测到的语言复用给后续所有 chunk，避免方言场景下各 chunk 被误判为不同语言（如 Russian/Dutch）
### 修复语言强制导致英文视频转录乱码问题
- **修复** `src/transcribe/whisper_engine.py`：`transcribe()` / `_transcribe_direct()` / `_transcribe_segmented()` 的 `language` 参数默认值从 `"zh"` 改为 `None`（Whisper 自动检测）
- **修复** `src/main.py`：`transcribe` / `pipeline` / `batch` CLI 命令的 `--language` 默认值从 `"zh"` 改为 `None`，显示时 `None` 显示为 `auto`
- **修复** `src/pipeline.py`：`process_video()` 的 `language` 默认值从 `"zh"` 改为 `None`
- **修复** `src/transcribe/whisper_engine.py`：分段转录时从第一个 chunk 的 Whisper 结果获取检测到的语言，传递给合并函数
- **新增** `src/transcribe/merger.py`：`_merge_consecutive_identical()` — 合并连续相同文本的 segment，消除 Whisper 对纯音乐/音效片段的重复输出
- **修复** `src/transcribe/merger.py`：`build_transcript_result()` / `merge_chunk_transcripts()` 的 `language` 默认值从 `"zh"` 改为 `None`
- **根因**：电影视频（宇宙巨人、星球大战）的音频为英文，强制 `language="zh"` 导致 Whisper 用中文模式转录英文音频，输出全为乱码。中文视频（沧浪之水）不受影响是因为语言匹配。
- **验证**：星球大战（132min 英文电影）测试，Whisper 正确检测为英文，LLM 提取 5 个亮点
- **发现**：107-118 分钟处有 11 分钟纯音乐/音效片段，Whisper 持续输出重复文本。这是 Whisper 本身的固有行为（非代码 bug），`_merge_consecutive_identical()` 优化后大幅减少重复 segment 数量

## 2026-06-24

### 分段转录策略真实视频测试，修复 chunk_audio ffprobe 路径 bug
- **修复** `src/utils/audio_preprocess.py`：`chunk_audio()` 新增 `ffprobe_path` 参数，内部 `get_audio_duration()` 使用正确的 ffprobe 而非 ffmpeg
- **修复** `src/transcribe/whisper_engine.py`：调用 `chunk_audio()` 时传递 `ffprobe_path`
- **修复** `config.yaml`：LLM timeout 从 300s 增至 1800s（140 分钟电影转录文本太大，原超时不够）
- **验证** 88 个单元测试全部通过
- **验证** 140 分钟电影全流程测试成功：
  - 转录：Whisper large-v3 分段转录 10 chunks，合并后 7668 segments，时间排序正确，无负时长
  - 分析：LLM 提取 4 个亮点（评分 0.8-0.95）
  - 剪辑：4 个独立片段 + 精华视频（110MB，6.8 分钟）
- **发现** Bash glob 展开问题：`videoagent batch 'E:/video/*.mp4'` 在 Git Bash 中会被 shell 提前展开为多个参数，导致 typer 报错。需通过 Python 脚本或 `discover_videos()` 直接调用。
- **验证** 批量操作全流程测试（两部电影串行处理）：
  - 电影1《宇宙巨人：希曼崛起》（140min）：转录10 chunks共7171 segments（1503.6s），LLM提取6个亮点（261.8s），剪辑6个片段+精华视频（3.1MB），总耗时1778.4s
  - 电影2《星球大战：曼达洛人与古古》（132min）：转录9 chunks共4393 segments（1272.4s，去重1条），LLM分析返回空JSON触发正则回退（0个亮点），总耗时1717.2s
  - 合并去重功能正常运作，时间戳排序正确
  - 批处理CSV汇总报告生成正常
  - **发现** 电影2的LLM分析超时问题：4393段转录文本过大，LLM在超时前返回空JSON。可能需要进一步优化prompt或分段分析策略

### 长视频分段转录策略（Segment-aware）功能实现 3.1-3.3
- **新增** `src/utils/audio_preprocess.py`：音频预处理模块
  - `extract_audio()` — FFmpeg 提取 16kHz mono WAV
  - `loudness_normalize()` — 响度归一化（EBU R128，两遍编码）
  - `get_audio_duration()` — ffprobe 获取音频时长
  - `chunk_audio()` — 按固定时长切分音频，支持 overlap
  - `should_segment_transcribe()` — 根据 GPU 显存 + 视频时长自动判断是否分段
    - GPU < 8GB：阈值 20 分钟；GPU 8-16GB：阈值 60 分钟；默认 30 分钟
    - 极短视频（< 5 分钟）永远不分段
  - `preprocess_audio_for_transcribe()` — 一站式预处理流水线
  - `AudioChunk` / `AudioPreprocessResult` 数据类
- **新增** `src/transcribe/merger.py`：Segment 级去重合并器
  - `apply_time_offset()` — 给 chunk segment 加全局时间戳偏移
  - `compute_text_similarity()` — 前 N 字符 + Levenshtein 混合相似度计算
    - 快速路径：前 20 字符比较，完全不同则直接返回低分
    - 精确路径：python-Levenshtein（有则用）或内置 DP 回退
  - `merge_segments()` — 多 chunk segment 合并去重
    - 时间重叠 + 文本相似度 > 阈值 → 保留范围更广的整段
    - 相似度 < 阈值 → 都保留（不同内容恰好重叠）
  - `build_transcript_result()` — 构建最终 TranscriptResult
  - `merge_chunk_transcripts()` — 一站式合并接口
  - `ChunkTranscript` / `MergeStats` 数据类
- **更新** `src/transcribe/whisper_engine.py`：集成分段转录
  - `WhisperEngine.__init__()` 新增分段配置参数（chunk_duration, overlap, threshold, similarity, loudness, beam_size, temperature_fallback, ffmpeg_path, ffprobe_path）
  - `transcribe()` 自动检测音频时长，超过阈值时切换分段模式
  - `_transcribe_direct()` — 原有直接转录逻辑（短视频）
  - `_transcribe_segmented()` — 分段转录流程：预处理 → 切分 → 逐 chunk 转录 → 去重合并
  - `_check_needs_segmented()` — 分段判断入口
  - Whisper 参数优化：beam_size=5, temperature=[0, 0.5] fallback
- **更新** `config.yaml`：新增 `whisper.segment_transcribe` 配置块
  - threshold_minutes, chunk_duration, overlap, similarity_threshold
  - normalize_loudness, beam_size, temperature_fallback
- **更新** `src/main.py`：
  - 新增 `_build_whisper_engine()` — 从配置构建 WhisperEngine（含分段参数）
  - `transcribe` 和 `pipeline` 命令使用新构建函数
- **更新** `src/pipeline.py`：`process_video()` 传递分段配置到 WhisperEngine
- **新增** `tests/test_audio_preprocess.py`：音频预处理单元测试
  - chunk 边界计算（单 chunk、多 chunk、无 overlap）
  - 分段判断逻辑（短/长视频、GPU 显存影响）
- **新增** `tests/test_merger.py`：Segment 合并去重单元测试
  - 时间偏移、文本相似度、去重合并、范围选择、排序等
- **注意**：以上代码仅通过单元测试验证，**未经真实视频外部验证**，分段转录流程的 FFmpeg 调用和 Whisper chunk 处理需要在实际长视频上测试

### 长视频分段转录策略升级为 Segment-aware 方案
- **更新** `ROADMAP.md`：将"3. 长视频分段转录策略"从固定时间切分替换为 segment-aware 方案
  - 新增 3.1 音频预处理（16kHz mono WAV, loudness normalize）
  - 新增 3.2 音频粗切 + 时间 overlap（15min/chunk, 10s overlap）
  - 新增 3.3 Whisper segment 级去重合并（核心升级，Levenshtein 相似度 > 0.8 去重）
  - 新增 3.4 统一合并输出层（结构化 segment 列表，对上层透明）
  - 新增 3.5 Whisper 执行策略优化（beam_size >= 5, temperature fallback）
  - 新增 3.6 不做 VAD 的理由说明
  - 新增完整流水线图和实施顺序表

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

### 长视频分段转录策略 3.4-3.5 完成
- **更新** `src/transcribe/models.py`：3.4 统一合并输出层
  - `Segment.to_dict()` — 转换为字典（支持 include_words 选项）
  - `Segment.to_srt_block()` — 转换为单个 SRT 字幕块
  - `TranscriptResult.to_dict()` — 结构化字典输出
  - `TranscriptResult.to_json()` — JSON 字符串输出（ensure_ascii=False）
  - `TranscriptResult.to_srt()` — 完整 SRT 字幕文本
  - `TranscriptResult.export_json()` / `export_srt()` — 文件导出
  - `TranscriptResult.from_dict()` / `from_json()` — 反序列化
  - `_seconds_to_srt_time()` 使用 round() 修复浮点毫秒精度问题
- **新增** `tests/test_models.py`：3.4 输出格式单元测试（24 个测试）
  - Segment 序列化/反序列化往返一致性
  - SRT 格式验证（含毫秒精度、小时级时间戳）
  - JSON 导出/导入往返一致性
  - 文件导出创建父目录
  - from_whisper_result 兼容新方法
- **新增** `tests/test_whisper_engine_params.py`：3.5 参数验证测试（13 个测试）
  - beam_size、temperature_fallback 默认值和自定义
  - 分段转录参数（chunk_duration、overlap、similarity_threshold 等）
  - config.yaml 配置值与 WhisperEngine 默认值一致性验证
- **注意**：单元测试全部通过（71 tests），真实视频端到端验证需要在有 GPU 的环境中运行
