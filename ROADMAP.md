# VideoAgent 实施路线图

> 最后更新: 2026-06-25  
> 当前版本: v0.2.0 (Smart Clip Engine v2.0 规划中)

---

## 已完成

- [x] **Phase 1**: Whisper 转录模块（`src/transcribe/`）
- [x] **Phase 2**: LLM 分析引擎（`src/analyze/`）
- [x] **Phase 3**: ffmpeg 剪辑模块（`src/edit/clipper.py`）
  - 单个片段裁剪
  - 批量提取独立片段文件
  - 拼接精华视频（交叉淡入淡出转场）
  - 从报告 JSON 一键提取（`clips_from_report()`）
- [x] CLI 入口（`src/main.py`）：`transcribe` / `analyze` / `clip` / `pipeline`
- [x] **单视频全流程接口**（`src/pipeline.py`）
  - `process_video()` — 封装 转录→分析→(可选)剪辑 完整管线
  - 每次调用独立创建和释放资源，返回 `VideoProcessResult`
  - 所有配置参数可覆盖（`whisper_*`、`llm_*`、`ffmpeg_*`）
- [x] **批量处理模块**（`src/batch/`）
  - `run_batch()` — 串行调用 `process_video()`，每个视频完全独立运行
  - `discover_videos()` — 支持文件/目录递归/glob 模式
  - CSV 汇总报告输出
  - CLI `batch` 命令
- [x] **长视频分段转录策略**（`src/transcribe/merger.py` + `src/utils/audio_preprocess.py`，2026-06-24 验证）
  - 音频预处理：FFmpeg 提取 16kHz mono WAV，可选 loudness normalize
  - 音频粗切 + overlap：15min/chunk，10s overlap，自动检测时长阈值
  - Segment 级去重合并：Levenshtein 相似度 > 0.8 去重，整段保留/丢弃
  - Whisper 参数优化：beam_size=5，temperature fallback
  - 统一输出层：TranscriptResult 接口对上层透明
  - 真实验证：140 分钟电影全流程（10 chunks，7171 segments，6 个亮点）
- [x] **Smart Clip Engine v2.0 架构规划**（文档）
  - 四层架构设计（AI 内容理解 → 规则引擎 → 策略引擎 → 最终优化）
  - 十个功能模块详细设计
  - Scene Detection 接口（Whisper segment MVP + OpenCV 预留）
  - 多维评分 + preset 权重系统
  - 实施顺序和 MVP 路径明确

---

## 近期目标（提升现有管线质量）

### 1. 批量处理模式 ✅ 已完成

> 已实现：`src/pipeline.py` + `src/batch/__init__.py` + CLI `batch` 命令

**已实现功能：**
- [x] `videoagent batch "D:/videos/*.mp4"` 批量处理目录
- [x] 支持 glob 模式和目录递归
- [x] 串行处理，每个视频完全独立运行（`process_video()` 接口）
- [x] 生成批量汇总报告（CSV），包含所有视频的处理结果

**待增强：**
- [ ] 并发控制：`--workers N` 同时处理 N 个视频（避免 GPU OOM）
- [ ] Excel 格式汇总报告

---

### 2. 剪辑后处理增强

当前剪辑功能已可用，进一步增强输出质量。

**功能设计：**
- **字幕叠加**：在剪辑片段上自动烧录 SRT 字幕（`-vf subtitles=xxx.srt`）
- **封面/缩略图生成**：每个片段自动截取关键帧（中间帧）作为封面图
- **元数据嵌入**：将标题、评分、描述写入 MP4 元数据（`-metadata title=xxx`）
- **章节标记**：拼接视频中每个片段起始处添加 chapter marker

**涉及文件：** `src/edit/clipper.py`（新增后处理方法）

---

### 3. 长视频分段转录策略（Segment-aware 升级）✅ 已完成

> 完成日期: 2026-06-24  
> 已实现：`src/utils/audio_preprocess.py` + `src/transcribe/merger.py` + `src/transcribe/whisper_engine.py`  
> 真实验证：140 分钟电影全流程测试通过（10 chunks，7171 segments，6 个亮点）

Whisper 处理超长视频（>1 小时）时容易 OOM，需要分段策略。
核心原则：**按 Whisper segment 边界对齐切分，而非固定时间切分**，避免句子断裂。

#### 3.1 音频预处理（Step 0）✅ 已完成

**涉及文件：** 新增 `src/utils/audio_preprocess.py`

- FFmpeg 统一格式转换：16kHz mono WAV
- 可选 loudness normalize（提升噪声视频质量）
- 提取音频后释放原视频，减少内存占用

