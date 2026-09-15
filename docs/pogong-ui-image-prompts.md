# 破宫十重奏风格 UI 图像生成 Prompt Pack

用途：为 ScreenCoder 生成多种游戏 UI 设计图输入，再由 `screen_to_schema.py` 生成粗略 HTML preview / handoff。

## 共通风格约束

- Mobile portrait game UI screenshot, 9:16 aspect ratio, clean flat 2D interface, not a mockup on a device.
- Style reference: 《破宫十重奏》现有主菜单 UI：米白宣纸背景、细灰线框、克制红棕点缀、朱印、黄铜/金色小标签、宋体/书法标题感、极简几何图形、淡墨插画、轻微纸纹和柔和阴影。
- UI must be readable by OCR: use clear Simplified Chinese labels, avoid overdecorated text, avoid tiny unreadable glyphs.
- Keep layout structured for later HTML reconstruction: distinct panels, visible bounding boxes, consistent spacing, no photorealism.
- Avoid gore, explicit violence, or real-world logos. Use abstract ritual / palace / music / card-battle motifs.
- Palette: warm ivory `#F4EFE3`, ink brown `#2E211A`, muted red `#A5352C`, brass gold `#B78A42`, pale gray `#B7B1A7`.

## Prompt 1 — 主菜单 / Main Menu

Create a mobile portrait game main menu UI screenshot for a Chinese narrative card roguelite called “破宫十重奏”. Off-white textured paper background, thin gray borders, muted red seal accents, brass number plaques, elegant Chinese typography. Layout: top left square button “设置” with gear icon, top right square button “成就”; centered large title “破宫之十重奏” and subtitle “一桌无人知晓的局，一场无法回头的演奏。”; two large horizontal action cards: “继续旅程 / 返回当前的破宫之旅” with number badge “10” and red circular door icon, “新的旅程 / 开启一场新的破宫之旅” with badge “01”; a bordered “最近旅程” panel with character name “沈伶音”, floor “07/10”, round “03/05”, progress petals; bottom three cards “规则说明”, “卡牌图鉴”, “结局回顾”. Minimal ink illustrations, clean OCR-readable Simplified Chinese text, flat UI screenshot, no device frame.

## Prompt 2 — 设置 / Settings

Create a mobile portrait game settings screen UI screenshot in the same “破宫十重奏” paper-and-ink style. Off-white parchment background, thin gray dividers, muted red circular seals, brass toggle knobs, elegant Chinese typography. Top bar: back arrow “返回”, centered title “设置”, small red seal “静”. Main sections: “声音” with sliders “主音量 72”, “乐音 58”, “音效 64”; “画面” with segmented options “低 / 中 / 高” and selected “高”, toggle “纸纹效果 开”, toggle “动态朱印 开”; “游戏” with toggle “自动存档 开”, toggle “战斗提示 开”, language row “语言 简体中文”; bottom brass outlined buttons “恢复默认” and red primary button “保存设置”. Layout must be clean and structured, distinct panels and rows, OCR-readable Chinese, subtle geometric ink icons, no photorealism.

## Prompt 3 — 档案 / Archive / Codex

Create a mobile portrait game archive / character dossier UI screenshot for “破宫十重奏”. Same off-white paper, ink-brown linework, muted red seals, brass labels. Top bar: “返回” left, title “档案馆”, right small tab “筛选”. Layout: left vertical navigation rail with tabs “角色”, “卡牌”, “事件”, “结局”, selected “角色” with red mark. Main panel titled “角色档案” with search field “搜索姓名或乐章”; large dossier card for “沈伶音” with pale ink portrait frame, tags “第七楼”, “琴弦”, “未完成”; stats rows “记忆 42”, “执念 68”, “共鸣 31”; notes panel titled “残页记录” containing short readable lines “她在第三次演奏后失去了名字。”; bottom grid of three smaller locked/available cards: “陆简”, “白鹿”, “？？？”. Strong panel boundaries for HTML reconstruction, legible Simplified Chinese, minimalist ink illustrations.

## Prompt 4 — 战斗界面 / Combat HUD

Create a mobile portrait tactical card battle UI screenshot in the same “破宫十重奏” style. Off-white parchment battlefield with thin gray grid and ink shadows, muted red enemy seals, brass resource counters. Top status bar: left player “沈伶音 HP 32/45”, right enemy “宫中影 HP 28/40”, center round seal “第 03 轮”. Middle: abstract palace-room battlefield with three enemy intent cards labeled “屏”, “聚”, “裂”, small damage markers, timeline ribbon “先手 → 敌意 → 演奏”. Lower panel: player hand of four cards with readable names “断弦”, “回声”, “朱印”, “退步”, each in bordered paper card style with cost circles. Bottom action bar: resource “气 4/6”, red primary button “结束回合”, small buttons “弃牌”, “查看规则”. Clean flat UI screenshot, structured panels, OCR-readable Chinese, no blood or gore, no device frame.
