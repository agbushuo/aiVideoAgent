# VideoAgent Web UI 迁移方案：NiceGUI → Next.js + React Flow

## Context

当前 Web UI 使用 NiceGUI，存在三个问题：
1. NiceGUI 路由未正确挂载到 FastAPI（根路径 404）
2. NiceGUI 适合简单后台面板，不适合复杂交互（DAG 编排、时间轴编辑）
3. 用户需要 Workflow-first + Timeline-first 的混合编辑器

目标：用 Next.js 前端替换 NiceGUI，保留 FastAPI 后端，实现三视图系统（Workflow / Scenes / Timeline）。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端框架 | Next.js 14 (App Router) + TypeScript |
| 样式 | TailwindCSS |
| 状态管理 | Zustand |
| 请求缓存 | @tanstack/react-query |
| DAG 编排 | @xyflow/react (React Flow) |
| 时间轴 | react-konva + konva |
| 拖拽 | @dnd-kit/core |
| Schema 校验 | Zod |
| 后端 | FastAPI（保留，扩展 API） |
| 实时推送 | SSE（Server-Sent Events） |

---

## 一、项目结构

```
aiVideoAgent/
├── src/                              # 现有 Python 后端（保留）
├── frontend/                         # 新增：Next.js 应用
│   ├── src/
│   │   ├── app/                      # App Router 页面
│   │   ├── components/               # React 组件
│   │   ├── lib/                      # API 客户端、工具函数
│   │   ├── stores/                   # Zustand 状态
│   │   ├── hooks/                    # 自定义 Hooks
│   │   └── types/                    # TypeScript 类型定义
│   ├── package.json
│   ├── next.config.js                # /api 代理到 8501
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── config.yaml
├── start.bat                         # 更新为同时启动两个服务
└── pyproject.toml                    # 最终移除 nicegui 依赖
```

---

## 二、后端 API 扩展

### 2.1 新增端点（`src/web/app.py`）

**任务管理：**
- `POST /api/tasks` — 创建任务（接收 pipeline_config 含阶段开关和参数）
- `DELETE /api/tasks/{task_id}` — 删除任务
- `POST /api/tasks/{task_id}/rerun-stage` — 重跑指定阶段

**阶段级执行：**
- `POST /api/tasks/{task_id}/stages/{stage_id}/run` — 执行单个阶段
- `GET /api/tasks/{task_id}/stages` — 查询所有阶段状态
- `GET /api/tasks/{task_id}/stages/{stage_id}` — 查询阶段详情和产物

**Scene / Candidate 数据：**
- `GET /api/tasks/{task_id}/scenes` — 场景列表（支持 ?tag=&min_score=&search=）
- `GET /api/tasks/{task_id}/scenes/{scene_id}` — 单个场景
- `PUT /api/tasks/{task_id}/scenes/{scene_id}` — 手动修改标签/评分
- `GET /api/tasks/{task_id}/candidates` — 候选列表（支持 ?sort=&order=）
- `PATCH /api/tasks/{task_id}/candidates/bulk-select` — 批量选中/取消

**字幕：**
- `GET /api/tasks/{task_id}/transcript` — 获取字幕片段
- `PUT /api/tasks/{task_id}/transcript` — 保存修改后的字幕

**配置参考数据：**
- `GET /api/config/presets` — 返回 `["douyin", "youtube", "bilibili", "viral", "all"]`
- `GET /api/config/clip-modes` — 返回 `["comedy", "action", "emotion", "dialogue", "knowledge", "hook", "viral", "all"]`
- `GET /api/config/scene-types` — 返回 `["Dialogue", "Comedy", "Fight", ...]`
- `GET /api/config/score-dimensions` — 返回 `["hook", "emotion", "comedy", ...]`
- `GET /api/config/pipeline-stages` — 返回 DAG 定义（节点、边、默认参数）
- `GET /api/config/weights` — 返回 weights.json 完整内容
- `GET /api/config/duration-templates` — 返回 `["60s", "90s", "180s", "300s"]`