```
Video Input → FFmpeg extract → 16kHz mono WAV → Whisper Pipeline
```

#### 3.2 音频粗切 + 时间 Overlap（Step 1）✅ 已完成

**涉及文件：** `src/transcribe/whisper_engine.py`（新增分段逻辑）

- 按固定时长粗切音频（默认 15min/chunk）
- 每个 chunk 前后添加时间 overlap（默认 10s），覆盖 3-5 个 Whisper segment
- 自动检测音频时长，超过阈值时切换分段模式

```
Audio (60min)
  → Chunk A: 0:00 - 15:00 (overlap: 0:00 - 0:10)
  → Chunk B: 14:50 - 30:00 (overlap: 14:50 - 15:10)
  → Chunk C: 29:50 - 45:00 (overlap: 29:50 - 30:10)
  → Chunk D: 44:50 - 60:00 (overlap: 44:50 - 45:10)
```

#### 3.3 Whisper Segment 级去重合并（Step 2，核心）✅ 已完成

**涉及文件：** 新增 `src/transcribe/merger.py`

- 每个 chunk 转录后，给 segment 加上全局时间戳偏移
- 所有 segment 按时间排序后，按 **segment 边界** 做去重（非按时间）
- 相邻 segment 做文本相似度比对（Levenshtein / 前 N 字符模糊匹配）
  - 相似度 > 0.8 → 判定为 overlap 重复，保留时间范围更广的那个
  - 相似度 < 0.8 → 保留两者
- **关键优势**：不会出现"半句话保留、半句话丢弃"的情况，总是整段保留或整段丢弃

```
Chunk A 输出 segment: [..., S2(14:20-14:35), S3(14:35-14:52)]
Chunk B 输出 segment: [S1'(14:50-15:08), S2'(15:08-15:25), ...]

合并去重逻辑：
  S3.text vs S1'.text → similarity 0.92 → 判定重复 → 保留 S1'（全局时间更准）
  最终: [..., S2(14:20-14:35), S1'(14:50-15:08), S2'(15:08-15:25), ...]
```

#### 3.4 统一合并输出层（Step 3）✅ 已实现

**涉及文件：** `src/transcribe/merger.py` + `src/transcribe/models.py`（扩展）

- 输出结构化 segment 列表（统一格式）
- 分段结果对上层透明 — `TranscriptResult` 接口不变
- 可选：LLM 标点修复后处理（后续做，见中期目标 5）

#### 3.5 Whisper 执行策略优化 ✅ 已实现

**涉及文件：** `src/transcribe/whisper_engine.py`

- `beam_size >= 5`（提升边界准确率）
- temperature fallback（首次 0，失败时 0.5）
- 默认 `large-v3`，不引入 retry 策略（准确率已足够，retry 收益低）

#### 3.6 不做 VAD 的理由（当前阶段）

- 目标场景（游戏录播/直播）说话人不固定、背景音复杂，VAD 误判率高
- Whisper 自身按句子输出 segment，segment-aware 方案已经解决边界问题
- 如果后续发现边界问题多，再引入 `silero-vad` 作为可选预处理步骤

#### 完整流水线

```
Video Input
   ↓
FFmpeg extract audio → 16kHz mono WAV
   ↓
Audio chunking (15min + 10s overlap)
   ↓
Whisper batch processing (per chunk)
   ↓
Global timestamp normalization
   ↓
Segment-level overlap deduplication  ← 核心升级
   ↓
Final TranscriptResult (transparent to upstream)
   ↓
LLM Analyze → Clip (unchanged)
```

#### 实施顺序

| 步骤 | 内容 | 状态 | 依赖 |
|------|------|------|------|
| 3.1 | 音频预处理 | ✅ 已完成 | 无 |
| 3.2 | 音频粗切 + overlap | ✅ 已完成 | 3.1 |
| 3.3 | Segment 级去重合并 | ✅ 已完成 | 3.2 |
| 3.4 | 统一输出层 | ✅ 已完成 | 3.3 |
| 3.5 | Whisper 参数优化 | ✅ 已完成 | 无 |

**真实验证（2026-06-24）：**
- 140 分钟电影全流程测试：转录 10 chunks 共 7171 segments，LLM 提取 6 个亮点，剪辑 6 个片段 + 精华视频（3.1MB）
- 两部电影批量串行处理：合并去重功能正常，时间戳排序正确，CSV 汇总报告生成正常

---

## 中期目标（功能扩展）

