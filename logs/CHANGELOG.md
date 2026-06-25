# 变更记录

## 2026-06-25

### 项目可视化仪表盘
- **新增** `dashboard.html`：交互式项目仪表盘，包含总览、架构关系图、数据流程图、模块详情、CLI 命令参考、路线图进度
- **新增** 模块依赖关系图 (Mermaid)
- **新增** 目录结构思维导图 (Mermaid)
- **新增** 传统管线 + Smart Clip v2.0 数据流时序图
- **新增** 长视频分段转录策略流程图
- **新增** 8 个模块详情卡片（可点击展开接口文档）
- **新增** CLI 命令速查表
- **新增** Phase 1-5 路线图进度条

### Smart Clip Engine v2.0 单元测试（87 个测试全部通过）
- **新增** `tests/test_clip_engine.py`：Smart Clip Engine v2.0 完整单元测试
  - TestScene（8 个）：创建、默认值、from_segments、序列化往返、duration/mid_point 属性
  - TestClipCandidate（3 个）：创建、序列化往返、默认值
  - TestClipResult（4 个）：创建、JSON 导出、序列化往返
  - TestWhisperSegmentDetector（10 个）：基本分组、间隔检测、空输入、合并短场景、拆分长场景、无序输入、OpenCV 预留接口
  - TestPresetWeights（12 个）：所有预设加载、未知预设报错、分数计算、自定义权重、JSON 文件加载
  - TestClipMode（3 个）：模式加载、列表、未知模式报错
  - TestScoreEngine（9 个）：预设评分、排序、排名分配、clip_mode、自定义权重、阈值过滤
  - TestClipFilter（9 个）：Diversity 去重、数量限制、时长约束、selected 标记、gap 计算
  - TestFilterHelpers（3 个）：diversify、select_top、select_by_duration 便捷函数
  - TestDurationPlanner（7 个）：60s/180s 模板、空输入、时间顺序、高分优先、duration_ratio
  - TestDurationHelpers（4 个）：plan_duration、list_duration_templates、show_duration_template
  - TestDurationSlots（6 个）：槽位数据结构、模板结构、动态生成（短/中/长）
  - TestFinalReviewer（6 个）：空输入、LLM 调用、结果序列化、target_duration 传递
  - TestFinalReviewHelper（1 个）：便捷函数
  - TestFullPipeline（3 个）：完整数据流集成、ClipResult 构建、weights.json 加载验证
- **验证结果**：87 passed in 0.14s

### Smart Clip Engine v2.0 MVP 实现（4.1-4.6 代码实现）
- **新增** `src/clip_engine/`：智能片段筛选引擎模块
  - `models.py` — Scene, ClipCandidate, ClipResult 数据模型
    - Scene: 场景对象，包含 segment_ids, text, scene_type, tags, summary, multi_score
    - ClipCandidate: 剪辑候选，包含 composite_score, rank, selected
    - ClipResult: 完整剪辑结果，包含 all_candidates, selected_candidates
    - MULTI_SCORE_DIMENSIONS: 8 个评分维度（hook, emotion, comedy, action, information, suspense, climax, viral）
    - SCENE_TYPES: 10 种场景类型
  - `scene_detector.py` — 场景检测器
    - SceneDetector 抽象基类（预留 OpenCV 接口）
    - WhisperSegmentDetector: 基于时间间隔分组（gap_threshold, min/max_scene_duration）
    - OpenCVSceneDetector: 预留接口（NotImplementedError）
  - `scorer.py` — 评分引擎
    - PresetWeights: 预设权重（douyin/youtube/bilibili/viral/all）
    - ClipMode: 剪辑模式权重（comedy/action/emotion/dialogue/knowledge/hook/viral/all）
    - ScoreEngine: 综合评分计算，支持 preset + clip_mode + custom_weights
  - `filter.py` — 过滤引擎
    - ClipFilter: Diversity 去重（min_gap 滑动窗口）、数量控制（max_clips）、时长约束（target_duration）
    - diversify(), select_top(), select_by_duration() 便捷函数
- **新增** `prompts/scene_analysis.md`：LLM Scene 标注 prompt
  - 场景类型识别、标签打标、多维评分（0-10 分制）、摘要生成
- **更新** `src/analyze/llm_analyzer.py`：
  - 新增 `_scene_prompt` prompt 加载
  - 新增 `_build_scenes_text()` — 构建场景文本
  - 新增 `_parse_scene_response()` — 解析 LLM 标注响应
  - 新增 `analyze_scenes()` — 对 Scene 列表进行 LLM 标注（支持分批、用户 prompt 注入）