**文件：**
- `GET /api/files/{path:path}/thumbnail` — 生成指定时间点的缩略图

**实时推送：**
- `GET /api/events?task_id=xxx` — SSE 事件流

### 2.2 TaskManager 改造（`src/web/task_manager.py`）

新增数据结构：

```python
@dataclass
class PipelineStageConfig:
    stage_id: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class StageResult:
    stage_id: str
    status: str          # pending | running | completed | failed | skipped
    started_at: float | None
    completed_at: float | None
    duration_seconds: float | None
    output_artifacts: dict[str, str]  # 产物文件路径
    error: str | None
```

PipelineTask 新增字段：
- `pipeline_stages: list[PipelineStageConfig]`
- `stage_results: dict[str, StageResult]`
- `intermediate_artifacts: dict[str, Any]`  # scenes, candidates 缓存

TaskManager 新增方法：
- `async run_stage(task, stage_id) -> StageResult` — 单阶段执行
- `async event_iter()` — SSE 事件生成器

### 2.3 新增文件

- `src/web/sse.py` — SSE 连接管理、事件广播
- `src/web/api_schemas.py` — Pydantic 请求/响应模型
- `src/web/stage_executor.py` — 阶段调度器，将 stage_id 映射到现有 pipeline 函数

### 2.4 SSE 事件协议

```
event: task_status
data: {"task_id": "abc", "status": "scoring", "percent": 72}

event: stage_start
data: {"task_id": "abc", "stage_id": "scoring", "stage_name": "Score Engine"}

event: stage_complete
data: {"task_id": "abc", "stage_id": "scoring", "artifacts": {...}, "duration": 12.3}

event: log
data: {"task_id": "abc", "level": "info", "message": "...", "stage": "scoring"}

event: progress
data: {"task_id": "abc", "step": "scoring", "step_detail": "...", "percent": 72}

event: error
data: {"task_id": "abc", "stage_id": "llm_annotation", "error": "..."}

event: pause
data: {"task_id": "abc", "reason": "subtitle_review", "message": "..."}

event: complete
data: {"task_id": "abc", "output_files": {...}}
```

---

## 三、前端架构

### 3.1 页面结构

| 路由 | 页面 | 说明 |
|---|---|---|
| `/` | Dashboard | 最近任务、快速创建 |
| `/tasks` | Task List | 任务列表（筛选、排序） |
| `/tasks/[id]` | **Task Workspace** | 主编辑器（三视图切换） |
| `/projects` | Projects | 项目管理 |

### 3.2 Task Workspace 布局

```
┌──────────────────────────────────────────────────┐
│ TopBar: Project Name | Run | Stop | Export       │
├──────────┬─────────────────────────┬──────────────┤
│ Sidebar  │     Main Canvas         │ Config Panel │
│          │                         │ (右侧，可选) │
│ Projects │  [Workflow View]        │  节点参数编辑 │
│ Presets  │  [Scene Explorer]       │              │
│ Runs     │  [Timeline Editor]      │              │
│          │  [Run Console]          │              │
└──────────┴─────────────────────────┴──────────────┘
```

### 3.3 Zustand Store 设计

**`workflowStore.ts`** — React Flow DAG 状态
```typescript
interface WorkflowState {
  nodes: PipelineNode[];
  edges: PipelineEdge[];
  selectedNodeId: string | null;
  toggleStage: (stageId: string) => void;
  reorderStages: (from: number, to: number) => void;
  updateStageParams: (stageId: string, params: Record<string, unknown>) => void;
  loadFromTask: (task: Task) => void;
  exportConfig: () => PipelineConfig;
}
```

**`sceneStore.ts`** — 场景数据 + 筛选
```typescript
interface SceneState {
  scenes: Scene[];
  candidates: ClipCandidate[];
  filters: { tags: string[]; minScore: number; searchQuery: string };
  sortBy: 'score' | 'start';
  selectedSceneIds: Set<number>;
  fetchScenes: (taskId: string) => Promise<void>;
  toggleSceneSelection: (sceneId: number) => void;
}
```