### 4. Smart Clip Engine v2.0（智能片段筛选引擎）

> 目标：从"LLM 一次性输出亮点"升级为"LLM 打标签 + 程序规则引擎 + 策略筛选"的多层架构  
> 核心变化：LLM 不再输出"有哪些精彩片段"，而是输出每个 Scene 的结构化标签和多维评分；后续排序、去重、组合全部由程序逻辑处理  
> 定位：Phase 4（功能增强阶段），替代原有模糊的"智能片段筛选"规划

---

#### 4.1 整体架构

```
Whisper
    │
    ▼
字幕 (Segment 列表)
    │
    ▼
Scene Detection
（场景切分 — 当前基于 Whisper segment 逻辑分组，预留 OpenCV 接口）
    │
    ▼
LLM 分析（分阶段调用）
（每个 Scene 输出标签 + 多维评分 + 简短摘要）
    │
    ▼
Score Engine
（程序评分 — 根据 preset 权重计算综合分）
    │
    ▼
Filter Engine
（去重合并、Diversity 最小间隔、时长约束、数量控制）
    │
    ▼
Duration Planner
（根据目标时长组合片段 — 如 60s ≈ 3 个高潮）
    │
    ▼
LLM Final Review（可选）
（从候选集中做最终精选和排序）
    │
    ▼
Clipper（已有）
（ffmpeg 裁剪 + 拼接）
```

---

#### 4.2 数据结构升级

**当前 `Highlight`（单维度）：**
```python
@dataclass
class Highlight:
    segment_id: int
    start: float
    end: float
    title: str
    reason: str
    score: float          # 单一评分 0-1
```

**升级后（多维度）：**
```python
@dataclass
class Scene:
    """场景 — 由多个 Whisper segment 逻辑分组而成"""
    scene_id: int                  # 场景编号
    start: float                   # 开始时间（秒）
    end: float                     # 结束时间（秒）
    segment_ids: list[int]         # 包含的 Whisper segment 索引
    text: str                      # 场景完整文本

    # LLM 标注结果
    scene_type: str                # 类型: Dialogue / Comedy / Fight / Romance / Speech / Teaching / Transition / Music / B-roll
    tags: list[str]                # 标签: [搞笑, 情绪爆发, 冲突, 高能]
    summary: str                   # 场景简短描述（1-2 句话）

    # 多维评分（0-10 分制）
    multi_score: dict[str, float]  # {hook, emotion, comedy, action, information, suspense, climax, viral}

@dataclass
class ClipCandidate:
    """剪辑候选 — 由 Scene 经规则引擎筛选后生成"""
    scene: Scene
    composite_score: float         # 根据 preset 权重计算的综合分
    rank: int                      # 排序位置
    selected: bool                 # 是否被最终选中
```

---

#### 4.3 功能模块设计

##### 模块 1：Scene Detection（场景切分）

**当前方案（MVP）：基于 Whisper segment 逻辑分组**
- 将连续的 Whisper segment 按语义分组为 Scene
- 分组规则：
  - 时间间隔 > 阈值（默认 5 秒静音）→ 新 Scene
  - 说话人变化（后续通过 VAD 或音频特征检测）
  - 话题变化（LLM 判断）
- 每个 Scene 包含多个 segment，形成独立的内容块

**预留接口（未来升级）：**
```python
class SceneDetector(ABC):
    """场景检测器抽象基类"""

    @abstractmethod
    def detect_scenes(
        self,
        segments: list[Segment],
        video_path: str | None = None,  # OpenCV 方案需要视频文件
    ) -> list[Scene]:
        ...

class WhisperSegmentDetector(SceneDetector):
    """基于 Whisper segment 逻辑分组的检测器（MVP）"""
    ...

class OpenCVSceneDetector(SceneDetector):
    """基于 OpenCV 帧差异的场景检测器（未来）"""
    ...
```

##### 模块 2：LLM Scene 标注

**LLM 输出格式（每个 Scene 独立输出）：**
```json
{
  "scene_id": 15,
  "scene_type": "Comedy",
  "tags": ["搞笑", "情绪爆发", "冲突", "高能"],
  "multi_score": {
    "hook": 9.6,
    "emotion": 8.8,
    "comedy": 9.6,
    "action": 1.2,
    "information": 3.1,
    "suspense": 4.0,
    "climax": 7.5,
    "viral": 9.1
  },
  "summary": "主角在这里遭遇了……（1-2 句话描述）"
}
```

**LLM 调用策略：**
- 复用现有分段转录策略：长视频按 chunk 分组，每个 chunk 内的 Scene 批量提交给 LLM
- 避免单个 prompt 超过上下文窗口
- 每个 chunk 独立调用，结果合并

