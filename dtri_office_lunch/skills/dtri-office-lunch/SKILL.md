---
name: dtri-office-lunch
description: Read the DTRI office lunch menu, help the user choose one meal, prepare an exact order summary, and submit only after the user replies with exact uppercase YES to that summary.
---

# DTRI office lunch

Use the installed `dtri-office-lunch` command as a black box. Never inspect or expose `browser-profile`, cookies, session state, or hidden form values.

## Workflow

1. Run `dtri-office-lunch` to obtain the current human-readable menu.
2. If it exits with `AUTH_REQUIRED`, tell the user that manual login is required, run `dtri-office-lunch login`, and wait for them to finish in the opened browser. Never ask for or enter credentials, OTP, or CAPTCHA.
3. Present the current stores and available meals from stdout. The number in brackets is the short selection number; the persistent backend ID appears at the end only for traceability.
4. Ask for an optional remark. Quantity is always one and only one meal may be ordered.
5. Run `dtri-office-lunch prepare <selection-number> --remark <remark>` with the short number in brackets, using safe shell argument quoting. Never pass the backend ID shown after `ID:` as the selection number. Do not submit yet.
6. Show the complete command output containing store, meal, price, quantity, remark, and `ORDER_TOKEN` to the user. Ask them to reply with exact uppercase `YES`.
7. Treat only the user's next reply of exactly `YES`, after that exact summary, as confirmation. A prior, lowercase, embedded, inferred, or unrelated yes is not confirmation. Any change requires a new `prepare` and confirmation.
8. After valid confirmation, pipe `YES` to `dtri-office-lunch submit <order-token>`:
   - PowerShell: `'YES' | dtri-office-lunch submit <order-token>`
   - POSIX shell: `printf 'YES\n' | dtri-office-lunch submit <order-token>`
9. Report the command result accurately. `SUBMISSION_UNCERTAIN` means the request may have reached the server; never retry it automatically.

Do not call `submit` speculatively, for testing, or without action-time user confirmation. Do not claim an order was accepted merely because `prepare` succeeded.
