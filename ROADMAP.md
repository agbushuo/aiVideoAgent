# VideoAgent 实施路线图

> 最后更新: 2026-06-26
> 当前版本: v1.1.0 (Phase 8 NiceGUI 已移除)

---

## 已完成

- [x] **Phase 1**: Whisper 转录模块 (`src/transcribe/`)
- [x] **Phase 2**: LLM 分析引擎 (`src/analyze/`)
- [x] **Phase 3**: ffmpeg 剪辑模块 (`src/edit/clipper.py`)
- [x] **Phase 3.5**: 长视频分段转录策略（音频预处理 + chunk + segment 去重，140min 电影验证通过）
- [x] **Phase 4**: Smart Clip Engine v2.0（四层架构：Scene Detection → LLM 标注 → Score/Filter → Clipper）
- [x] **Phase 4**: Scene Explorer（场景表格 + 筛选 + 排序 + 搜索 + 行内编辑）
- [x] **Phase 4.5**: 场景工具函数库（时间格式化、分数颜色、类型徽章等）
- [x] **Phase 5**: Web 控制台 v1（NiceGUI + FastAPI + TaskManager + CLI `serve` 命令）
- [x] **Phase 5.5**: 后端 API 扩展（阶段级执行、SSE 事件流、20+ REST 端点）
- [x] **Phase 2 (Web UI)**: Next.js 脚手架 + App Shell（Dashboard、任务列表、工作区、Zustand 状态管理）
- [x] **Phase 3 (Web UI)**: Workflow Builder — React Flow DAG 画布、自定义节点、ConfigPanel、运行管线
- [x] **Phase 5 (Web UI)**: Timeline Editor — Konva.js 时间轴、clip 拖拽/缩放、播放头、视频预览、导出
- [x] **Phase 6 (Web UI)**: Run Console — SSE 实时日志、阶段状态面板、重试按钮、历史日志恢复
- [x] **Phase 7 (Web UI)**: 集成测试 — 41 个 API 自动化测试全部通过、前端功能验证、管线执行器解耦
- [x] **Phase 8 (Web UI)**: 替换 NiceGUI — 删除旧代码、移除依赖、清理引用
- [x] 批量处理模块：`run_batch()` + glob 模式 + CSV 汇总报告

---

## 进行中

### Web UI 现代化：Next.js + React Flow 前端架构

> 目标：从 NiceGUI 迁移到 Workflow-first + Timeline-first 的混合编辑器
> 技术栈：Next.js 14 (App Router) + TypeScript + TailwindCSS + Zustand + React Flow + Konva.js
> 启动日期: 2026-06-25

**架构设计：**
```
VideoAgent Web
├── App Shell（布局层）
│   ├── TopBar: Project / Run / Save
│   ├── Sidebar: Projects / Presets / Pipelines / Runs
│   └── Main Canvas: 三视图切换
│
├── Workflow Builder（流程编排）     ← React Flow DAG
├── Pipeline Config Panel（参数面板） ← Schema 驱动表单
├── Scene Explorer（AI 分析结果）   ← 场景表格 + 筛选
├── Timeline Editor（剪辑可视化）   ← Konva.js 时间轴
└── Run Console（任务执行）         ← CI/CD 风格日志
```

**三视图系统：**
1. **Workflow 视图** — DAG 可视化管线编排（React Flow），拖拽排序、阶段开关、参数编辑
2. **Scene 视图** — AI 理解结果中心，tag 筛选、score 排序、搜索、选中添加到时间轴
3. **Timeline 视图** — 剪辑可视化编辑器（Konva.js），clip 拖拽/缩放/合并/删除

**实施阶段：**

| 阶段 | 内容 | 状态 | 依赖 |
|------|------|------|------|
| **Phase 1** | 后端 API 扩展（阶段级执行、SSE、20+ 端点） | 🟡 进行中 | 无 |
| **Phase 2** | Next.js 脚手架 + App Shell | ✅ 已完成 | Phase 1 |
| **Phase 3** | Workflow Builder（React Flow DAG） | ✅ 已完成 | Phase 2 |
| **Phase 4** | Scene Explorer（场景表格） | ✅ 已完成 | Phase 2 |
| **Phase 5** | Timeline Editor（Konva.js 时间轴） | ✅ 已完成 | Phase 4 |
| **Phase 6** | Run Console（SSE 实时日志） | ✅ 已完成 | Phase 1 |
| **Phase 7** | 集成测试 | ✅ 已完成 | 以上全部 |
| **Phase 8** | 替换 NiceGUI（删除旧代码） | ✅ 已完成 | Phase 7 |