##### 模块 3：Clip Mode（切片模式）

用户通过 `--mode` 指定剪辑类型：

| 模式 | 说明 | 优先维度 |
|------|------|----------|
| `comedy` | 搞笑片段 | comedy 80%, humor 20% |
| `action` | 打斗/动作片段 | action 70%, suspense 30% |
| `emotion` | 情绪片段（哭、吵架、反转） | emotion 60%, climax 40% |
| `dialogue` | 文戏/台词/名场面 | information 40%, dialogue 30%, hook 30% |
| `knowledge` | 知识点/教学/干货 | information 80%, education 20% |
| `hook` | 前三秒最吸引人的片段 | hook 90%, viral 10% |
| `viral` | 综合爆款（AI 综合判断） | 见下方权重公式 |
| `all` | 不限制类型，全量输出 | 按综合分排序 |

`viral` 模式默认权重：
```
Hook:     30%
Emotion:  25%
Comedy:   20%
Conflict: 15%
Info:     10%
```

##### 模块 4：Clip Count（片段数量控制）

```bash
--clips 5     # 输出 Top 5
--clips 20    # 输出 20 个素材
--clips 0     # 不限制数量（默认行为）
```

##### 模块 5：Duration Planner（成片时长规划）

```bash
--duration 60s    # 目标 60 秒成片
--duration 180s   # 目标 3 分钟成片
```

AI 自动规划结构：
- 60s → 约 3 个高潮片段（15s Hook + 20s 冲突 + 25s 结尾）
- 180s → 约 5 个高潮 + 2 个过渡 + 1 个 Ending
- 片段长度动态调整，不完全由内容决定（见模块 6）

##### 模块 6：Dynamic Clip（动态片段长度）

- 不以固定时长（如 30 秒）裁剪
- 以 Scene 边界作为剪辑点
- 片段长度由内容自然结束点决定（可能 18s / 43s / 91s）
- Duration Planner 在组合时考虑总时长约束，但不截断单个 Scene

##### 模块 7：Auto Diversity（自动去重）

**问题：** AI 常输出时间相邻的多个片段（12:10, 12:20, 12:35, 12:48），实际属于同一段内容。

**解决方案：**
```python
def diversify(
    candidates: list[ClipCandidate],
    min_gap: float = 120.0,    # 最小间隔（秒），默认 2 分钟
) -> list[ClipCandidate]:
    """同一时间区域内只保留最高分的片段"""
    ...
```

- 按时间排序候选片段
- 滑动窗口检测：与已选中片段距离 < min_gap 的，只保留最高分
- 确保输出的片段分布在视频的不同区域

##### 模块 8：Category Weight（平台预设权重）

```bash
--preset douyin     # 抖音权重
--preset youtube    # YouTube 权重
--preset bilibili   # B 站权重
--preset custom     # 自定义权重（需配合 --weights）
```

预设权重表：

| 维度 | douyin | youtube | bilibili |
|------|--------|---------|----------|
| Hook | 40% | 20% | 15% |
| Emotion | 30% | 10% | 20% |
| Conflict | 20% | 10% | 10% |
| Information | 10% | 50% | 35% |
| Comedy | 0% | 10% | 25% |
| Story | 0% | 30% | 20% |

权重配置可持久化为 JSON 文件，支持用户自定义。

##### 模块 9：用户自定义 Prompt

```bash
videoagent clip movie.mp4 --prompt "切情侣吵架片段"
videoagent clip movie.mp4 --prompt "切所有名场面"
videoagent clip movie.mp4 --prompt "只切女性角色高光"
```

- 用户 prompt 注入到 LLM Scene 标注的 system prompt 中
- LLM 根据 prompt 调整标签和评分倾向
- 可与 `--mode` 叠加使用（prompt 优先级更高）

##### 模块 10：二阶段筛选（核心流程）

```
Stage 1 — LLM Scene 标注：
  所有 Scene → LLM 批量打标签 + 多维评分
  （复用分段策略，长视频分批调用）

Stage 2 — 程序规则引擎：
  Score Engine → 根据 preset 计算综合分
  Filter Engine → Diversity 去重 + 数量/时长约束
  Duration Planner → 按目标时长组合

Stage 3 — LLM Final Review（可选）：
  候选列表（如 20 个）→ LLM 最终精选（如 5 个）+ 重排序
  "以下是 20 个候选片段，请选出最适合短视频的 5 个并排序"
```

---

