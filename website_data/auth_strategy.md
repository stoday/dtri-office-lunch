# 使用者登入狀態的安全自動化方案

## 不保存原始憑證

不要把 Cookie、Session ID、JWT、密碼、OTP、`__VIEWSTATE` 或 Playwright `storage_state` 檔案放進 `website_data`、Git、Dropbox 或測試 fixture。這些資料可能讓持有檔案的人直接冒用登入狀態。

## 建議流程

1. 自動化工具啟動本機瀏覽器的專用使用者設定檔。
2. 第一次執行時導向登入頁。
3. 使用者自行輸入帳密並完成驗證。
4. 工具只在同一台電腦的專用設定檔中重用登入狀態。
5. 偵測到登入逾時時，停止並要求使用者重新登入。
6. 提供「清除本機登入狀態」功能，刪除專用設定檔。

## Playwright Python 範例

```python
from pathlib import Path
from playwright.sync_api import sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = PROJECT_ROOT / "browser-profile"
TARGET = "https://intranet.ideas.iii.org.tw:8099/default.aspx"


with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(TARGET)

    # 如果被導向登入頁，交還畫面給使用者；不要由程式讀取或填入密碼。
    if "/Login.aspx" in page.url or ":550" in page.url:
        print("請在瀏覽器完成登入後，再按 Enter 繼續")
        input()

    page.goto(TARGET)
    # 登入狀態只存在 PROFILE_DIR，不輸出、不上傳、不寫入 website_data。
    print(page.title())
    context.close()
```

## 不建議的做法

- 從 Chrome／Edge 讀取 Cookie 再寫入檔案。
- 把 `storage_state.json` 放在專案資料夾。
- 把 Session ID 放到 `.env.example`、README 或測試資料。
- 將真實登入狀態複製到 mock fixture。
- 讓多人共用同一個瀏覽器設定檔或 Session。

本專案目前把 persistent profile 放在專案的 `browser-profile` 目錄，方便管理；但該目錄包含敏感登入狀態，請勿分享、上傳、同步到 Dropbox 或提交版本控制。若改用 `storage_state`，也應放在受限位置並排除備份；本工具不會替使用者擷取或傳送該檔案。
