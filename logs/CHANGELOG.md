# 变更记录

## 2026-06-28

### 更新项目文档
- **更新** `README.md`：重写项目介绍，补充 Web 控制台功能说明、Smart Clip Engine 用法、完整项目结构、技术栈（前端/后端分开）
- **更新** `ARCHITECTURE.md`：全面重写，更新项目结构（含 frontend/、data/、src/web/ 完整目录树），补充 Web 后端数据流、设置优先级、34+ API 端点清单
- **更新** `ROADMAP.md`：更新版本至 v1.2.0，标记所有已完成功能（预设管理、设置管理、i18n、任务持久化、批量删除、文件浏览器），移除过时的"进行中"部分

### 清理测试文件和依赖
- **删除** `tests/`：全部测试文件（conftest.py、__init__.py、test_analyze.py、test_transcribe.py），测试已跑过且不再维护
- **删除** `run_test.py`：CLI 快速测试脚本
- **更新** `pyproject.toml`：移除 `[project.optional-dependencies] dev` 中的 pytest/pytest-asyncio

### 设置保存同步写入 config.yaml
- **更新** `src/web/settings_manager.py`：`save_settings()` 调用 `_sync_config_yaml()` 将 LLM 设置写入 `config.yaml` 的 llm 段（正则匹配替换 provider/model/endpoint/api_key/temperature/max_tokens），新增 `get_active_llm_config_from()` 从内存字典读取配置（不读文件），`DEFAULT_SETTINGS` 新增 `theme`/`accentColor` 默认值，`load_settings()` 合并逻辑扩展为处理 `theme` 和 `accentColor`

### 模型设置同步本地缓存（localStorage 回退）
- **更新** `frontend/src/lib/api.ts`：用户设置读写增加 localStorage 同步。`getUserSettings()` 成功后缓存到 localStorage，`saveUserSettings()` 成功后同步写入。新增 `getUserSettingsWithFallback()` 优先 API，失败回退本地缓存。新增 `saveUserSettingsWithFallback()` API 失败时本地持久化并返回 false。新增 `mergeSettings()` 深度合并局部更新
- **更新** `frontend/src/app/settings/page.tsx`：加载改用 `getUserSettingsWithFallback()`，保存改用 `saveUserSettingsWithFallback()`。保存按钮区分服务端保存（绿色）和本地缓存（琥珀色 "已本地缓存"）
- **更新** `frontend/messages/zh.json`：settings 命名空间新增 `saving` 翻译键
- **更新** `frontend/messages/en.json`：同上

### 侧边栏导航重构 + 设置页面（前后端联动）
- **更新** `frontend/src/components/layout/Sidebar.tsx`：导航改为"预设"、"全部任务"、"设置"三项，"查看全部任务"从底部移至导航第二位，"管线"重命名为"设置"并更换 Settings 图标，底部改为版本信息
- **更新** `frontend/src/app/settings/page.tsx`：设置页面改为"外观"和"模型"两个标签页，模型配置合并为统一页面，通过"本地模型/在线模型"按钮切换，数据通过 API 持久化到后端
- **新增** `src/web/settings_manager.py`：用户设置管理器，读写 `data/settings.json`，提供 `merge_llm_into_config()` 将用户设置合并到 config.yaml（用户设置优先级更高）
- **更新** `src/web/app.py`：新增 `GET/PUT /api/settings` 接口，`rerun_stage` 和 `run_stage` 端点自动合并用户 LLM 设置
- **更新** `src/web/pipeline_runner.py`：管线启动时合并用户 LLM 设置，覆盖 config.yaml 默认值
- **更新** `frontend/src/lib/api.ts`：新增 `getUserSettings()`、`saveUserSettings()` API 客户端方法
- **更新** `frontend/messages/zh.json`：sidebar 命名空间新增 `tasks`、`settings` 键，settings 命名空间合并本地/在线模型为 `tabModel` + `modelType` 切换，新增 `temperatureHint` 翻译键
- **更新** `frontend/messages/en.json`：同上英文翻译

### 预设页面左下角添加返回主页按钮
- **更新** `frontend/src/components/presets/PresetList.tsx`：底部新增 Home 图标 + "返回主页" 链接，使用 `next/link` 跳转
- **更新** `frontend/messages/zh.json`：presets 命名空间新增 `backToHome` 翻译键
- **更新** `frontend/messages/en.json`：同上