**`timelineStore.ts`** — 时间轴编辑
```typescript
interface TimelineState {
  clips: TimelineClip[];
  tracks: TimelineTrack[];
  zoom: number;           // 像素/秒
  playheadPosition: number;
  isPlaying: boolean;
  addClip: (scene: Scene) => void;
  removeClip: (clipId: string) => void;
  moveClip: (clipId: string, newStart: number) => void;
  resizeClip: (clipId: string, newStart: number, newEnd: number) => void;
  mergeClips: (clipIds: string[]) => void;
  exportTimeline: () => TimelineExport;
}
```

**`taskStore.ts`** — 任务 + SSE
```typescript
interface TaskState {
  currentTask: Task | null;
  tasks: Task[];
  stageResults: Record<string, StageResult>;
  sseConnected: boolean;
  createTask: (config: TaskCreateConfig) => Promise<string>;
  connectSSE: (taskId?: string) => void;
  handleSSEEvent: (event: SSEEvent) => void;
}
```

**`configStore.ts`** — 参考数据缓存
```typescript
interface ConfigState {
  presets: Preset[];
  clipModes: ClipMode[];
  sceneTypes: string[];
  scoreDimensions: ScoreDimension[];
  weights: Record<string, Record<string, number>>;
  loadAll: () => Promise<void>;
}
```

### 3.4 React Flow 节点定义

```typescript
// 8 个阶段节点
const STAGES = [
  { id: 'transcribe', label: '转录', icon: 'mic' },
  { id: 'scene_detection', label: '场景检测', icon: 'scissors' },
  { id: 'llm_annotation', label: 'LLM 标注', icon: 'brain' },
  { id: 'scoring', label: '评分引擎', icon: 'star' },
  { id: 'filtering', label: '筛选引擎', icon: 'filter' },
  { id: 'duration_planning', label: '时长规划', icon: 'clock' },
  { id: 'final_review', label: '最终评审', icon: 'check' },
  { id: 'clipping', label: 'FFmpeg 剪辑', icon: 'film' },
];

// 节点数据包含：enabled, status, params, duration
// 边连接反映 DAG 执行顺序
// 用户可拖拽排序、开关阶段、点击编辑参数
```

### 3.5 Konva.js 时间轴数据模型

```typescript
interface TimelineClip {
  id: string;
  sceneId: number;
  trackId: string;
  start: number;     // 源视频起始时间
  end: number;       // 源视频结束时间
  position: number;  // 时间轴位置（秒）
  color: string;     // 按 scene_type 着色
  label: string;
  score: number;
  tags: string[];
}

// Konva Layer 结构：
// Layer 0: 背景网格 + 时间标尺
// Layer 1: Track 背景
// Layer 2: Clip 矩形（可拖拽、可缩放）
// Layer 3: Playhead（红色竖线）
// Layer 4: 选中手柄 + Tooltip
```

### 3.6 右侧 Config Panel

Schema 驱动的表单 UI，根据选中的节点动态渲染：

```typescript
const stageSchemas = {
  transcribe: { language: 'select', model_name: 'text', device: 'select' },
  scene_detection: { gap_threshold: 'slider', min_scene_duration: 'number', ... },
  scoring: { preset: 'select', clip_mode: 'select' },
  filtering: { max_clips: 'number', min_gap: 'slider' },
  // ... 每个阶段对应不同的表单控件
};
```

---

## 四、实施阶段

### Phase 1：后端 API 扩展（2 周）
- **修改** `src/web/app.py` — 新增所有 REST 端点 + SSE
- **修改** `src/web/task_manager.py` — StageResult、PipelineStageConfig、run_stage()
- **新增** `src/web/sse.py` — SSE 事件流
- **新增** `src/web/api_schemas.py` — Pydantic 模型
- **新增** `src/web/stage_executor.py` — 阶段调度器
- NiceGUI 保持不变（开发期间两套并存）

### Phase 2：Next.js 脚手架 + App Shell（1 周）
- `npx create-next-app@latest frontend` + 安装所有依赖
- App Shell 布局（TopBar + Sidebar + MainCanvas）
- Dashboard 页面（最近任务列表）
- API 代理配置（next.config.js /api → localhost:8501）
- 所有 TypeScript 类型定义