#### 4.4 CLI 命令设计

```bash
# 基础用法（兼容现有行为）
videoagent clip report.json --video input.mp4

# 新模式：按类型筛选
videoagent clip report.json --video input.mp4 --mode comedy --clips 5
videoagent clip report.json --video input.mp4 --mode action
videoagent clip report.json --video input.mp4 --mode emotion

# 平台预设
videoagent clip report.json --video input.mp4 --preset douyin --clips 10
videoagent clip report.json --video input.mp4 --preset bilibili

# 时长约束
videoagent clip report.json --video input.mp4 --duration 60s --mode viral
videoagent clip report.json --video input.mp4 --duration 180s --preset youtube

# 自定义 prompt
videoagent clip report.json --video input.mp4 --prompt "切情侣吵架片段"
videoagent clip report.json --video input.mp4 --prompt "只切名场面"

# 组合使用
videoagent clip report.json --video input.mp4 \
    --mode viral --preset douyin --clips 10 --duration 180s

# pipeline 全流程（增强）
videoagent pipeline input.mp4 --clip --mode comedy --clips 5 --preset douyin
```

---

#### 4.5 涉及文件

```
src/
 ├── clip_engine/              # 新增：智能片段筛选引擎
 │    ├── __init__.py
 │    ├── scene_detector.py    # Scene Detection（Whisper segment 分组 + OpenCV 接口）
 │    ├── scorer.py            # Score Engine（多维评分 + preset 权重计算）
 │    ├── filter.py            # Filter Engine（Diversity 去重、数量/时长约束）
 │    ├── planner.py           # Duration Planner（目标时长组合规划）
 │    └── models.py            # Scene, ClipCandidate 数据模型
 │
 ├── analyze/
 │    └── llm_analyzer.py      # 更新：新增 scene_analysis() 方法
 │
 └── main.py                   # 更新：clip 命令增加 --mode, --preset, --clips, --duration, --prompt
```

---

#### 4.6 实施顺序

| 步骤 | 内容 | 预估时间 | 依赖 |
|------|------|----------|------|
| **4.1** | 数据结构升级（Scene, ClipCandidate 模型） | 半天 | 无 |
| **4.2** | Scene Detection（Whisper segment 分组 MVP） | 1 天 | 4.1 |
| **4.3** | LLM Scene 标注 prompt + 分段调用 | 1 天 | 4.1, 4.2 |
| **4.4** | Score Engine（preset 权重计算） | 半天 | 4.1 |
| **4.5** | Filter Engine（Diversity 去重） | 半天 | 4.4 |
| **4.6** | Clip Mode + Clip Count（CLI 参数） | 半天 | 4.4, 4.5 |
| **4.7** | Duration Planner | 1 天 | 4.5 |
| **4.8** | Category Weight（预设权重配置） | 半天 | 4.4 |
| **4.9** | 用户自定义 Prompt | 半天 | 4.3 |
| **4.10** | LLM Final Review（二阶段筛选） | 1 天 | 4.3, 4.5 |
| **4.11** | CLI 集成 + 端到端测试 | 1 天 | 以上全部 |

**优先实现（MVP）：4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6**
- 这几步完成后即可实现 `--mode` + `--clips` + `--preset` + Diversity 去重
- 纯程序逻辑部分（4.4/4.5）开发成本低、可测试性强
- 效果提升明显，可快速验证方向

---

### 5. 多语言混合视频支持

中文视频常夹杂英文术语，Whisper 标点处理不够完美。

**功能设计：**
- 转录后增加标点修复后处理（基于语言模型）
- 支持指定多种语言：`--language zh,en`
- 语言切换检测：自动识别视频中的语言切换点

**涉及文件：** `src/transcribe/whisper_engine.py`、新增 `src/utils/punctuation_fix.py`

---

## 远期目标（架构升级）

### 6. FastAPI 服务化

将 CLI 工具升级为 HTTP 服务，支持远程调用和嵌入其他系统。

**功能设计：**
- REST API 端点：
  - `POST /transcribe` — 上传视频，返回字幕
  - `POST /analyze` — 提交字幕，返回分析报告
  - `POST /clip` — 提交报告 + 视频，返回剪辑文件
  - `GET /tasks/{id}/status` — 查询任务进度
- 任务队列：长任务异步化（Celery / ARQ）
- WebSocket 实时进度推送
- 文件上传支持（multipart / 分片上传）

**涉及文件：** 新增 `src/server/` 模块（FastAPI 应用）

---

## 技术债务