**Phase 1 详细（后端 API 扩展）：**

| 步骤 | 内容 | 状态 | 文件 |
|------|------|------|------|
| 1.1 | Pydantic API 模型（TaskCreate, StageResult, SceneResponse 等） | ✅ 已完成 | `src/web/api_schemas.py` |
| 1.2 | SSE 事件流系统（广播、过滤、keepalive） | ✅ 已完成 | `src/web/sse.py` |
| 1.3 | 阶段调度器（8 个阶段映射到 pipeline 函数） | ✅ 已完成 | `src/web/stage_executor.py` |
| 1.4 | TaskManager 扩展（PipelineStageConfig, StageResult, run_stage） | ✅ 已完成 | `src/web/task_manager.py` |
| 1.5 | REST API 端点（34 个路由：任务 CRUD、阶段执行、Scene/Candidate、配置、SSE） | ✅ 已完成 | `src/web/app.py` |

**Phase 3 详细（Workflow Builder）：**

| 步骤 | 内容 | 状态 | 文件 |
|------|------|------|------|
| 3.1 | 表单字段类型 + 阶段 schema 映射 | ✅ 已完成 | `frontend/src/types/workflow.ts` |
| 3.2 | React Flow 暗色主题 CSS | ✅ 已完成 | `frontend/src/styles/reactflow-overrides.css` |
| 3.3 | 自定义 PipelineNode（图标、toggle、状态） | ✅ 已完成 | `frontend/src/components/workflow/PipelineNode.tsx` |
| 3.4 | 可复用表单字段 StageFormField | ✅ 已完成 | `frontend/src/components/workflow/StageFormField.tsx` |
| 3.5 | schema 驱动 ConfigPanel | ✅ 已完成 | `frontend/src/components/workflow/ConfigPanel.tsx` |
| 3.6 | React Flow 画布 + store 同步 | ✅ 已完成 | `frontend/src/components/workflow/ReactFlowCanvas.tsx` |
| 3.7 | 根组件 WorkflowBuilder + 运行管线 | ✅ 已完成 | `frontend/src/components/workflow/WorkflowBuilder.tsx` |

**Workflow Builder 功能：**
- React Flow DAG 画布：8 个阶段节点分层排列（转录→场景检测→LLM 标注→评分→筛选→时长规划/最终评审→剪辑）
- 自定义 PipelineNode：lucide 图标、toggle 开关、状态指示灯（等待/运行中/已完成/失败/已跳过）
- ConfigPanel：schema 驱动参数表单（select/number/slider/textarea/checkbox），动态加载 preset 和 clipMode 选项
- 运行管线：视频路径输入 + 语言选择 → POST /api/tasks，自动收集所有节点配置
- 暗色主题，品牌色一致

**Phase 4 详细（Scene Explorer）：**

| 步骤 | 内容 | 状态 | 文件 |
|------|------|------|------|
| 4.1 | 场景工具函数（formatTime, getMaxScore, getScoreColor 等） | ✅ 已完成 | `frontend/src/lib/sceneUtils.ts` |
| 4.2 | sceneStore 扩展（编辑状态、updateScene） | ✅ 已完成 | `frontend/src/stores/sceneStore.ts` |
| 4.3 | 筛选工具栏（搜索、tag 芯片、minScore、排序） | ✅ 已完成 | `frontend/src/components/scenes/SceneFiltersBar.tsx` |
| 4.4 | TanStack Table 场景表格（8 列） | ✅ 已完成 | `frontend/src/components/scenes/SceneTable.tsx` |
| 4.5 | 场景编辑弹窗（scene_type/tags/summary/8 分数） | ✅ 已完成 | `frontend/src/components/scenes/SceneEditModal.tsx` |
| 4.6 | 空状态组件 | ✅ 已完成 | `frontend/src/components/scenes/EmptyState.tsx` |
| 4.7 | 主编排组件 + MainCanvas 集成 | ✅ 已完成 | `frontend/src/components/scenes/SceneExplorer.tsx` |

**Scene Explorer 功能：**
- TanStack Table 场景表格：8 列（复选框、ID、时间、类型、标签、摘要、最高分进度条、编辑）
- 筛选工具栏：搜索框（300ms 防抖）、tag 多选芯片、最低分输入、排序下拉（最高分/时间升降序）
- 场景编辑弹窗：scene_type 下拉、tags 逗号分隔输入、summary 文本域、8 个评分维度（0-10 分）
- 勾选管理：单行复选框、全选、选中计数提示条
- 类型颜色徽章：10+ 种场景类型各有专属颜色
- 空状态提示：区分"无数据"和"无匹配"两种状态

