# 登入後 API 線索

本頁面載入後使用同源端點：

`https://intranet.ideas.iii.org.tw:8099/common/bbsales.ashx`

## 取得餐點

```text
POST common/bbsales.ashx?cs=getodrpdt&store=&key=
```

JavaScript 以同步 `$.ajax` 呼叫，回應直接當作 JSON 陣列使用。頁面從每筆資料讀取的欄位包括：

```json
{
  "id": "545",
  "title": "弍食穗",
  "cate": "便當",
  "cateid": "...",
  "storeid": "53",
  "opentime": "...",
  "stock": "...",
  "preorder": "...",
  "pdtname": "水煮嫩雞胸",
  "price": "115"
}
```

`store` 可傳店家 ID；`key` 可傳搜尋文字。頁面初始載入使用空字串取得全部餐點。

## 取得公告／店家備註

```text
POST common/bbsales.ashx?cs=getkeyval&_key=storeremark
Accept: application/json
```

回應是 JSON 陣列，頁面使用每筆資料的 `_val` 組成公告內容。

## 取得店家清單

```text
GET common/bbsales.ashx?cs=bindStore
Accept: application/json
```

回應資料至少包含 `id` 與 `title`，前端用它建立店家搜尋選單。

## 購物車與送出

選擇數量與備註時，`addcarts(storeid)` 只在瀏覽器記憶體更新 `carts` 陣列；不會立即呼叫 API。購物車顯示也由前端 `showcarts()` 計算總額。

真正送出時才呼叫：

```text
POST common/bbsales.ashx?cs=odr
Content-Type: application/x-www-form-urlencoded
```

表單資料欄位為：

```text
array=<JSON.stringify(carts)>
```

不要在離線測試中對這個端點送出請求；它會產生真實訂單。登入 Cookie／工作階段與任何動態驗證值也不應保存或重播。

## 重要限制

- 以上是從登入後頁面的 JavaScript 與表單結構讀出的請求線索，未執行真實送單。
- `getodrpdt`、`getkeyval`、`bindStore` 可能要求有效的登入工作階段。
- `__VIEWSTATE` 是 ASP.NET 頁面狀態，不是穩定 API token；本資料包沒有保存它。
