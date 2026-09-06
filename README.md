# DTRI Office Lunch

`dtri-office-lunch` 使用專案內的 Playwright `browser-profile/` 讀取 DTRI 今日便當菜單，讓人或 Agent 建立一份待確認訂單，並且只有在 `submit` 的 stdin 收到精確大寫 `YES` 時才送出。

## 安全界線

- 帳號、密碼、OTP 與 CAPTCHA 一律由使用者在可見瀏覽器中手動處理。
- `browser-profile/` 包含登入狀態，不可提交、上傳或分享。
- 每次只能訂一種餐點，數量固定為 1，可加備註。
- `prepare` 不會送單；它只建立一次性 `ORDER_TOKEN`。
- `YES` 必須在使用者看過該筆訂單摘要後提供。
- `submit` 在發出 request 前先記錄嘗試狀態。結果不確定時禁止自動重送，避免重複訂餐。

## 本機安裝

在此 repository 中執行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m playwright install chromium
```

確認命令：

```powershell
dtri-office-lunch --help
```

CLI 必須在 Git repository 內執行。它會由目前目錄往上尋找 Git root，並使用該處的 `browser-profile/` 與 `data/`。

## 使用流程

### 1. 手動登入

登入狀態不存在或失效時，查詢命令會以 exit code 2 回報 `AUTH_REQUIRED`，不會自行卡住等待：

```powershell
dtri-office-lunch login
```

請在開啟的瀏覽器自行完成登入。程式不會讀取或填入憑證。

### 2. 取得菜單

```powershell
dtri-office-lunch
```

`menu` 是相同命令的明確寫法：

```powershell
dtri-office-lunch menu
```

stdout 會直接顯示方便選擇的短序號，並在每一項最後保留後端餐點 ID：

```text
今日便當菜單

【好吃便當】
[1] 排骨飯｜100 元 (ID: 101)
[2] 雞腿飯｜110 元 (ID: 102)
```

短序號會依當次菜單由 1 開始排列。CLI 同時把短序號與後端 ID 的對照保存在 `data/latest-menu.json`，所以後續不需要輸入三位數 ID。

### 3. 建立待確認訂單

```powershell
dtri-office-lunch prepare 1 --remark '不要辣'
```

stdout 會顯示商家、餐點、價格、數量、備註與一次性 `ORDER_TOKEN`。先把完整摘要交給使用者確認，此時尚未送單。

### 4. 使用者確認後送出

只有使用者在該摘要後回覆精確大寫 `YES`，Agent 才能執行：

```powershell
'YES' | dtri-office-lunch submit <ORDER_TOKEN>
```

小寫 `yes`、其他句子或缺少 stdin 都會被拒絕。每個 token 只能嘗試送出一次。

## 安裝 Agent Skill

命令會把隨套件附帶的同一份 `SKILL.md` 安裝到目標 skills 目錄；程式功能仍由已安裝的 `dtri-office-lunch` Python 套件提供。

內建平台捷徑會安裝到目前 Git repository，不會全域安裝：

```powershell
dtri-office-lunch install-skill codex
dtri-office-lunch install-skill claude
dtri-office-lunch install-skill antigravity
```

安裝位置：

| 平台 | Repository 內的位置 |
| --- | --- |
| Codex | `.agents/skills/dtri-office-lunch/SKILL.md` |
| Claude Code | `.claude/skills/dtri-office-lunch/SKILL.md` |
| Antigravity | `.agents/skills/dtri-office-lunch/SKILL.md` |

Codex 與 Antigravity 共用 Agent Skills 標準位置，因此同一 repository 通常只需寫入一次。現有 Skill 預設不覆蓋；更新時明確加上 `--force`。

### 自訂 skills 目錄

若使用其他 Agent，或希望自行決定安裝位置，使用 `--dest` 指定 **skills 根目錄**：

```powershell
dtri-office-lunch install-skill --dest C:\my-agent\skills
```

此例會建立 `C:\my-agent\skills\dtri-office-lunch\SKILL.md`。`--dest` 不需要在 Git repository 內執行，但不得和平台名稱同時使用；例如 `install-skill codex --dest ...` 會被拒絕。目標已有 `SKILL.md` 時同樣須明確加上 `--force` 才會覆寫。

## 離線驗證

```powershell
python -m unittest discover -s tests -v
python -m build
```

測試不會登入內網，也不會發出真實訂單 request。