**Phase 5 详细（Timeline Editor）：**

| 步骤 | 内容 | 状态 | 文件 |
|------|------|------|------|
| 5.1 | Timeline 类型定义 + 布局常量 | ✅ 已完成 | `frontend/src/types/timeline.ts` |
| 5.2 | Konva 画布核心（时间标尺、Clip 渲染、拖拽缩放） | ✅ 已完成 | `frontend/src/components/timeline/TimelineCanvas.tsx`, `TimeRuler.tsx`, `ClipRenderer.tsx` |
| 5.3 | Playhead 播放头 + store 增强 | ✅ 已完成 | `frontend/src/components/timeline/Playhead.tsx`, `frontend/src/stores/timelineStore.ts` |
| 5.4 | 视频预览窗口 + 缩略图浮窗 | ✅ 已完成 | `frontend/src/components/timeline/VideoPreview.tsx`, `ThumbnailPreview.tsx` |
| 5.5 | Timeline 工具栏 | ✅ 已完成 | `frontend/src/components/timeline/TimelineToolbar.tsx` |
| 5.6 | 主编排组件（数据加载、导出、SSE） | ✅ 已完成 | `frontend/src/components/timeline/TimelineEditor.tsx` |
| 5.7 | 集成到 MainCanvas | ✅ 已完成 | `frontend/src/components/layout/MainCanvas.tsx` |

**Timeline Editor 功能：**
- Konva.js 时间轴画布：时间标尺（自适应刻度密度）、单轨道、clip 矩形按场景类型着色
- Clip 交互：水平拖拽移动、左右缩放手柄调整起止时间、0.5 秒网格吸附、选中高亮
- Playhead 播放头：红色竖线贯穿轨道，可拖拽移动，requestAnimationFrame 驱动播放动画
- 视频预览窗口：源视频播放，与 playhead 双向同步，音量控制
- 缩略图浮窗：鼠标悬浮时间轴时显示对应帧的缩略图（200ms 防抖）
- 工具栏：播放/暂停、缩放（+/-）、吸附开关、删除 clip、清空、导出
- 数据加载：从 `/api/tasks/{id}/candidates` 加载已选中候选，自动铺满时间轴
- 导出：收集时间轴 clips → `POST /api/tasks/{id}/stages/clipping/run` 触发 FFmpeg 剪辑
- SSE 监听：任务完成时自动刷新 candidates

**Phase 6 详细（Run Console）：**

| 步骤 | 内容 | 状态 | 文件 |
|------|------|------|------|
| 6.1 | taskStore 扩展（consoleLogs、SSE 日志处理） | ✅ 已完成 | `frontend/src/stores/taskStore.ts` |
| 6.2 | 阶段状态面板（状态卡片、Retry 按钮） | ✅ 已完成 | `frontend/src/components/console/StageStatusPanel.tsx` |
| 6.3 | CI/CD 风格日志面板（级别颜色、自动滚动） | ✅ 已完成 | `frontend/src/components/console/LogPanel.tsx` |
| 6.4 | 主编排组件（左右分栏、SSE 连接、历史加载） | ✅ 已完成 | `frontend/src/components/console/RunConsole.tsx` |
| 6.5 | 集成到 MainCanvas（Console tab） | ✅ 已完成 | `frontend/src/components/layout/MainCanvas.tsx` |

**Run Console 功能：**
- 左右分栏布局：左侧 320px 阶段状态面板 + 右侧自适应日志面板
- 阶段状态面板：8 个 pipeline 阶段卡片，状态图标（pending/running/completed/failed/skipped）、耗时、错误信息
- Retry 按钮：失败阶段一键重试，调用 `POST /api/tasks/{id}/rerun-stage`
- CI/CD 风格日志：等宽字体、时间戳、级别徽章（info/success/warning/error）、阶段标签
- 自动滚动：新日志自动滚到底部，手动上滚暂停，滚回底部恢复
- 历史日志：mount 时从 `GET /api/tasks/{id}` 加载，刷新页面后可恢复
- SSE 实时推送：log/stage_start/stage_complete/error 事件自动追加到日志面板
- 状态栏：运行状态指示器 + SSE 连接状态 + 进度百分比

**新增 API 端点：**

