# DTRI 訂便當系統：離線自動化資料包

這個資料包來自 2026-08-06 登入後首頁的唯讀擷取，目標是讓自動化工具可以先在本機 mock 頁面上開發與測試，不必每次連到內網。

## 已擷取範圍

- 登入後首頁：`https://intranet.ideas.iii.org.tw:8099/default.aspx`
- 單一簽入後的餐點列表、價格、數量下拉選單、餐點備註欄位
- 頁面上的主要連結、表單 method/action 與穩定欄位 ID
- 注意事項文字與目前購物車數量（擷取時為 0）

尚未擷取：購物車明細、送出訂單、付款或訂單完成頁。這些流程需要下一次在網站上逐步示範後再補入。

## 本機啟動

在專案根目錄執行：

```powershell
py -m http.server 8765 --directory website_data/mock_site
```

再開啟 <http://127.0.0.1:8765/>。這是靜態 mock，不會連線到內網，也不會送出真實訂單。

## Playwright 範例

需要本機已安裝 Playwright：

```powershell
py -m pip install playwright
py -m playwright install chromium
py website_data/playwright_example.py
```

範例會選擇餐點數量、填入備註並驗證購物車數量；它只操作 mock 頁面。

## 敏感資料處理

沒有保存帳號、密碼、Cookie、Token、ASP.NET `__VIEWSTATE` 或登入工作階段資料。`__VIEWSTATE` 會隨頁面與 session 改變，不能當作穩定自動化定位資訊。
