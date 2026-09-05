from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).parent
URL = (ROOT / "mock_site" / "index.html").resolve().as_uri()


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL)

        page.locator('[id="545"]').select_option("2")
        page.locator('[id="rmk545"]').fill("不要辣")
        page.locator('input[data-add="545"]').click()

        assert page.locator("#cart-count").inner_text() == "2"
        assert page.locator('[id="rmk545"]').input_value() == "不要辣"
        assert page.locator('[id="550"]').is_disabled()
        print("offline fixture test passed")
        browser.close()


if __name__ == "__main__":
    main()