- [ ] `clipper.py` 中 `_merge_with_fade` 的 complex filter 构建逻辑需要更多边界测试（片段时长 < 转场时长等）
- [ ] ffmpeg 错误处理可以更精细（区分编码错误、格式不支持、磁盘空间不足等）
- [ ] 缺少单元测试覆盖 `clipper.py`
- [ ] 配置文件缺少 schema 验证（建议用 pydantic 替代裸 dict）

---

## 可视化界面（远期规划）

### 需求分析

当前 CLI 工具功能完整，但对非技术用户不够友好。可视化界面需要解决：
- 批量视频的拖拽上传和队列管理
- 转录/分析进度的实时可视化
- 亮点片段的时间轴预览（类似视频编辑器的轨道视图）
- 一键导出剪辑结果

### 方案对比

| 方案 | 技术栈 | 优点 | 缺点 | 适合场景 |
|------|--------|------|------|----------|
| **桌面应用** | Tauri + React | 体积小(<5MB)、原生性能、可调用本地 ffmpeg | 需要打包分发、多平台适配 | 个人用户、离线使用 |
| **Web 服务** | FastAPI + React/Vue | 跨平台、无需安装、可远程访问 | 需要部署服务器、大文件上传体验差 | 团队协作、云端部署 |
| **轻量 GUI** | NiceGUI (Python) | 纯 Python 开发、与现有代码无缝集成、开发快 | 功能受限、不适合复杂交互 | 快速原型、内部工具 |
| **Electron** | Electron + React | 生态成熟、功能强大 | 包体积大(>100MB)、内存占用高 | 商业产品、功能丰富 |

### 推荐方案：分两阶段实现

#### 阶段一：NiceGUI 快速原型（2-3 周）

**为什么选 NiceGUI：**
- 纯 Python，无需前端工程师，与现有代码栈零摩擦
- 内置文件上传、进度条、表格、图表组件
- 开发速度极快，适合验证界面交互逻辑
- 生成的 Web 界面可通过浏览器访问（localhost:8080）

**MVP 功能：**
- 文件上传区（支持拖拽 + 批量选择）
- 处理队列表格（实时状态更新）
- 亮点时间轴（可点击选中/取消片段）
- 导出面板（选择片段 + 配置参数）

**涉及文件：** 新增 `src/gui/nicegui_app.py`

---

#### 阶段二：Tauri + React 桌面应用（1-2 个月）

**升级到 Tauri 的触发条件：**
- NiceGUI 原型验证了交互逻辑
- 需要打包分发给非技术用户
- 需要更丰富的视频预览（原生视频播放器集成）
- 需要离线使用和系统级集成（右键菜单、文件关联）

**Tauri 专属功能：**
- **原生视频预览**：集成系统播放器，支持倍速、跳转
- **时间轴编辑器**：拖拽调整片段边界、合并/拆分亮点
- **右键菜单集成**：右键视频文件 → "用 VideoAgent 处理"
- **系统托盘**：后台处理时最小化到托盘
- **自动更新**：内置更新机制
- **多平台打包**：Windows / macOS / Linux 一键打包

---

### 界面功能清单（按优先级）

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 文件拖拽上传 | 支持单个/批量视频文件 |
| P0 | 处理进度展示 | 转录/分析/剪辑三阶段进度条 |
| P0 | 亮点时间轴 | 可视化展示亮点片段，支持选中/取消 |
| P0 | 一键导出 | 导出独立片段 + 精华视频 + 报告 |
| P1 | 视频预览播放 | 预览原始视频和剪辑片段 |
| P1 | 片段边界调整 | 在时间轴上拖拽微调片段起止时间 |
| P1 | 批量队列管理 | 暂停/恢复/取消/重跑 |
| P2 | 片段合并/拆分 | 手动合并相邻片段或拆分过长片段 |
| P2 | 转场效果选择 | 选择不同转场类型（淡入/滑动/缩放） |
| P2 | 字幕预览 | 在视频预览中叠加字幕 |
| P3 | 模板系统 | 保存剪辑配置为模板（评分阈值、时长限制等） |
| P3 | 历史记录 | 查看历史处理记录，支持重新导出 |
| P3 | 快捷键支持 | 键盘操作时间轴、播放控制 |

---

## Viral Engine：短视频精剪引擎（v2.0 规划）

> 目标：从游戏录播/直播长视频中自动精剪为 **短视频（30-60s）** 或 **精华合集（10-25min）**  
> 用户：自用（不追求产品化，追求效果）  
> 原则：保留现有管线，增量升级

---

### 整体架构

