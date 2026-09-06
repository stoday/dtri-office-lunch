"""Agent-friendly CLI for reading the DTRI lunch menu and placing one order."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Iterator, TextIO

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


TARGET_URL = "https://intranet.ideas.iii.org.tw:8099/default.aspx"
LOGIN_URL = "https://intranet.ideas.iii.org.tw:8099/Login.aspx?returnUrl=/default.aspx"
PENDING_ORDER_VERSION = 1
SKILL_NAME = "dtri-office-lunch"
SKILL_TARGETS = {
    "codex": Path(".agents") / "skills" / SKILL_NAME,
    "claude": Path(".claude") / "skills" / SKILL_NAME,
    "antigravity": Path(".agents") / "skills" / SKILL_NAME,
}


class AuthRequiredError(RuntimeError):
    """Raised when the project-local browser profile is not authenticated."""


class ChineseArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return (
            super().format_help()
            .replace("usage:", "用法：")
            .replace("options:", "選項：")
            .replace("positional arguments:", "命令：")
        )


def find_project_root(start: Path | None = None) -> Path:
    """Find the current Git repository root without invoking Git."""

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("找不到目前 Git repository；請在專案目錄內執行此命令。")


def profile_dir(project_root: Path) -> Path:
    return project_root / "browser-profile"


def data_dir(project_root: Path) -> Path:
    return project_root / "data"


def menu_selection_path(project_root: Path) -> Path:
    return data_dir(project_root) / "latest-menu.json"


def pending_order_path(project_root: Path, token: str) -> Path:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    if not token or any(character not in allowed for character in token):
        raise RuntimeError("無效的 order token。")
    return data_dir(project_root) / "pending-orders" / f"{token}.json"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def is_logged_in(page) -> bool:
    return (
        page.url.rstrip("/").endswith("/default.aspx")
        and page.locator("form#aspnetForm").count() > 0
        and page.get_by_text("DTRI訂便當系統", exact=True).count() > 0
    )


def wait_for_user_login(
    page, timeout_seconds: int, error_stream: TextIO = sys.stderr
) -> None:
    print("瀏覽器已開啟。請自行輸入帳號、密碼並完成登入。", file=error_stream)
    print("程式不會讀取或填入帳密；登入成功後會自動結束。", file=error_stream)
    deadline = datetime.now().timestamp() + timeout_seconds
    while datetime.now().timestamp() < deadline:
        if is_logged_in(page):
            return
        page.wait_for_timeout(1000)
    raise TimeoutError("等待登入逾時，請重新執行 login。")


def wait_for_page_data(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass


def _find_items(value) -> list[dict]:
    if isinstance(value, str):
        try:
            return _find_items(json.loads(value))
        except json.JSONDecodeError:
            return []
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            if any(
                "id" in item and ("pdtname" in item or "title" in item)
                for item in value
            ):
                return value
        for child in value:
            found = _find_items(child)
            if found:
                return found
    elif isinstance(value, dict):
        for child in value.values():
            found = _find_items(child)
            if found:
                return found
    return []


def fetch_menu_items(page) -> list[dict]:
    raw = page.evaluate(
        """async () => {
          const response = await fetch('/common/bbsales.ashx?cs=getodrpdt&store=&key=', {
            credentials: 'same-origin'
          });
          if (!response.ok) throw new Error(`menu API returned ${response.status}`);
          return await response.json();
        }"""
    )
    return _find_items(raw)


def item_name(item: dict) -> str:
    return str(
        item.get("pdtname")
        or item.get("name")
        or item.get("title")
        or f"餐點 {item.get('id')}"
    )


def item_store(item: dict) -> str:
    return str(
        item.get("store")
        or item.get("storename")
        or item.get("store_name")
        or item.get("title")
        or "店家未提供"
    )


def item_price(item: dict) -> str:
    value = item.get("price")
    return "價格未提供" if value in (None, "") else f"{value} 元"


def available_items(items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        if item.get("id") in (None, ""):
            continue
        status = item.get("status", 1)
        stock = item.get("stock")
        if str(status).lower() in {"0", "false", "disabled", "soldout", "sold_out"}:
            continue
        if stock is not None:
            try:
                if int(stock) <= 0:
                    continue
            except (TypeError, ValueError):
                pass
        result.append(item)
    return result


def format_menu(items: list[dict]) -> str:
    items = available_items(items)
    if not items:
        return "今天沒有可訂的便當。"
    lines = ["今日便當菜單"]
    current_store = None
    for selection_number, item in enumerate(items, start=1):
        store = item_store(item)
        if store != current_store:
            lines.extend(["", f"【{store}】"])
            current_store = store
        lines.append(
            f"[{selection_number}] {item_name(item)}｜{item_price(item)} "
            f"(ID: {item['id']})"
        )
    return "\n".join(lines)


def save_menu_selections(project_root: Path, items: list[dict]) -> dict:
    """Persist the displayed short-number to backend-ID mapping."""

    available = available_items(items)
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "selections": [
            {"number": number, "item_id": str(item["id"])}
            for number, item in enumerate(available, start=1)
        ],
    }
    write_json(menu_selection_path(project_root), record)
    return record


def resolve_menu_selection(project_root: Path, selection_number: str) -> str:
    try:
        number = int(selection_number)
    except ValueError as error:
        raise RuntimeError("餐點序號必須是菜單方括號中的數字。") from error
    path = menu_selection_path(project_root)
    if not path.is_file():
        raise RuntimeError("找不到最近一次菜單；請先執行 dtri-office-lunch。")
    record = json.loads(path.read_text(encoding="utf-8"))
    selected = next(
        (
            entry
            for entry in record.get("selections", [])
            if entry.get("number") == number
        ),
        None,
    )
    if selected is None:
        raise RuntimeError(f"找不到餐點序號 {number}；請重新取得菜單。")
    return str(selected["item_id"])


def build_order_payload(item: dict, remark: str = "") -> list[dict]:
    return [
        {
            "id": int(item["id"]),
            "loc": item.get("loc"),
            "pdtname": item.get("pdtname") or item.get("name") or item.get("title"),
            "unit": item.get("unit"),
            "maxoffer": item.get("maxoffer", 1),
            "safestock": item.get("safestock"),
            "stock": item.get("stock"),
            "cateid": item.get("cateid"),
            "cate": item.get("cate"),
            "status": item.get("status", 1),
            "price": item.get("price"),
            "title": item.get("title") or item.get("pdtname") or item.get("name"),
            "preorder": item.get("preorder"),
            "amt": "1",
            "remark": remark,
            "storeid": item.get("storeid"),
            "opentime": item.get("opentime"),
        }
    ]


def create_pending_order(project_root: Path, item: dict, remark: str = "") -> dict:
    token = secrets.token_urlsafe(18)
    record = {
        "version": PENDING_ORDER_VERSION,
        "token": token,
        "status": "prepared",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "item": {
            "id": str(item["id"]),
            "name": item_name(item),
            "store": item_store(item),
            "price": item.get("price"),
        },
        "quantity": 1,
        "remark": remark,
        "payload": build_order_payload(item, remark),
    }
    write_json(pending_order_path(project_root, token), record)
    return record


def format_order_summary(record: dict) -> str:
    price = record["item"].get("price")
    price_text = "價格未提供" if price in (None, "") else f"{price} 元"
    remark = record.get("remark") or "無"
    return "\n".join(
        [
            "待確認訂單",
            f"商家：{record['item']['store']}",
            f"餐點：{record['item']['name']}",
            f"價格：{price_text}",
            "數量：1",
            f"備註：{remark}",
            f"ORDER_TOKEN: {record['token']}",
            "請在看完以上摘要後回覆精確大寫 YES。",
        ]
    )


def send_order_payload(page, payload: list[dict]) -> dict:
    return page.evaluate(
        """async (cartPayload) => {
          const body = new URLSearchParams();
          body.set('array', JSON.stringify(cartPayload));
          const response = await fetch('/common/bbsales.ashx?cs=odr', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
              'X-Requested-With': 'XMLHttpRequest'
            },
            body
          });
          return {
            ok: response.ok,
            status: response.status,
            text: (await response.text()).slice(0, 4000)
          };
        }""",
        payload,
    )


@contextmanager
def authenticated_page(project_root: Path) -> Iterator:
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir(project_root)), headless=True
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            if not is_logged_in(page):
                raise AuthRequiredError(
                    "AUTH_REQUIRED: 請先執行 dtri-office-lunch login。"
                )
            page.goto(TARGET_URL, wait_until="domcontentloaded")
            if not is_logged_in(page):
                raise AuthRequiredError(
                    "AUTH_REQUIRED: 登入狀態已失效，請執行 dtri-office-lunch login。"
                )
            wait_for_page_data(page)
            yield page
        finally:
            context.close()


def run_login(project_root: Path, timeout_seconds: int) -> int:
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir(project_root)), headless=False
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            wait_for_user_login(page, timeout_seconds)
        finally:
            context.close()
    print("LOGIN_OK: 已更新目前專案的登入狀態。")
    return 0


def run_menu(project_root: Path) -> int:
    with authenticated_page(project_root) as page:
        items = fetch_menu_items(page)
    save_menu_selections(project_root, items)
    print(format_menu(items))
    return 0


def run_prepare(project_root: Path, selection_number: str, remark: str) -> int:
    item_id = resolve_menu_selection(project_root, selection_number)
    with authenticated_page(project_root) as page:
        items = available_items(fetch_menu_items(page))
    selected = next(
        (item for item in items if str(item.get("id")) == str(item_id)), None
    )
    if selected is None:
        raise RuntimeError(
            f"序號 {selection_number} 對應的餐點 ID {item_id} 已不可訂；"
            "請重新取得菜單。"
        )
    record = create_pending_order(project_root, selected, remark)
    print(format_order_summary(record))
    return 0


def run_submit(
    project_root: Path, token: str, input_stream: TextIO = sys.stdin
) -> int:
    confirmation = input_stream.read().strip()
    if confirmation != "YES":
        raise RuntimeError(
            "CONFIRMATION_REQUIRED: stdin 必須只有精確大寫 YES；沒有送出訂單。"
        )

    path = pending_order_path(project_root, token)
    if not path.is_file():
        raise RuntimeError("找不到待確認訂單；請重新執行 prepare。")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("status") != "prepared":
        raise RuntimeError(f"此訂單狀態為 {record.get('status')}，禁止重複送出。")

    with authenticated_page(project_root) as page:
        current_items = available_items(fetch_menu_items(page))
        current_item = next(
            (
                item
                for item in current_items
                if str(item.get("id")) == record["item"]["id"]
            ),
            None,
        )
        original = record["payload"][0]
        unchanged = current_item is not None and all(
            str(current_item.get(field)) == str(original.get(field))
            for field in ("price", "storeid", "pdtname")
        )
        if not unchanged:
            record["status"] = "stale"
            record["stale_at"] = datetime.now(timezone.utc).isoformat()
            write_json(path, record)
            raise RuntimeError(
                "ORDER_CHANGED: 餐點已下架或內容、價格、店家已變更；請重新取得菜單並 prepare。"
            )

        # Persist the no-retry boundary immediately before making the request.
        # If the process crashes after the POST, it cannot be replayed blindly.
        record["status"] = "submitting"
        record["submission_attempted_at"] = datetime.now(timezone.utc).isoformat()
        write_json(path, record)
        try:
            result = send_order_payload(page, record["payload"])
        except Exception as error:
            record["status"] = "submission_uncertain"
            record["error"] = str(error)
            write_json(path, record)
            raise RuntimeError(
                "SUBMISSION_UNCERTAIN: 送單過程發生錯誤，為避免重複訂餐不會自動重試。"
            ) from error

    record["status"] = "submitted" if result.get("ok") else "rejected"
    record["response"] = result
    write_json(path, record)
    print("ORDER_REQUEST_SENT" if result.get("ok") else "ORDER_REQUEST_REJECTED")
    print(f"HTTP_STATUS: {result.get('status')}")
    if result.get("text"):
        print(f"SERVER_RESPONSE: {result['text']}")
    return 0 if result.get("ok") else 1


def install_skill(
    project_root: Path | None = None,
    platform: str | None = None,
    force: bool = False,
    *,
    dest: Path | None = None,
) -> Path:
    """Install the packaged skill into a platform preset or explicit skills directory."""

    if (platform is None) == (dest is None):
        raise RuntimeError("請指定一個平台，或指定 --dest，但不可同時使用兩者。")

    if platform is not None:
        if project_root is None:
            raise RuntimeError("平台安裝需要目前 Git repository。")
        target_dir = project_root / SKILL_TARGETS[platform]
    else:
        assert dest is not None
        target_dir = dest.expanduser().resolve() / SKILL_NAME

    target_file = target_dir / "SKILL.md"
    if target_file.exists() and not force:
        raise RuntimeError(
            f"Skill 已存在：{target_file}；如要更新請加上 --force。"
        )
    target_dir.mkdir(parents=True, exist_ok=True)
    source = resources.files("dtri_office_lunch").joinpath(
        "skills", SKILL_NAME, "SKILL.md"
    )
    target_file.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target_file


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(
        prog="dtri-office-lunch",
        description="列出 DTRI 便當菜單，建立待確認訂單，並在 stdin 收到 YES 後送單。",
    )
    parser.add_argument(
        "--timeout", type=int, default=600, help="login 等待秒數（預設 600）。"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("menu", help="輸出今日商家與便當選項（預設命令）。")
    subparsers.add_parser("login", help="開啟瀏覽器供使用者手動登入。")
    prepare = subparsers.add_parser("prepare", help="建立一份待確認訂單。")
    prepare.add_argument("selection_number", help="菜單方括號中的短序號。")
    prepare.add_argument("--remark", default="", help="訂單備註。")
    submit = subparsers.add_parser("submit", help="stdin 為 YES 時送出待確認訂單。")
    submit.add_argument("order_token", help="prepare 輸出的 ORDER_TOKEN。")
    installer = subparsers.add_parser(
        "install-skill", help="安裝隨套件附帶的 Agent Skill。"
    )
    installer.add_argument(
        "platform", nargs="?", choices=sorted(SKILL_TARGETS), help="內建平台安裝位置。"
    )
    installer.add_argument(
        "--dest",
        type=Path,
        help="指定 skills 根目錄；會在其中建立 dtri-office-lunch 子目錄。",
    )
    installer.add_argument("--force", action="store_true", help="覆寫現有 SKILL.md。")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "install-skill":
            root = find_project_root() if args.platform is not None else None
            target = install_skill(
                root, args.platform, args.force, dest=args.dest
            )
            print(f"SKILL_INSTALLED: {target}")
            return 0

        root = find_project_root()
        if args.command in (None, "menu"):
            return run_menu(root)
        if args.command == "login":
            return run_login(root, args.timeout)
        if args.command == "prepare":
            return run_prepare(root, args.selection_number, args.remark)
        if args.command == "submit":
            return run_submit(root, args.order_token)
        raise RuntimeError("未知命令。")
    except AuthRequiredError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (
        PlaywrightTimeoutError,
        TimeoutError,
        RuntimeError,
        OSError,
        ValueError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