- **更新** `src/main.py`：
  - 新增 `_parse_duration()` — 解析时长字符串（60s, 3m, 1h 等格式）
  - 新增 `_get_video_path_from_report()` — 从报告读取视频路径
  - 新增 `_run_smart_clip()` — Smart Clip Engine v2.0 完整流程
  - `clip` 命令新增参数: `--smart-clip`, `--mode`, `--preset`, `--clips`, `--duration`, `--prompt`, `--min-gap`, `--transcript`
  - `pipeline` 命令新增参数: `--smart-clip`, `--mode`, `--preset`, `--clips`, `--duration`, `--prompt`
- **更新** `ROADMAP.md`：
  - 版本升至 v0.3.0
  - Smart Clip Engine v2.0 标记为 ✅ MVP 已完成（4.1-4.6）
  - 新增待实现项（4.7-4.11）
- **设计决策**：
  - Scene Detection MVP 完全基于 Whisper segment 时间间隔分组，不依赖视频文件
  - 保留 SceneDetector 抽象基类，后续可切换 OpenCV 帧差异方案
  - preset 权重使用模块级常量表（避免 dataclass mutable default 问题）
  - LLM 标注复用现有分段策略，长视频分批处理（max_scenes_per_batch=50）
  - CLI 通过 --smart-clip 参数切换新旧模式，完全兼容现有行为

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
  - `BatchResult` — 批量处理结果聚合，包含 success_count/fai
### Smart Clip Engine v2.0 增强（4.7-4.10 实现）
- **新增** `src/clip_engine/planner.py`：Duration Planner（目标时长组合规划）
  - DurationPlanner: 根据目标时长智能组合片段
  - 预定义模板：60s（3高潮）、90s（4-5片段）、180s（5高潮+2过渡+1结尾）、300s
  - 动态模板生成：根据任意目标时长自动生成槽位
  - 槽位角色系统：hook/climax/transition/ending，按优先级分配
  - plan_duration() 便捷函数
- **新增** `src/clip_engine/weights.json`：预设权重配置文件
  - 内置预设权重（douyin/youtube/bilibili/viral/all）
  - 内置剪辑模式权重（comedy/action/emotion/dialogue/knowledge/hook/viral/all）
  - 支持 ~/.videoagent/weights.json 用户自定义覆盖
- **新增** `src/clip_engine/reviewer.py`：LLM Final Review（二阶段筛选）
  - FinalReviewer: 对规则引擎筛选后的候选做 LLM 最终精选和重排序
  - ReviewResult/ReviewSelection 结果模型
  - final_review() 便捷函数
- **新增** `prompts/final_review.md`：LLM Final Review 独立 prompt 文件
  - 精选标准：独立性、吸引力、多样性、节奏感、平台适配
  - 排序原则：Hook 前置、节奏递进、类型交替、留白
  - 角色定义：hook/buildup/climax/transition/ending
- **更新** `src/clip_engine/scorer.py`：
  - 权重从 JSON 文件加载（替代硬编码常量）
  - 新增 reload_weights() — 运行时刷新权重缓存
  - 新增 PresetWeights.from_json_file() — 从外部 JSON 加载自定义权重
  - ScoreEngine 新增 weight_file 参数
  - 新增 list_presets() / show_preset() / ClipMode.list_available() 便捷函数
- **更新** `src/analyze/llm_analyzer.py`：
  - 新增 _final_review_prompt 加载
  - 新增 _default_final_review_prompt() 默认 prompt
  - 新增 _build_candidates_text() — 构建候选片段文本
  - 新增 _parse_final_review_response() — 解析 Final Review 响应
  - 新增 final_review() — LLM 二阶段筛选方法
  - 改进 analyze_scenes() 中的用户 prompt 注入逻辑（从 system prompt 改为 user prompt 末尾追加）
- **更新** `src/main.py`：
  - _run_smart_clip() 集成 Duration Planner 和 LLM Final Review
  - 新增 --duration-planner CLI 参数（启用 Duration Planner）
  - 新增 --final-review CLI 参数（启用 LLM Final Review）
  - 新增 --final-review-count CLI 参数（Final Review 精选数量）
  - clip 和 pipeline 命令均支持新参数
- **更新** `src/clip_engine/__init__.py`：更新模块文档
to_srt()` — 完整 SRT 字幕文本
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
