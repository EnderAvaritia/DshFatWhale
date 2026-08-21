# DshFatWhale 🐋 — DeepSeek 余额鲸鱼桌宠

DeepSeek-Balance-Whale-Widget（DSH 小鲸鱼余额挂件）的**独立运行桌面版**：不依赖 DSH、不依赖浏览器，一只透明置顶的小鲸鱼趴在屏幕角落，帮你盯着 DeepSeek 账户余额。

实现参照 [dafeiyu-pet](https://github.com/1190fasheqi/dafeiyu-pet)（Python + PySide6 透明桌宠）的工程方式，行为对齐原 web 挂件。

## 功能

- 💰 **余额 + 今日已用 + 峰谷时段常驻气泡**：余额/今日已用/当前时段（梁文峰·梁文谷）常驻显示在鲸鱼上方，**右键菜单可关**；数字滚动动画；60 秒自动刷新 + 点击鲸鱼后台刷新；网络瞬时抖动自动沿用最近余额不报错
- 📊 **今日已用两种模式**（右键菜单切换，默认记账）：
  - **小鲸鱼记账（推荐，免令牌）**：观测余额后用余额差值自动记账（`.dshw-usage.json`，跨天自动归零归档）
  - **实时·令牌**：填平台令牌后按**峰谷定价**（高峰 9–12 / 14–18 点）实时换算今日已用
- 🖱️ **拖拽 + 四边吸附**：默认趴屏幕右下角，拖到屏幕四分之一区域自动吸附；**过屏幕中线即镜像翻转**（左半屏镜像，右半屏还原）
- 👆 **点击 = 台词表循环**：点一下鲸鱼随机说一句 `台词表.md` 里的词，再点换一句，说完自动回落常驻余额气泡
- 🧸 **Q 弹按压**：按下压扁、松手回弹，配按压/松手音效（小黄鸭 / 音效1 两套可切，音量可调）
- 🎚️ **右键菜单**（桌面版"汉堡菜单"）：余额气泡开关 / 用量模式 / 音效 / 音量 / 大小 / 设置 Key / 置顶 / 鼠标穿透 / 开机自启 / 退出
- 🗔 **系统托盘**：左键切换显隐，右键同款菜单（穿透后靠它解除）
- 📐 呼吸 / 摇摆 / 蹦跳小动画，位置、大小、吸附状态、音效、模式全部记忆（`config.json`）

## 运行

需要 **Python 3.11+**（已在 Python 3.14.5 验证）。

```powershell
# 首次：创建虚拟环境并装依赖
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 运行：双击 启动鲸鱼.bat，或
.\.venv\Scripts\pythonw.exe 鲸鱼.py
```

## 配置 API Key

余额接口需要 `DEEPSEEK_API_KEY`，两种配置方式（环境变量优先）：

1. **环境变量**（推荐，不落盘）：
   ```powershell
   setx DEEPSEEK_API_KEY "sk-xxxx"
   ```
2. **右键菜单 → 设置 DeepSeek Key…**（存入 `config.json`，已被 `.gitignore` 排除）

实时·令牌模式还需在右键菜单填**平台令牌**（浏览器 DevTools 里用量请求的 `Authorization` 头）。

### API Key 与平台令牌的区别

| | API Key（DEEPSEEK_API_KEY） | 平台令牌（DEEPSEEK_PLATFORM_TOKEN） |
|---|---|---|
| 获取方式 | platform.deepseek.com 控制台**创建**（官方） | 浏览器 DevTools **抓包**（网页登录会话） |
| 查余额 | ✅ 官方接口 `api.deepseek.com/user/balance` | — |
| 查今日用量明细 | ❌ 官方 API 不开放 | ✅ 借平台网页内部接口 |
| 时效 | 长期有效，可随时吊销重建 | 网页登录过期即失效，需重新抓 |
| 安全级别 | 服务器密钥 | 会话凭证（更敏感，泄露=账号会话被劫持） |
| 稳定性 | 官方接口，稳定 | 非官方用法，网站改版可能失效 |

**为什么需要两种？** 官方 API 只开放余额查询，**今日消耗明细（各模型 token、费用）只有网页后台能看**，所以令牌模式要借网页会话去读自己的后台。因此原挂件设计了两套"今日已用"：

- **记账模式（默认，推荐）**：只用 API Key，用余额差值推算今日消耗，零配置零风险
- **实时·令牌模式**：额外填平台令牌，拿真实用量明细（含峰谷定价换算），代价是会过期、需维护

## 配置文件（config.json）

首次运行自动生成 `config.json`（全是默认值，多数项也可在右键菜单里改）。`config.example.json` 是**合法可复制**的模板——想手改就把它复制成 `config.json` 再改值。编辑后重启生效。

| 键 | 默认 | 说明 |
|---|---|---|
| `usage_mode` | `"ledger"` | 用量模式：`ledger` 小鲸鱼记账（默认）/ `token` 实时·令牌 |
| `persistent_bubble` | `true` | 常驻余额气泡（余额+今日已用+峰谷时段），右键菜单可关 |
| `size` | `1.0` | 显示大小档位 |
| `sound_set` | `"duck"` | 音效：`duck` 小黄鸭 / `fx1` 音效1 |
| `vol` | `0.9` | 音量 0~1 |
| `sound_on` | `true` | 是否播放音效 |
| `ds_api_key` | `""` | 余额 API Key（环境变量 `DEEPSEEK_API_KEY` 优先） |
| `platform_token` | `""` | 平台令牌（实时·令牌模式用，可留空） |
| `topmost` | `true` | 置顶 |
| `passthrough` | `false` | 鼠标穿透（穿透后靠托盘菜单解除） |
| `autostart` | `false` | 开机自启 |
| `x` / `y` | `null` | 手动位置；`null` 表示按吸附锚点自动摆放 |
| `h` | `"right"` | 水平吸附：`left` / `right` / `null`（`null`=自由） |
| `v` | `"bottom"` | 垂直吸附：`top` / `bottom` / `null`（`null`=自由） |
| `h_off` / `v_off` | `0` | 吸附偏移量（px），拖拽松手时自动写入 |

注意：`config.json` 含明文 API Key，已在 `.gitignore` 中排除、不会入库；`config.example.json` 是公开模板。

## 目录结构

```text
鲸鱼.py            入口：QApplication、config 加载、主窗口 + 托盘
widget.py          主窗口：透明置顶、QPainter 绘制、tick 动画、拖拽/吸附/镜像/按压/气泡
balance.py         数据层：余额拉取、记账模式、令牌模式（峰谷定价）、缓存与瞬断兜底
sound.py           QSoundEffect 音效：两套音效组、音量
menu.py            右键菜单 + 系统托盘 + 开机自启
config.py          config.json 读写、路径解析、Key 解析（环境变量优先）
config.example.json  配置模板（复制成 config.json 改值即可）
assets/            鲸鱼图 DSniang1.png、音效 Ya1/Ya2/D1/D2.mp3、托盘图标 icon.ico
台词表.md          台词数据（用户可编辑：加一行 `- 台词` 即可新增）
启动鲸鱼.bat       启动脚本（自动选 .venv 或系统 pythonw）
鲸鱼.spec          PyInstaller 打包配置
tests/             balance 逻辑单测 + Qt 冒烟测试
```

## 添加自定义台词

鲸鱼说的所有话都在 `台词表.md` 里，**不用改代码**：

1. 用记事本打开 `台词表.md`
2. 在任意分组下新起一行，写 `- 你的台词`（如 `- 今天也要加油鸭！`）
3. 保存，重启程序生效

想调出现频率就改分组标题里的 `权重 N`（数字越大越常出现）。分组标题支持 `大字`（加大加粗）、`心声`（灰色斜体"内心OS"）、`多行`（整组台词拼成一个气泡）三种属性；`## 点击触发` 是**点击鲸鱼时优先说**的话（留空则点击显示余额），`## 拖拽后随机` 是拖拽松手时说的话。具体格式见文件顶部说明。

## 打包成独立 exe（可分享，无需 Python）

```powershell
.\.venv\Scripts\pip install pyinstaller
.\.venv\Scripts\pyinstaller 鲸鱼.spec
```

产物在 `dist/DshFatWhale.exe`，双击即用（杀毒软件可能对 PyInstaller 产物误报，加信任即可）。exe 与 `config.json`、账本文件同级存放，整个文件夹可拷走。

## 验证

```powershell
.\.venv\Scripts\python.exe tests\test_balance.py   # 逻辑单测
.\.venv\Scripts\python.exe tests\_smoke_qt.py      # Qt 冒烟（offscreen）
```

## 常见问题

- **显示"未配置 DEEPSEEK_API_KEY"**：见上方 Key 配置。
- **今日已用显示 --**：记账模式需先跑一次余额观测（60 秒内自动完成）；令牌模式需配置平台令牌。
- **没有声音**：确认 `assets/*.mp3` 存在；缺失时静默降级。
- **改代码不生效**：重启程序即可（无缓存问题）。

## 致谢

- 逻辑与素材移植自 [MeteorNOX/DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)（MIT）
- 工程实现参照 [1190fasheqi/dafeiyu-pet](https://github.com/1190fasheqi/dafeiyu-pet)（MIT）

## 协议

MIT
