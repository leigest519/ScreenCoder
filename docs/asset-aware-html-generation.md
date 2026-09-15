# Asset-Aware HTML Generation Design

本文档定义 ScreenCoder 如何从“截图转 HTML”升级为“资产感知的截图转 HTML”。目标是让 ScreenCoder 能识别复杂游戏 UI 中的旧纸、金属边框、铆钉、朱印、挂签、角色框和插图等装饰资产，并把它们映射到可复用的 Web/Godot UI 组件语义，而不是只生成普通 `div`、Tailwind class 和灰色图片占位。

## 背景

当前流水线主要覆盖三类能力：

- `block_parsor.py`：让视觉模型框出大区域，例如 sidebar、header、navigation、main content。
- `html_generator.py`：针对区域截图生成 HTML/Tailwind 片段。
- `image_box_detection.py`、`UIED/run_single.py`、`mapping.py`、`image_replacer.py`：找出 HTML 中的灰色图片占位，将其映射到原图 UIED 检测框，并裁剪替换为真实图片。

这套流程适合普通网页截图，但对游戏主菜单、HUD、RPG 面板等复杂 UI 会遇到三个问题：

- 纸张破损、金属边框、铆钉、红绳、朱印等装饰不是普通内容块，不能只靠 `border`、`shadow` 和背景色稳定复现。
- 现有替换逻辑只识别 `.bg-gray-400` 占位块，无法表达“这个边框应该用 NinePatch/StyleBoxTexture 资产”。
- 生成 HTML 缺少组件语义，后续无法可靠移交到 `web-ui-reference` 或 Godot。

## 目标

- 对输入截图输出结构化 UI schema，包含页面、语义区、组件 prefab、资产角色和内容字段。
- 将截图中的复杂装饰分为三类：可程序化 CSS、可裁剪位图、需引用设计资产库。
- 让生成 HTML 引用稳定组件语义，例如 `ornate-action-plaque`、`paper-panel`、`brass-plate`、`red-seal`。
- 保留当前研究型流水线的快速原型能力，同时新增可审计、可回归的资产感知路径。
- 与 `web-ui-reference` 分工清楚：ScreenCoder 负责识别、裁剪、映射和生成初稿；`web-ui-reference` 负责资产治理、组件实现、视觉回归和 Godot 合同。

## 非目标

- 不在 ScreenCoder 内维护完整设计系统。
- 不把外部资产包、许可证、Storybook 或 Godot Theme 合同放到本仓库长期治理。
- 不要求自动生成达到像素级一致；像素级或艺术级修正应进入 `web-ui-reference` 的组件和截图回归流程。
- 不把游戏运行时状态、Godot `.tscn` 或业务逻辑复制到 ScreenCoder。

## 目标架构

```text
input screenshot
  -> optional hosted OCR text detection
  -> layout detection
  -> semantic region classification
  -> asset role detection
  -> component schema generation
  -> optional source crop extraction
  -> HTML preview generation
  -> visual diff and handoff package
```

### Optional Hosted OCR

ScreenCoder can enrich schema region `content` with OCR text and OCR boxes before writing preview/handoff files. The current preferred hosted open-source-model option is PaddleOCR PP-OCRv4 on Replicate:

- Provider flag: `--ocr-provider replicate_paddleocr`
- Required manual gate: `REPLICATE_API_TOKEN`
- Output shape normalized internally to `{provider, text, blocks[]}` where each block has `text`, `bbox`, optional `confidence`, and optional `polygon`.

Additional experimental/fallback providers are available through the same abstraction:

- `--ocr-provider hf_ocr`: Hugging Face hosted open-model OCR, gated by `HF_TOKEN`; useful for plain text but often lacks boxes.
- `--ocr-provider ocr_space`: OCR.space hosted fallback, gated by `OCR_SPACE_API_KEY`; practical but not open-source.

If a provider is requested but its credential is missing, ScreenCoder keeps generating the non-OCR preview package and writes the manual gate into handoff notes instead of failing the whole run.

### Stage 1: Layout Detection

继续复用 `block_parsor.py` 的大区域识别能力，但 prompt 不应固定在普通网页区域。新 prompt 应允许输出游戏 UI 区域，例如：