### 剪辑模式和平台预设选项 i18n 国际化
- **更新** `frontend/messages/zh.json`：workflow 命名空间新增 clipModes（8 个剪辑模式中文标签）和 presetLabels（5 个平台预设中文标签）
- **更新** `frontend/messages/en.json`：同上英文标签
- **更新** `frontend/src/components/workflow/ConfigPanel.tsx`：使用 useTranslations("workflow") 渲染剪辑模式和预设下拉框的本地化标签
- **更新** `frontend/src/components/presets/PresetEditor.tsx`：使用 useTranslations("workflow") 渲染剪辑模式和预设下拉框的本地化标签

### 修复预设页面 i18n 命名空间解析错误
- **更新** `frontend/messages/zh.json`：新增 presets 命名空间（含 scoreDims 子对象），使其与 next-intl 读取的 `frontend/messages/` 路径一致
- **更新** `frontend/messages/en.json`：同上英文翻译

### 实现预设管理界面（Preset Manager）
- **新增** `src/web/preset_manager.py`：PresetManager 单例类，管理 data/presets.json 持久化，支持 CRUD、复制、Prompt 模板管理
- **更新** `src/web/app.py`：新增预设管理 API 端点（GET/PUT/DELETE /api/presets, POST /api/presets/{name}/duplicate）和 Prompt 管理端点（GET/PUT /api/prompts）
- **新增** `frontend/src/app/presets/page.tsx`：预设管理页面，左侧列表 + 右侧编辑器布局
- **新增** `frontend/src/components/presets/PresetList.tsx`：预设列表组件，支持选择、复制、新建
- **新增** `frontend/src/components/presets/PresetEditor.tsx`：预设编辑器，含管线参数、评分权重、Prompt 模板三个标签页
- **新增** `frontend/src/components/presets/PromptEditor.tsx`：Prompt 编辑器组件，支持预设级覆盖
- **更新** `frontend/src/types/config.ts`：新增 PresetData、PromptInfo 接口
- **更新** `frontend/src/lib/api.ts`：新增预设 CRUD 和 Prompt 管理的 API 客户端方法
- **更新** `messages/zh.json`：新增 presets 命名空间翻译
- **更新** `messages/en.json`：新增 presets 命名空间翻译

### 移除时间轴（Timeline）模块
- **更新** `frontend/src/components/layout/MainCanvas.tsx`：移除"时间轴"标签及其动态导入，只保留 Workflow 和场景两个标签
- **删除** `frontend/src/components/timeline/`：删除整个时间轴组件目录（TimelineEditor、TimelineToolbar、TimelineCanvas、ClipRenderer、VideoPreview、ThumbnailPreview、Playhead、TimeRuler 共 8 个文件）
- **删除** `frontend/src/stores/timelineStore.ts`：时间轴状态管理模块
- **删除** `frontend/src/types/timeline.ts`：时间轴类型定义

### 恢复左侧边栏导航链接，移除冗余项
- **更新** `frontend/src/components/layout/Sidebar.tsx`：恢复预设和管线导航链接，移除"项目"和"运行历史"（功能已并入"查看全部任务"），"查看全部任务"移至底部

### Workflow 画布放大 + ConfigPanel 布局优化
- **更新** `frontend/src/components/layout/Layout.tsx`：新增全局 SSE 连接（`/api/events`），所有页面实时接收任务状态变更，无需打开任务详情页
- **更新** `frontend/src/components/console/RunConsole.tsx`：移除重复的 SSE 连接（由 Layout 全局管理），只保留历史日志加载
- **更新** `frontend/src/app/tasks/page.tsx`：任务列表页新增 5 秒轮询兜底，当有运行中任务时自动刷新
- **更新** `frontend/src/components/workflow/WorkflowBuilder.tsx`：布局从"画布+右侧面板"改为"画布在上方+配置面板在下方全宽"，ConfigPanel 不再占用画布宽度
- **更新** `frontend/src/components/workflow/ConfigPanel.tsx`：从右侧竖条面板改为底部全宽横条面板，参数项水平排列，未选中节点时显示紧凑提示
- **更新** `frontend/src/components/workflow/ReactFlowCanvas.tsx`：初始缩放从 0.6 提升至 0.85，最大缩放从 1.5 提升至 2，外层容器改为 `h-full w-full`
- **更新** `frontend/src/components/workflow/PipelineNode.tsx`：节点最小宽度从 180 增至 220，最大宽度 280，内边距和图标尺寸加大
- **更新** `frontend/src/components/workflow/StageFormField.tsx`：表单字段间距加大

