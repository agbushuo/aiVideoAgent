# VideoAgent 实施路线图

> 最后更新: 2026-06-28
> 当前版本: v1.2.0

---

## 已完成

- [x] **Phase 1**: Whisper 转录模块 (`src/transcribe/`)
- [x] **Phase 2**: LLM 分析引擎 (`src/analyze/`)
- [x] **Phase 3**: ffmpeg 剪辑模块 (`src/edit/clipper.py`)
- [x] **Phase 3.5**: 长视频分段转录策略（音频预处理 + chunk + segment 去重，140min 电影验证通过）
- [x] **Phase 4**: Smart Clip Engine v2.0（四层架构：Scene Detection → LLM 标注 → Score/Filter → Clipper）
- [x] **Phase 4**: Scene Explorer（场景表格 + 筛选 + 排序 + 搜索 + 行内编辑）
- [x] **Phase 4.5**: 场景工具函数库（时间格式化、分数颜色、类型徽章等）
- [x] **Phase 5**: Web 控制台（FastAPI + Next.js + TaskManager + CLI `serve` 命令）
- [x] **Phase 5.5**: 后端 API 扩展（阶段级执行、SSE 事件流、34+ REST 端点）
- [x] **Phase 6**: Workflow Builder — React Flow DAG 画布、自定义节点、ConfigPanel
- [x] **Phase 7**: Run Console — SSE 实时日志、阶段状态面板、重试按钮
- [x] 批量处理模块：`run_batch()` + glob 模式 + CSV 汇总报告
- [x] 任务持久化：`data/tasks.json` 自动保存，后端重启不丢失
- [x] 批量删除：前端复选框 + 后端 `DELETE /api/tasks/bulk-delete`
- [x] 管线断点续跑：跳过已有转录（`skip_existing_transcript`）
- [x] 预设管理：`data/presets.json` 持久化 + Web 编辑器（CRUD + 复制 + Prompt 覆盖）
- [x] 用户设置管理：`data/settings.json` + config.yaml 同步 + localStorage 回退
- [x] 文件浏览器：驱动器列表 + 目录浏览 + 视频过滤
- [x] 后端 i18n：字典式国际化模块（zh/en）
- [x] 前端 i18n：next-intl 全组件国际化（zh/en）
- [x] 侧边栏导航重构：预设、任务、设置三项导航
- [x] 设置页面：外观（主题/配色）+ 模型配置（本地/在线 LLM 切换）

---

## 近期目标（提升现有管线质量）

### 剪辑后处理增强

当前剪辑功能已可用，进一步增强输出质量。

- [ ] **字幕叠加**：在剪辑片段上自动烧录 SRT 字幕（`-vf subtitles=xxx.srt`）
- [ ] **封面/缩略图生成**：每个片段自动截取关键帧（中间帧）作为封面图
- [ ] **元数据嵌入**：将标题、评分、描述写入 MP4 元数据
- [ ] **章节标记**：拼接视频中每个片段起始处添加 chapter marker

**涉及文件：** `src/edit/clipper.py`（新增后处理方法）

---

### 批量处理增强

**已实现：** `run_batch()` + glob 模式 + CSV 汇总报告

**待增强：**
- [ ] 并发控制：`--workers N` 同时处理 N 个视频（避免 GPU OOM）
- [ ] Excel 格式汇总报告

---

### 多语言混合视频支持

- [ ] 转录后增加标点修复后处理（基于语言模型）
- [ ] 支持指定多种语言：`--language zh,en`
- [ ] 语言切换检测：自动识别视频中的语言切换点

**涉及文件：** `src/transcribe/whisper_engine.py`、新增 `src/utils/punctuation_fix.py`

---

## 中期目标（功能扩展）

### Smart Clip Engine v2.0 增强

> MVP 已完成，以下功能待实现

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

- [ ] 任务队列：长任务异步化（Celery / ARQ）
- [ ] 文件上传支持（multipart / 分片上传）
- [ ] 多用户支持（项目隔离、权限管理）
- [ ] Docker 容器化部署

---

## 技术债务

- [ ] `clipper.py` 中 `_merge_with_fade` 的 complex filter 需要更多边界测试
- [ ] ffmpeg 错误处理可以更精细（区分编码错误、格式不支持、磁盘空间不足）
- [ ] 配置文件缺少 schema 验证（建议用 pydantic 替代裸 dict）

---

## 已完成的历史记录

### Smart Clip Engine v2.0（2026-06-25 完成）

四层架构：AI 内容理解 → 规则引擎 → 策略引擎 → 最终优化

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

**流水线：**
```
Video → FFmpeg extract → 16kHz mono WAV → Audio chunking (15min + 10s overlap)
  → Whisper batch (per chunk) → Global timestamp normalization
  → Segment-level overlap dedup → Final TranscriptResult
```

**真实验证：** 140 分钟电影全流程（10 chunks，7171 segments，6 个亮点）

---

### Web 控制台（2026-06-25 启动，2026-06-28 完成核心功能）

**技术栈：** FastAPI + Next.js 16 + TypeScript + TailwindCSS + Zustand + React Flow + next-intl

**已完成功能：**
- Dashboard（任务概览、快速创建）
- Workflow Builder（React Flow DAG、8 阶段节点、schema 驱动表单）
- Scene Explorer（TanStack Table、tag/score/search 筛选、行内编辑）
- Run Console（SSE 实时日志、阶段状态、重试）
- 预设管理（CRUD、复制、Prompt 编辑器）
- 设置页面（外观主题、本地/在线 LLM 配置、config.yaml 同步）
- 文件浏览器（驱动器列表、目录导航、视频过滤）
- 任务持久化（data/tasks.json）
- 批量删除（复选框、输出文件可选删除）
- 全局 SSE（所有页面实时接收任务状态变更）
- 国际化（前后端 zh/en）
