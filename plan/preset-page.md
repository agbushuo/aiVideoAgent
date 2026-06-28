# 预设界面实现方案

## 背景

用户需要一个预设管理界面，可以：
1. 分别配置 Workflow 各阶段参数并保存为预设
2. 编辑各预设使用的 LLM Prompts
3. 数据保存到 `data/presets.json` 本地文件

目前 `/presets` 路由已在侧边栏链接，但页面不存在。评分权重已有 `weights.json` 管理，Prompt 模板在 `prompts/` 目录。需要把这三者整合为可管理的"预设"。

## 预设数据结构

```typescript
interface PresetData {
  name: string;           // 唯一标识，如 "douyin"
  displayName: string;    // 显示名称，如 "抖音爆款"
  description: string;    // 描述
  stageParams: Record<string, Record<string, unknown>>;  // { transcribe: { language: "zh" }, scoring: { preset: "douyin" }, ... }
  weights: Record<string, number>;  // 自定义评分权重（可选，覆盖默认）
  prompts: Record<string, string>;  // { scene_analysis: "...", final_review: "..." } 每个预设可覆盖默认 prompt
}
```

## 实现步骤

### 1. 后端：预设管理 API

**新增 `src/web/preset_manager.py`**
- `PresetManager` 单例类
- `data/presets.json` 持久化（类似 TaskManager 的 save/load 模式）
- 方法：`list()`, `get(name)`, `save(preset)`, `delete(name)`
- 同时管理 `prompts/` 目录下的 Prompt 文件：
  - `list_prompts()` 返回可用 prompt 文件名
  - `get_prompt(name)` 读取 prompt 内容
  - `save_prompt(name, content)` 写入 prompt 文件

**新增 API 端点（`src/web/app.py`）**
- `GET /api/presets` — 列出所有预设
- `GET /api/presets/{name}` — 获取预设详情
- `PUT /api/presets/{name}` — 创建/更新预设
- `DELETE /api/presets/{name}` — 删除预设
- `GET /api/prompts` — 列出可用 Prompt 模板
- `GET /api/prompts/{name}` — 获取 Prompt 内容
- `PUT /api/prompts/{name}` — 更新 Prompt 内容

### 2. 前端：类型和 API 客户端

**更新 `frontend/src/types/config.ts`**
- 新增 `PresetData` 接口

**更新 `frontend/src/lib/api.ts`**
- `listPresets()`, `getPreset(name)`, `savePreset(preset)`, `deletePreset(name)`
- `listPrompts()`, `getPrompt(name)`, `savePrompt(name, content)`

### 3. 前端：预设页面

**新增 `frontend/src/app/presets/page.tsx`**

布局：
- 左侧：预设列表（卡片式，显示名称、描述、权重摘要）
- 右侧：编辑区（选中预设后显示）

编辑区包含标签页：
- **管线参数** — 按阶段分组显示参数表单（复用 ConfigPanel 的逻辑，读取 `BASE_STAGE_SCHEMAS`）
  - 转录：语言、模型、设备
  - 场景检测：间隙阈值、最小时长、最长时间
  - 评分：预设、剪辑模式
  - 筛选：最大片段数、最小间隔、目标时长
  - 时长规划：目标时长
  - 最终评审：精选数量
  - 剪辑：合并片段、转场时长
- **评分权重** — 8 维评分滑块（hook, emotion, comedy, action, information, suspense, climax, viral）
- **Prompt 模板** — 列出该预设关联的 Prompt，点击可编辑（scene_analysis, final_review）
- **操作栏** — 保存、复制、删除

**新增 `frontend/src/components/presets/PresetList.tsx`** — 预设列表组件
**新增 `frontend/src/components/presets/PresetEditor.tsx`** — 预设编辑器（含标签页）
**新增 `frontend/src/components/presets/PromptEditor.tsx`** — Prompt 编辑器（代码编辑器样式）

### 4. i18n

**更新 `messages/zh.json` 和 `messages/en.json`**
- 新增 `presets` 命名空间：标题、描述、标签页名、按钮文本等

### 5. 初始化默认预设

首次加载时，如果 `data/presets.json` 不存在，从现有 `weights.json` 的 preset 部分自动生成默认预设条目（douyin, youtube, bilibili, viral, all），权重取自 weights.json，stageParams 使用默认值。

## 关键文件

| 文件 | 操作 |
|------|------|
| `src/web/preset_manager.py` | 新增 |
| `src/web/app.py` | 更新 — 新增 API 端点 |
| `frontend/src/app/presets/page.tsx` | 新增 |
| `frontend/src/components/presets/PresetList.tsx` | 新增 |
| `frontend/src/components/presets/PresetEditor.tsx` | 新增 |
| `frontend/src/components/presets/PromptEditor.tsx` | 新增 |
| `frontend/src/types/config.ts` | 更新 — 新增 PresetData 类型 |
| `frontend/src/lib/api.ts` | 更新 — 新增 API 方法 |
| `messages/zh.json` | 更新 — 新增 presets 命名空间 |
| `messages/en.json` | 更新 — 新增 presets 命名空间 |
| `logs/CHANGELOG.md` | 更新 |

## 验证方式

1. 后端：`pytest tests/test_web_api.py` 确认 API 不报错
2. 前端：预览 `localhost:3000/presets` 页面
3. 点击侧边栏"预设"导航到预设页面
4. 创建新预设、编辑参数、修改 Prompt、保存后验证数据持久化