- `title-stack`
- `primary-actions`
- `recent-run-panel`
- `quick-links`
- `corner-system-actions`
- `background-ornament`

输出仍使用归一化 bbox，但需要增加 `confidence`、`reason` 和 `expected_component`。

### Stage 2: Semantic Region Classification

新增语义分类，让每个区域有明确职责。

示例输出：

```json
{
  "id": "primary-actions",
  "label": "继续旅程 / 新的旅程",
  "bbox": [88, 260, 918, 520],
  "component_prefab": "ornate-action-plaque",
  "content_priority": "L0-primary-action",
  "asset_roles": ["paper-panel", "brass-plate", "ornate-border", "red-seal", "corner-rivet"]
}
```

### Stage 3: Asset Role Detection

资产检测不是简单 OCR 或 UIED 检测。它需要把视觉元素映射到可复用资产角色。

初始角色集合应对齐 `web-ui-reference`：

- `ritual-background`
- `ornate-border`
- `paper-panel`
- `brass-plate`
- `red-seal`
- `corner-rivet`
- `symbolic-icon`
- `portrait-frame`
- `quick-card-illustration`
- `title-logotype`
- `ink-divider`
- `blood-smear`
- `rope-knot`
- `hanging-tag`
- `progress-petal`
- `damage-scratch`

每个角色输出 `strategy`：

| Strategy | Meaning | Example |
| --- | --- | --- |
| `css-procedural` | 可用 CSS 渐变、阴影、伪元素模拟 | 暗角、噪点、普通纸纹 |
| `crop-source` | 从源图裁剪可复用片段 | 角色头像、底部卡片插图 |
| `reference-asset` | 应引用外部/内部资产库 | 金属九宫格边框、铆钉、挂签 |
| `manual-art` | 需要人工或图像生成资产 | 手写题字、复杂插画 |

### Stage 4: Component Schema Generation

新增 ScreenCoder 输出，不直接只产 HTML。

建议文件：

```text
data/run/<case>/screen-schema.json
data/run/<case>/asset-crops/
data/run/<case>/preview.html
data/run/<case>/handoff.md
```

`screen-schema.json` 示例：

```json
{
  "page_type": "game-main-menu",
  "viewport": { "width": 820, "height": 1600 },
  "theme_hint": "japanese-horror",
  "template_hint": "ornamental-mobile",
  "regions": [
    {
      "id": "primary-actions",
      "prefab": "ornate-action-plaque",
      "bbox": [64, 410, 756, 840],
      "content": {
        "primary_title": "继续旅程",
        "secondary_title": "新的旅程",
        "subtitle": "返回当前的破宫之旅"
      },
      "asset_roles": [
        { "role": "paper-panel", "strategy": "reference-asset" },
        { "role": "brass-plate", "strategy": "reference-asset" },
        { "role": "red-seal", "strategy": "css-procedural" }
      ]
    }
  ]
}
```

### Stage 5: HTML Preview Generation

HTML 预览分两种模式：

| Mode | Use case | Output |
| --- | --- | --- |
| `standalone` | 快速查看生成效果 | 单文件 `preview.html`，内联 CSS 和裁剪图 |
| `component-reference` | 移交 `web-ui-reference` | 输出组件/slot schema，不复制组件实现 |

`standalone` 可以继续用 `html_generator.py` 生成，但 prompt 应要求按 prefab 生成，而不是按 `sidebar/header/navigation/main content` 生成。

`component-reference` 应生成可导入 `web-ui-reference` 的候选配置，例如：

```json
{
  "composition": "horror-ornamental",
  "prefabs": ["ritual-title-stack", "ornate-action-plaque", "journey-status-panel", "relic-quick-card"],
  "missing_assets": ["ornate-border", "brass-plate", "portrait-frame"]
}
```

## 与 web-ui-reference 的边界

ScreenCoder 输出的资产角色和 prefab 必须对齐 `web-ui-reference` 的命名。推荐边界：

| Responsibility | ScreenCoder | web-ui-reference |
| --- | --- | --- |
| 从截图识别区域 | Yes | No |
| 从截图裁剪候选素材 | Yes | Optional review only |
| 维护资产许可证 | No | Yes |
| 定义 NinePatch/StyleBoxTexture | No | Yes |
| 实现可复用组件 | No | Yes |
| 生成一次性 HTML 预览 | Yes | Optional |
| Storybook/Playwright 回归 | No | Yes |
| Godot handoff contract | Draft only | Source of truth |