### Phase 3：Workflow Builder（2 周）
- React Flow 画布 + 自定义 PipelineNode
- 阶段开关、拖拽排序
- 右侧 Config Panel（schema 驱动）
- Run Pipeline 按钮 → POST /api/tasks

### Phase 4：Scene Explorer（1 周）
- 场景数据表格（TanStack Table）
- Tag 筛选、Score 排序、搜索
- 选中场景 → 添加到时间轴

### Phase 5：Timeline Editor（2 周）
- Konva.js 时间轴画布
- Clip 拖拽、缩放、合并、删除
- 时间标尺、Playhead、缩放控制

### Phase 6：Run Console（1 周）
- CI/CD 风格执行视图
- SSE 实时日志
- 阶段状态、重试按钮

### Phase 7：集成测试（1 周）
- 端到端全流程测试
- 字幕审核流程验证

### Phase 8：替换 NiceGUI（0.5 周）
- **删除** `src/web/ui.py`
- **修改** `src/web/app.py` — 移除 NiceGUI 相关代码
- **修改** `pyproject.toml` — 移除 nicegui 依赖
- **修改** `start.bat` — 同时启动两个服务

---

## 五、start.bat 最终形态

```batch
@echo off
chcp 65001 >nul
echo ========================================
echo   VideoAgent - Starting Services
echo ========================================

set PYTHON=C:\Users\Administrator\.conda\envs\ai-video\python.exe

echo [1/2] Backend: http://127.0.0.1:8501
start "VideoAgent Backend" %PYTHON% -c "from src.web.app import run; run()"

echo [2/2] Frontend: http://localhost:3000
timeout /t 3 /nobreak >nul
cd /d %~dp0frontend
start "VideoAgent Frontend" cmd /k "npm run dev"

echo ========================================
pause
```

---

## 六、关键文件清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/web/app.py` | 大幅扩展 | 新增 20+ API 端点 + SSE |
| `src/web/task_manager.py` | 扩展 | 阶段级执行支持 |
| `src/web/ui.py` | 删除（Phase 8） | NiceGUI UI，不再需要 |
| `src/web/sse.py` | 新增 | SSE 事件流 |
| `src/web/api_schemas.py` | 新增 | 请求/响应模型 |
| `src/web/stage_executor.py` | 新增 | 阶段调度器 |
| `frontend/` | 新增 | 整个 Next.js 应用 |
| `start.bat` | 修改 | 双服务启动 |
| `pyproject.toml` | 修改 | 移除 nicegui |

---

## 七、管线断点续跑（跳过已有转录）— 待实现

> **背景：** 管线在转录后阶段（Scene Detection）因 bug 失败，修复后重新跑管线需要重新转录（~42min）。需要支持加载已有转录文件，从分析阶段继续。

### 实现方案

**后端：**
1. `src/web/api_schemas.py` — `TaskCreateRequest` 新增 `skip_existing_transcript: bool = False`
2. `src/web/task_manager.py` — `PipelineTask` 新增同名字段
3. `src/web/pipeline_runner.py` — 转录阶段前检查 `outputs/{stem}/subtitles/{stem}.json`
   - 存在且启用 → `TranscriptResult.from_json()` 加载，跳过 Whisper
   - 字幕审核暂停点保留不变
4. `src/web/pipeline_runner.py` — 异常日志追加完整 traceback（已修复）

**前端：**
5. `frontend/src/types/api.ts` — `TaskCreateRequest` 添加 `skip_existing_transcript?: boolean`
6. `frontend/src/components/workflow/WorkflowBuilder.tsx` — 添加"跳过已有转录"复选框
7. `messages/zh.json` + `messages/en.json` — `workflow.skipTranscribe` 翻译键

**已修复的关联 bug：**
- `src/clip_engine/scene_detector.py` — `_split_long_scenes` 单个 segment 超过 max_duration 时 `IndexError`（已修复）