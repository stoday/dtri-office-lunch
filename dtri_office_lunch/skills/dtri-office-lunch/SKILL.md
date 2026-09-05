---
name: dtri-office-lunch
description: 讀取數轉院辦公室午餐菜單，協助使用者選擇一份餐點、準備精確訂單摘要，且僅在使用者針對該摘要回覆全大寫 YES 後送出訂單。
---

# 數轉院辦公室午餐

將已安裝的 `dtri-office-lunch` 指令視為黑箱使用。不得檢視或洩露 `browser-profile`、Cookie、工作階段狀態或隱藏表單欄位。

## 操作流程

1. 執行 `dtri-office-lunch`，取得目前的人類可讀菜單。
2. 若指令以 `AUTH_REQUIRED` 結束，告知使用者必須手動登入，執行 `dtri-office-lunch login`，並等待使用者在開啟的瀏覽器完成登入。不得索取或輸入帳密、一次性密碼或 CAPTCHA。
3. 從 stdout 呈現目前商家與可選餐點。方括號內是方便點餐的短序號；末尾的持久後端 ID 僅供追溯。
4. 詢問使用者是否有備註。數量固定為一，且每次只能訂一份餐點。
5. 使用方括號內的短序號執行 `dtri-office-lunch prepare <selection-number> --remark <remark>`，並採用安全的 shell 參數引號。不得將 `ID:` 後的後端 ID 當作選餐序號；此時不得送出訂單。
6. 將包含商家、餐點、價格、數量、備註與 `ORDER_TOKEN` 的完整指令輸出展示給使用者，要求其回覆完全相同的全大寫 `YES`。
7. 僅當使用者在該精確摘要之後的下一則回覆完全等於 `YES`，才視為確認。先前出現、小寫、夾在句中、推測而來或無關的 yes 均不算確認。任何更動都必須重新 `prepare` 與確認。
8. 收到有效確認後，將 `YES` 經 stdin 傳入 `dtri-office-lunch submit <order-token>`：
   - PowerShell：`'YES' | dtri-office-lunch submit <order-token>`
   - POSIX shell：`printf 'YES\n' | dtri-office-lunch submit <order-token>`
9. 如實回報指令結果。`SUBMISSION_UNCERTAIN` 表示請求可能已抵達伺服器，絕不可自動重試。

不得為猜測、測試或未取得操作當下使用者確認而呼叫 `submit`。不得僅因 `prepare` 成功就宣稱訂單已被接受。