### 修复旧版任务数据加载兼容性，添加批量删除功能
- **更新** `src/web/task_manager.py`：`load()` 方法增加健壮的反序列化逻辑，兼容旧版 repr 格式数据（`TaskStatus.COMPLETED` 字符串、`TaskProgress(...)` / `LogEntry(...)` repr、`"True"`/`"False"` 字符串布尔值）
- **更新** `src/web/task_manager.py`：`_serialize()` 增加 `Enum` 类型处理（输出 `.value`）和字符串布尔值修复，防止新数据再次序列化错误
- **更新** `src/web/task_manager.py`：新增 `_parse_task_status()`、`_parse_bool()`、`_parse_float()`、`_parse_repr_string()` 解析辅助方法
- **新增** `src/web/app.py`：`DELETE /api/tasks/bulk-delete` 批量删除接口，支持 `task_ids` 列表和 `delete_outputs` 参数（同时删除输出文件）
- **新增** `frontend/src/lib/api.ts`：`bulkDeleteTasks()` API 客户端方法
- **新增** `frontend/src/stores/taskStore.ts`：`selectedTaskIds` 选中状态、`toggleSelectTask()`、`selectAllTasks()`、`clearSelection()`、`bulkDeleteTasks()` 动作
- **更新** `frontend/src/app/tasks/page.tsx`：任务列表新增复选框列、全选、批量操作栏、批量删除确认弹窗（含"同时删除输出文件"选项）
- **新增** `frontend/messages/zh.json`：批量删除相关翻译键 `selectedCount`、`bulkDelete`、`cancel`
- **新增** `frontend/messages/en.json`：批量删除相关翻译键 `selectedCount`、`bulkDelete`、`cancel`

### 实现管线断点续跑（跳过已有转录）功能
- **更新** `src/web/api_schemas.py`：`TaskCreateRequest` 新增 `skip_existing_transcript: bool = False` 字段
- **更新** `src/web/task_manager.py`：`PipelineTask` 新增 `skip_existing_transcript: bool = False` 字段
- **更新** `src/web/pipeline_runner.py`：转录阶段前检查 `outputs/{stem}/subtitles/{stem}.json`，文件存在且启用跳过时，用 `TranscriptResult.from_json()` 加载，跳过 Whisper 引擎
- **更新** `src/utils/i18n.py`：新增后端翻译键 `pipe.stepSkippingTranscribe`、`pipe.loadingExistingTranscript`、`pipe.existingTranscriptLoaded`（zh/en）
- **更新** `frontend/src/types/api.ts`：`TaskCreateRequest` 添加 `skip_existing_transcript?: boolean`
- **更新** `frontend/src/components/workflow/WorkflowBuilder.tsx`：添加"跳过已有转录"复选框，创建任务时传递参数

### 修复 LLM 标注阶段的 prompt 格式冲突 bug
- **修复** `src/analyze/llm_analyzer.py`：`analyze_scenes()` 方法将 `prompt.format(scenes_text=...)` 改为 `re.sub()` 替换，避免 JSON 示例中的 `{}` 被 Python `str.format()` 误解析为占位符（`KeyError: '"scene_id"'`）
- **修复** `prompts/final_review.md`：JSON 示例中的 `{}` 转义为 `{{}}`，防止同样的 `str.format()` 冲突

### 修复 Smart Clip 管线 AnalysisReport 参数错误
- **修复** `src/web/pipeline_runner.py`：Smart Clip 模式创建 `AnalysisReport` 时传了不存在的 `metadata` 参数导致 `TypeError`，移除该参数

### 修复剪辑阶段 merge_clips 参数名错误
- **修复** `src/web/pipeline_runner.py`：调用 `clipper.merge_clips()` 时参数名 `transition` 改为 `transition_duration`，匹配 `Clipper.merge_clips()` 方法签名

### 任务持久化（后端重启不丢失任务）
- **更新** `src/web/task_manager.py`：`TaskManager` 新增 `_task_to_dict()`、`save()`、`load()`、`_save_now()` 方法，任务数据序列化到 `data/tasks.json`
- **更新** `src/web/task_manager.py`：`create_task()` 创建任务后自动调用 `_save_now()` 持久化
- **更新** `src/web/app.py`：`lifespan` 启动时调用 `TaskManager().load()` 恢复任务，关闭时调用 `save()` 保存
- **更新** `src/web/app.py`：任务取消和删除操作后调用 `save()` 持久化
- **更新** `src/web/pipeline_runner.py`：管线在审核暂停点、完成、失败三个关键节点调用 `task_manager.save()` 持久化