任务管理：
- `POST /api/tasks` — 创建任务（含 pipeline_config）
- `DELETE /api/tasks/{id}` — 删除任务
- `POST /api/tasks/{id}/rerun-stage` — 重跑指定阶段

阶段级执行：
- `POST /api/tasks/{id}/stages/{stage}/run` — 执行单个阶段
- `GET /api/tasks/{id}/stages` — 查询所有阶段状态
- `GET /api/tasks/{id}/stages/{stage}` — 查询阶段详情

Scene / Candidate：
- `GET /api/tasks/{id}/scenes` — 场景列表（支持 tag/score/search 筛选）
- `GET /api/tasks/{id}/scenes/{id}` — 单个场景
- `PUT /api/tasks/{id}/scenes/{id}` — 手动修改标签/评分
- `GET /api/tasks/{id}/candidates` — 候选列表
- `PATCH /api/tasks/{id}/candidates/bulk-select` — 批量选中

字幕：
- `GET /api/tasks/{id}/transcript` — 获取字幕
- `PUT /api/tasks/{id}/transcript` — 保存修改
- `PUT /api/tasks/{id}/transcript/segments/{idx}` — 更新单个片段

配置参考数据：
- `GET /api/config/presets` — 预设权重
- `GET /api/config/clip-modes` — 剪辑模式
- `GET /api/config/scene-types` — 场景类型
- `GET /api/config/score-dimensions` — 评分维度
- `GET /api/config/pipeline-stages` — DAG 定义
- `GET /api/config/weights` — 完整权重配置
- `GET /api/config/duration-templates` — 时长模板

实时推送：
- `GET /api/events` — SSE 事件流
- `GET /api/tasks/{id}/events` — 特定任务 SSE 流

---

## 近期目标（提升现有管线质量）

### 剪辑后处理增强

当前剪辑功能已可用，进一步增强输出质量。

**功能设计：**
- **字幕叠加**：在剪辑片段上自动烧录 SRT 字幕（`-vf subtitles=xxx.srt`）
- **封面/缩略图生成**：每个片段自动截取关键帧（中间帧）作为封面图
- **元数据嵌入**：将标题、评分、描述写入 MP4 元数据
- **章节标记**：拼接视频中每个片段起始处添加 chapter marker

**涉及文件：** `src/edit/clipper.py`（新增后处理方法）

---

### 批量处理增强

**已实现：** `run_batch()` + glob 模式 + CSV 汇总报告

**待增强：**
- [ ] 并发控制：`--workers N` 同时处理 N 个视频（避免 GPU OOM）
- [ ] Excel 格式汇总报告

---

### 管线断点续跑（跳过已有转录）

> 背景：管线在转录后阶段（Scene Detection）因 bug 失败，修复后重新跑管线需要重新转录（~42min）。需要支持加载已有转录文件，从分析阶段继续。

**功能设计：**
- [x] `TaskCreateRequest` / `PipelineTask` 新增 `skip_existing_transcript: bool` 参数
- [x] 管线 runner 在转录阶段前检查 `outputs/{video_stem}/subtitles/{video_stem}.json`
- [x] 文件存在且启用跳过时，用 `TranscriptResult.from_json()` 加载，跳过 Whisper 引擎
- [x] 字幕审核暂停点（review_enabled）保留不变
- [x] 前端 WorkflowBuilder 添加"跳过已有转录"复选框
- [x] 异常日志记录完整 traceback 到任务日志（已修复）

**涉及文件：** `src/web/api_schemas.py`、`src/web/task_manager.py`、`src/web/pipeline_runner.py`、`frontend/src/components/workflow/WorkflowBuilder.tsx`

---

### 多语言混合视频支持

- 转录后增加标点修复后处理（基于语言模型）
- 支持指定多种语言：`--language zh,en`
- 语言切换检测：自动识别视频中的语言切换点

**涉及文件：** `src/transcribe/whisper_engine.py`、新增 `src/utils/punctuation_fix.py`

---

## 中期目标（功能扩展）

### Smart Clip Engine v2.0 增强

> MVP 已完成（4.1-4.10），以下功能待实现

- [ ] **4.11** CLI 集成 + 端到端测试
- [ ] **OpenCV Scene Detection** — 基于帧差异的场景检测器（当前只有 Whisper segment 分组）
- [ ] **说话人分离** — 通过音频特征检测说话人变化，作为 Scene Detection 信号
- [ ] **片段质量评估** — 客观指标（PSNR, SSIM）+ 主观评分