```
          长视频 (直播/录播)
                ↓
    ┌─────────────────────┐
    │ Stage 1: 转录       │  (已有) Whisper → 字幕
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │ Stage 2: 注意力扫描  │  (新增) 音频+文本混合分析
    │   Attention Scanner  │  → 每秒注意力曲线
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │ Stage 3: 亮点识别    │  (已有+升级) LLM 分析
    │   + Viral Builder    │  → 片段 + 传播角色标注
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │ Stage 4: 故事编排    │  (新增) 按模板组装片段
    │   Story Planner      │  → EDL 编辑决策列表
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │ Stage 5: 渲染输出    │  (已有+增强) ffmpeg 剪辑
    │   Render Engine      │  → 字幕烧录/缩放/去静音
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │ Stage 6: 质量评估    │  (预留) Viral Critic
    │   (可选, 后期添加)    │  → 评分 + 修复建议
    └─────────────────────┘
```

---

### 目录结构（增量式，不破坏现有功能）

```
src/
 ├── transcribe/          # 保留：Whisper 转录 (不变)
 ├── analyze/             # 保留：LLM 分析 (不变)
 ├── clip_engine/         # 新增：Smart Clip Engine (Phase 4)
 ├── attention/           # 新增：注意力扫描
 │    ├── scanner.py      # 主入口：混合分析引擎
 │    ├── audio_features.py   # 音频特征提取 (音量/语速/停顿)
 │    └── text_features.py    # 文本特征 (反转词/信息密度/情绪)
 ├── viral/               # 新增：传播片段构建
 │    ├── segment_builder.py  # 从注意力曲线选传播片段
 │    └── scorer.py           # Viral Score 计算 (公式可配置)
 ├── planner/             # 新增：故事编排
 │    ├── story_planner.py    # LLM 驱动的故事结构编排
 │    └── templates.py        # 预设模板 (游戏/口播/故事)
 ├── edit/                # 增强：渲染引擎
 │    ├── clipper.py          # 保留：基础剪辑 (不变)
 │    └── effects.py          # 新增：后处理效果
 └── utils/               # 保留 + 扩展
```

---

### 故事模板系统

不同内容类型使用不同的叙事结构模板：

#### 模板 1：游戏实况 (`gaming_highlight`)

```
目标时长: 30-60s (短视频) 或 10-25min (精华)
结构:
  0-3s    HOOK: 最精彩的瞬间前置 (击杀/翻车/搞笑)
  3-8s    CONTEXT: 极短背景 (在干嘛/什么局)
  8s-     CORE: 按时间线播放精彩片段，快剪节奏
  结尾    PAYOFF: 结果/反转/笑点落地
选片规则:
  - 优先高音量峰值段 (战斗/爆炸/惊呼)
  - 优先操作密集段 (APM 高)
  - 保留完整的"起因→过程→结果"链
```

#### 模板 2：故事分享 (`storytelling`)

```
目标时长: 30-60s
结构:
  0-2s    HOOK: 冲突/反常识/悬念前置
  2-8s    SETUP: 背景铺垫 (极短)
  8-25s   CORE: 核心信息/故事主体
  25-30s  TWIST: 反转/总结/金句
选片规则:
  - 优先情绪变化大的段落
  - 优先有"但是/然而/实际上"等反转词的段落
  - 保留完整的叙事弧
```

#### 模板 3：口播知识 (`talking_head`)

```
目标时长: 30-60s (短视频) 或 10-25min (精华)
结构:
  0-3s    HOOK: 最核心的观点/数据前置
  3-10s   TEASER: "为什么重要"
  10s-    CORE: 按信息密度排序，去掉废话
  结尾    CTA: 总结/行动号召
选片规则:
  - 优先信息密度最高的段落
  - 去掉"嗯/啊/然后"等填充词段落 (静音移除)
  - 保留数据/案例/类比
```

#### 模板 4：直播精华 (`livestream_digest`)

```
目标时长: 10-25min
结构:
  按时间线保留精彩片段，去水留精
  - 去掉长时间挂机/等待/重复操作
  - 保留高光时刻 + 有趣互动
  - 片段之间快速过渡
选片规则:
  - 注意力评分 > 阈值的段落
  - 观众互动高峰 (弹幕/笑声)
  - 关键决策/转折点
```

---

### 注意力扫描器 (Attention Scanner) 设计

**混合信号分析，输出每秒级注意力曲线：**