ScreenCoder 的 handoff 文档只应说明“识别到了什么”和“建议映射到什么”，最终合同由 `web-ui-reference` 管理。

## 新增模块建议

```text
asset_roles.py
component_schema.py
screen_to_schema.py
schema_to_html.py
handoff_writer.py
```

### `asset_roles.py`

维护 ScreenCoder 侧可识别资产角色的轻量枚举。该文件应从 `web-ui-reference` 的文档或导出 JSON 同步，不应自行发明不同命名。

### `component_schema.py`

定义 Pydantic 或 dataclass schema，用于约束 region、component、asset role、crop 和 handoff。

### `screen_to_schema.py`

新主入口，负责把截图转成 `screen-schema.json`。它可以复用当前 `block_parsor.py`、OCR、UIED 和视觉模型。

### `schema_to_html.py`

把 `screen-schema.json` 变成可打开的 `preview.html`。该模块只用于预览，不作为设计系统源代码。

### `handoff_writer.py`

生成 `handoff.md`，包含：

- 输入截图。
- 识别到的页面类型。
- 区域和 prefab 映射。
- 裁剪资产清单。
- 缺失资产角色。
- 建议在 `web-ui-reference` 中实现或补齐的组件。

## Prompt 改造

旧 prompt 关注“还原容器内 HTML/Tailwind”。新 prompt 应要求模型输出结构化 JSON，再由代码生成 HTML。

推荐 prompt 目标：

- 先识别页面类型和主任务。
- 再识别语义区域和交互优先级。
- 最后识别资产角色及生成策略。
- 不要求模型凭空生成复杂纹理；复杂纹理必须标记为 `reference-asset` 或 `manual-art`。

## 评估指标

### 结构评估

- 主区域 bbox 是否覆盖正确。
- prefab 分类是否正确。
- 文案 OCR/视觉识别是否足够支撑内容模型。
- 主行动、次行动、状态面板和底部入口是否层级清楚。

### 资产评估

- 资产角色召回率。
- `css-procedural`、`crop-source`、`reference-asset` 分类是否合理。
- 裁剪图是否可用，是否包含过多背景或文字。

### 视觉评估

- Playwright 截图与源图的粗粒度布局差异。
- 主操作可发现性。
- 文字可读性。
- 装饰是否误导为可点击区域。

## 实施阶段

### Phase 1: Schema First

- 新增 `screen_to_schema.py`。
- 将 `block_parsor.py` 的输出转换为区域 schema。
- 手工配置一组游戏 UI prefab 和 asset roles。
- 输出 `screen-schema.json` 和 `handoff.md`。

### Phase 2: Asset Role Detection

- 增加资产角色识别 prompt。
- 识别 `paper-panel`、`brass-plate`、`red-seal`、`ornate-border`、`portrait-frame`。
- 输出每个资产角色的推荐策略。

### Phase 3: Preview HTML

- 新增 `schema_to_html.py`。
- 生成一版 standalone HTML 预览。
- 对 `crop-source` 资产生成 `asset-crops/`。

### Phase 4: Reference Handoff

- 输出可被 `web-ui-reference` 读取的 JSON。
- 在 handoff 中列出缺失组件和缺失资产。
- 与 `web-ui-reference` 的 Storybook/Playwright 验收对接。

## 风险

- VLM 对装饰资产的语义识别不稳定，需要 schema 校验和人工修正入口。
- 直接裁剪原图可能包含版权或混合背景，不应默认进入长期资产库。
- 如果 ScreenCoder 内部实现完整组件系统，会与 `web-ui-reference` 分叉，导致重复维护。
- 过度追求像素级自动复现会拖慢研究迭代；本项目应优先输出可移交的结构化初稿。

## 验收标准

- 给定一张复杂游戏主菜单截图，能输出 `screen-schema.json`。
- `screen-schema.json` 至少包含标题区、主行动区、状态面板、快捷入口四类区域。
- 每类区域能映射到 prefab 和 asset roles。
- `handoff.md` 能清楚列出哪些资产应由 `web-ui-reference` 维护。
- standalone `preview.html` 可打开，并保留主要信息层级。