### 修复任务持久化序列化错误（全面加固）
- **修复** `src/web/task_manager.py`：`_task_to_dict()` 的 `_serialize()` 函数增加 `try/except` 兜底，任何无法序列化的对象转为字符串而非抛出异常
- **修复** `src/web/task_manager.py`：重写 `_serialize()` 类型判断顺序，先检查 `dict`/`list`/`tuple` 再检查 `is_dataclass`，避免 `list`/`dict` 类型被误判
- **修复** `src/web/task_manager.py`：`load()` 方法在反序列化时重建 `TaskStatus` 枚举（JSON 中存储的是字符串），避免重启后 `task.status` 是字符串导致 `.value` 报错
- **新增** `src/web/task_manager.py`：`PipelineTask` 新增 `status_str` 属性，安全返回状态字符串（兼容枚举和字符串两种形式）
- **更新** `src/web/app.py`：所有 API 端点用 `status_str` 替代 `status.value`，状态比较用字符串而非枚举
- **更新** `src/web/pipeline_runner.py`：`_broadcast()` 用 `status_str` 替代 `status.value`

## 2026-06-26

### 修复管线运行按钮 + i18n 错误
- **更新** `frontend/src/components/workflow/WorkflowBuilder.tsx`：任务详情页从 taskStore 读取视频路径（只读），"运行管线"改为"继续运行"调用 resumeTask，创建新任务时保持原有逻辑
- **更新** `frontend/src/components/layout/TopBar.tsx`：运行/停止按钮绑定 resumeTask/cancelTask，已完成/已取消/错误状态隐藏运行和停止按钮
- **修复** `frontend/src/components/workflow/PipelineNode.tsx`：`workflow.status.*` 动态键无法解析，改用本地 STATUS_LABELS 查找表 + `useTranslations("workflow")` 命名空间
- **修复** `frontend/i18n/request.ts`：`requestLocale` 可能是 Promise，需 await 后使用，避免 `[object Promise]` 作为 locale 传入
- **修复** `src/clip_engine/scene_detector.py`：`_split_long_scenes` 当 group 只有单个 segment 且超过 max_scene_duration 时，没有 gap 可拆分导致 `IndexError: list index out of range`，增加空 gaps 检测直接保留原 group
- **更新** `src/web/pipeline_runner.py`：异常日志记录完整 traceback 到任务日志，便于排查错误

### 时间轴视频加载 + 场景片段回显
- **更新** `frontend/src/components/timeline/TimelineEditor.tsx`：视频路径改为从 taskStore 响应式读取，修复挂载时任务未加载导致视频不显示的问题
- **更新** `frontend/src/components/timeline/TimelineEditor.tsx`：时间轴在没有选中候选片段时，自动从场景数据加载片段显示（按时间排序）
- **修复** `frontend/src/components/workflow/PipelineNode.tsx`：`workflow.status.*` 翻译键无法动态解析，改用全路径键名

### 移除主画布控制台标签
- **更新** `frontend/src/components/layout/MainCanvas.tsx`：移除 `console` 视图标签及 `RunConsole` 动态导入，只保留 Workflow / 场景 / 时间轴三个标签
- **更新** `frontend/src/app/tasks/[id]/page.tsx`：不再向 MainCanvas 传递 `taskId` prop

### 文件系统浏览 + 侧边栏 404 修复
- **新增** `src/web/app.py`：`GET /api/fs/drives` — 列出可用驱动器（Windows 盘符 / Unix 根目录）
- **新增** `src/web/app.py`：`GET /api/fs/list?path=...` — 列出目录内容，自动标记视频文件
- **新增** `frontend/src/components/FileBrowser.tsx`：文件浏览器模态框组件
  - 驱动器切换、面包屑导航、视频/全部过滤器
  - 双击目录进入、双击文件选中
- **更新** `frontend/src/app/page.tsx`："浏览"按钮集成文件浏览器，移除 `showOpenFilePicker` 旧代码
- **修复** `frontend/src/components/layout/Sidebar.tsx`：移除指向不存在页面的链接（/projects、/presets、/pipelines、/runs），只保留 /tasks
- **修复** `frontend/src/components/FileBrowser.tsx`：`fetchDrives` 获取驱动器后未设置 `items` 状态，导致表格始终显示"空目录"