---

## 远期目标（架构升级）

### Viral Engine：短视频精剪引擎

> 目标：从游戏录播/直播长视频中自动精剪为 **短视频（30-60s）** 或 **精华合集（10-25min）**

```
长视频 → Stage 1: 转录 → Stage 2: Attention Scanner
  → Stage 3: 亮点识别 + Viral Builder → Stage 4: Story Planner
  → Stage 5: Render Engine → 短视频 / 精华合集
```

**新增模块：**
- **Attention Scanner** — 音频+文本混合分析，生成每秒注意力曲线
- **Viral Builder** — 片段 + 传播角色标注
- **Story Planner** — 按模板组装片段，生成 EDL 编辑决策列表
- **Render Engine** — 字幕烧录/缩放/去静音

---

### 服务化部署

- 任务队列：长任务异步化（Celery / ARQ）
- 文件上传支持（multipart / 分片上传）
- 多用户支持（项目隔离、权限管理）
- Docker 容器化部署

---

## 技术债务

- [ ] `clipper.py` 中 `_merge_with_fade` 的 complex filter 需要更多边界测试
- [ ] ffmpeg 错误处理可以更精细（区分编码错误、格式不支持、磁盘空间不足）
- [ ] 缺少 `clipper.py` 单元测试
- [ ] 配置文件缺少 schema 验证（建议用 pydantic 替代裸 dict）
- [ ] `src/web/ui.py` NiceGUI 代码将在 Phase 8 删除

---

## 已完成的历史记录

### Smart Clip Engine v2.0（2026-06-25 完成）

四层架构：AI 内容理解 → 规则引擎 → 策略引擎 → 最终优化

**已完成模块：**
- [x] 4.1 数据结构升级（Scene, ClipCandidate 模型）
- [x] 4.2 Scene Detection（Whisper segment 分组 MVP + OpenCV 预留接口）
- [x] 4.3 LLM Scene 标注 prompt + 分段调用
- [x] 4.4 Score Engine（preset 权重: douyin/youtube/bilibili/viral/all）
- [x] 4.5 Filter Engine（Diversity 去重、数量/时长约束）
- [x] 4.6 Clip Mode + Clip Count（CLI 参数）
- [x] 4.7 Duration Planner（60s/90s/180s/300s 模板 + 动态生成）
- [x] 4.8 Category Weight（预设权重 JSON + 用户自定义）
- [x] 4.9 用户自定义 Prompt
- [x] 4.10 LLM Final Review（二阶段筛选）

**数据流：**
```
Whisper Segments → Scene Detection → Scene[]
Scene[] → LLM 标注 → Scene[] (含 tags, multi_score)
Scene[] → Score Engine → ClipCandidate[] (含 composite_score)
ClipCandidate[] → Filter Engine → 选中的 ClipCandidate[]
选中的 → Duration Planner → 按目标时长组合（可选）
选中的 → Final Review → LLM 最终精选（可选）
选中的 → Clipper → 最终片段
```

**权重系统：**
- Preset 权重：douyin / youtube / bilibili / viral / all
- Clip Mode 权重：comedy / action / emotion / dialogue / knowledge / hook / viral / all
- 评分维度：hook / emotion / comedy / action / information / suspense / climax / viral

---

### 长视频分段转录策略（2026-06-24 完成）

**已实现：** `src/utils/audio_preprocess.py` + `src/transcribe/merger.py`

**流水线：**
```
Video → FFmpeg extract → 16kHz mono WAV → Audio chunking (15min + 10s overlap)
  → Whisper batch (per chunk) → Global timestamp normalization
  → Segment-level overlap dedup → Final TranscriptResult
```

**真实验证：** 140 分钟电影全流程（10 chunks，7171 segments，6 个亮点）

---

### Web 控制台 v1（NiceGUI，已废弃）

> 已实现基础功能，但 NiceGUI 不适合复杂交互（DAG 编排、时间轴编辑）
> 正在迁移到 Next.js + React Flow 架构

**已实现的功能（迁移到后端 API）：**
- FastAPI + NiceGUI Web 界面
- TaskManager（任务生命周期、字幕审核暂停/恢复、WebSocket 推送）
- Pipeline 全流程（转录 → 审核 → 分析 → 剪辑）
- REST API：任务 CRUD、进度查询、文件下载

**迁移状态：**
- ✅ 后端 API 扩展完成（Phase 1）
- 🟡 Next.js 前端开发中（Phase 2-8）