```python
@dataclass
class AttentionPoint:
    timestamp: float
    attention_score: float    # 综合注意力分 (0-1)
    audio: AudioFeatures      # 音频特征
    text: TextFeatures        # 文本特征

@dataclass
class AudioFeatures:
    volume: float             # 音量 (归一化 0-1)
    speech_rate: float        # 语速 (字/秒)
    pitch: float              # 音调
    is_silence: bool          # 是否静音段
    volume_delta: float       # 音量变化率 (突然变大 = 可能精彩)

@dataclass
class TextFeatures:
    info_density: float       # 信息密度
    has_reversal: bool        # 是否含反转词
    emotion: str              # neutral / surprise / excitement / ...
    emotion_delta: float      # 情绪变化幅度
```

**音频特征提取（依赖）：**
- `librosa` — 音频信号分析（音量、音调、MFCC）
- `pydub` — 静音检测、音频切片

**文本特征提取：**
- 反转词词典（但是/然而/实际上/没想到/结果/居然/卧槽/我靠）
- 信息密度 = 单位时间内有效词汇数 / 总词汇数
- 情绪分类 = LLM 批量标注（每 5 秒一个标签，不必每秒）

---

### Viral Score 公式（可配置，后续调优）

```python
# 默认公式，权重后续根据实际效果调整
VIRAL_SCORE_FORMULA = {
    "hook_strength": 0.35,       # 开头吸引力
    "emotion_delta": 0.25,       # 情绪变化幅度
    "info_density": 0.20,        # 信息密度
    "structure_fit": 0.20,       # 与模板结构的匹配度
}

# 不同模板可以覆盖权重
TEMPLATE_WEIGHTS = {
    "gaming_highlight": {
        "hook_strength": 0.30,
        "emotion_delta": 0.30,   # 游戏更看重情绪/刺激
        "info_density": 0.15,
        "structure_fit": 0.25,
    },
    "talking_head": {
        "hook_strength": 0.25,
        "emotion_delta": 0.15,
        "info_density": 0.35,    # 口播更看重信息量
        "structure_fit": 0.25,
    },
}
```

---

### CLI 命令设计

```bash
# 短视频模式 (30-60s)
videoagent viral input.mp4 --template gaming_highlight --duration short

# 精华合集模式 (10-25min)
videoagent viral input.mp4 --template livestream_digest --duration digest

# 批量处理多个视频
videoagent viral --batch "D:/recordings/*.mp4" --template gaming_highlight

# 指定输出平台格式
videoagent viral input.mp4 --platform tiktok    # 9:16 竖屏
videoagent viral input.mp4 --platform youtube    # 16:9 横屏

# 迭代优化 (后期添加)
videoagent viral input.mp4 --auto-iterate --max-rounds 3

# 查看注意力曲线 (调试用)
videoagent scan input.mp4 --output attention_curve.json
```

---

### 渲染引擎增强 (effects.py)

```python
class RenderEffects:
    """后处理效果"""

    def burn_subtitles(self, video, srt_path, style="kinetic_bold"):
        """烧录字幕，支持关键词高亮"""

    def dynamic_zoom(self, video, attention_curve, trigger_threshold=0.8):
        """高注意力点自动缩放 (Ken Burns 效果)"""

    def remove_silence(self, video, threshold=-40, min_duration=0.3):
        """移除静音段 (直播去水)"""

    def fast_cut_transition(self, clip1, clip2, duration=0.1):
        """快剪转场 (比淡入淡出更激进)"""

    def beat_sync_cuts(self, video, audio_beats):
        """按音乐节拍对齐剪辑点"""
```

---

### Viral Critic（预留接口，后期实现）

```python
class ViralCritic:
    """视频质量评估 + 自动修复建议"""

    def evaluate(self, video_path: str, template: str) -> CriticReport:
        """评估视频质量，返回问题列表和修复建议"""

    def auto_fix(self, report: CriticReport, original_clips: list) -> EDL:
        """根据评估报告自动调整片段选择"""
```

**触发条件：** 等有真实数据对比后再实现，不急于现在做。

---

### 实施顺序

| 阶段 | 内容 | 预估时间 | 依赖 |
|------|------|----------|------|
| **V2.1** | 故事模板系统 + CLI `viral` 命令 | 1-2 周 | 无 |
| **V2.2** | 注意力扫描器 (音频+文本) | 2-3 周 | librosa, pydub |
| **V2.3** | Viral Score + 片段选择器 | 1 周 | V2.2 |
| **V2.4** | 渲染效果增强 (字幕/缩放/去静音) | 1-2 周 | ffmpeg |
| **V2.5** | Viral Critic 闭环 | 待定 | 有真实数据后 |