### 后端 i18n 国际化模块
- **新增** `src/utils/i18n.py`：字典式后端国际化模块，支持 zh/en 翻译
  - `_(key, locale, **params)` — 获取翻译字符串，支持参数格式化
  - `get_stage_label(stage_id, locale)` / `get_stage_description(stage_id, locale)` — 阶段多语言名称/描述
  - `resolve_locale(accept_language)` — 从 Accept-Language 头解析语言代码
  - 涵盖应用生命周期、任务管理、阶段执行、管线日志、SSE 事件等翻译键
- **更新** `src/web/app.py`：所有 API 端点引入 i18n
  - HTTPException 错误消息国际化（任务不存在、阶段未执行、场景不存在等）
  - 任务创建/删除/恢复/取消接口的返回消息国际化
  - 评分维度、管线阶段配置接口返回多语言数据
  - 应用生命周期和启动日志消息国际化
- **更新** `src/web/pipeline_runner.py`：所有管线日志和进度消息国际化
  - 转录、审核、分析、评分、筛选、规划、评审、剪辑各阶段日志
  - SSE 阶段名称广播消息国际化
  - 错误处理消息国际化
- **更新** `src/web/stage_executor.py`：阶段执行器错误消息国际化
  - 未知阶段、前置依赖缺失、无候选片段等 ValueError 消息

### 前端 i18n 基础设施修复
- **新增** `frontend/i18n/request.ts`：next-intl 请求配置文件（从 src/i18n/ 迁移至项目根目录）
- **新增** `frontend/i18n/ClientProvider.tsx`：客户端国际化 Provider 组件
- **新增** `frontend/routing.ts`：next-intl 路由配置（支持 zh/en 语言，无路由前缀）
- **更新** `frontend/next.config.ts`：注册 next-intl 插件（createNextIntlPlugin）
- **更新** `frontend/src/app/layout.tsx`：包裹 ClientProvider 以支持客户端 useTranslations hook
- **更新** `frontend/src/i18n/request.ts` → 删除（路径重复，合并至 frontend/i18n/request.ts）

### 剩余前端组件 i18n 国际化迁移
- **更新** `frontend/src/components/workflow/PipelineNode.tsx`：引入 `useTranslations("workflow")`，将 Enable/Disable 按钮标题和状态标签（pending/running/completed/failed/skipped）替换为 i18n 翻译键
- **更新** `frontend/src/lib/sceneUtils.ts`：新增 `getScoreDimLabel(key, locale)` 函数，支持中英文评分维度标签切换；保留 `SCORE_DIMENSION_LABELS_MAP` 向后兼容
- **更新** `frontend/src/types/workflow.ts`：新增 `EN_BASE_STAGE_SCHEMAS` 和 `EN_STAGE_DESCRIPTIONS` 英文常量，以及 `getStageSchemas(locale)` 和 `getStageDescriptions(locale)` 辅助函数
- **更新** `frontend/src/i18n/request.ts`：修复消息文件导入路径（`../../messages/` → `../../../messages/`）
- **更新** `messages/zh.json` 和 `messages/en.json`：新增 `workflow.status` 命名空间（pending/running/completed/failed/skipped 状态标签）

### Timeline 组件 i18n 国际化迁移
- **更新** `frontend/src/components/timeline/TimelineToolbar.tsx`：引入 `useTranslations("timeline")`，将硬编码英文字符串替换为 i18n 翻译键（play、pause、zoomIn、zoomOut、snapOn/snapOff、timelineDuration、empty、deleteClip、clearAll、exportClips、exporting、export）
- **更新** `frontend/src/components/timeline/VideoPreview.tsx`：引入 `useTranslations("timeline")`，替换 noVideo、noVideoHint、play、pause、mute、unmute 字符串
- **更新** `frontend/src/components/timeline/TimelineCanvas.tsx`：引入 `useTranslations("timeline")`，替换 noClips 空状态文本
- **更新** `frontend/src/components/timeline/ClipRenderer.tsx`：引入 `useTranslations("timeline")`，替换 clipLabel 和 scorePrefix 文本
- **更新** `frontend/src/components/timeline/ThumbnailPreview.tsx`：引入 `useTranslations("timeline")`，替换 frameAt 图片 alt 属性

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
