from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from dtri_office_lunch import cli


class CliTests(unittest.TestCase):
    def test_format_menu_uses_short_numbers_and_keeps_backend_ids(self) -> None:
        items = [
            {"id": 101, "pdtname": "排骨飯", "title": "好吃便當", "price": 100, "status": 1},
            {"id": 102, "pdtname": "雞腿飯", "title": "好吃便當", "price": 110, "status": 1},
            {"id": 201, "pdtname": "售完餐", "title": "別家", "price": 90, "status": 0},
        ]

        output = cli.format_menu(items)

        self.assertIn("【好吃便當】", output)
        self.assertIn("\n[1] 排骨飯｜100 元 (ID: 101)", output)
        self.assertIn("\n[2] 雞腿飯｜110 元 (ID: 102)", output)
        self.assertNotIn("- [1]", output)
        self.assertNotIn("售完餐", output)

    def test_menu_selection_resolves_short_number_to_backend_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli.save_menu_selections(
                root,
                [
                    {"id": 351, "pdtname": "炒冬粉", "status": 1},
                    {"id": 352, "pdtname": "每日特餐", "status": 1},
                ],
            )

            self.assertEqual(cli.resolve_menu_selection(root, "1"), "351")
            self.assertEqual(cli.resolve_menu_selection(root, "2"), "352")
            with self.assertRaisesRegex(RuntimeError, "找不到餐點序號 3"):
                cli.resolve_menu_selection(root, "3")

    def test_pending_order_has_one_item_and_remark(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = cli.create_pending_order(
                root,
                {"id": "101", "pdtname": "排骨飯", "title": "好吃便當", "price": 100},
                "不要辣",
            )

            saved = json.loads(
                cli.pending_order_path(root, record["token"]).read_text(encoding="utf-8")
            )
            self.assertEqual(saved["status"], "prepared")
            self.assertEqual(saved["quantity"], 1)
            self.assertEqual(saved["payload"][0]["amt"], "1")
            self.assertEqual(saved["payload"][0]["remark"], "不要辣")

    def test_submit_rejects_anything_except_exact_yes_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = cli.create_pending_order(
                root, {"id": 101, "pdtname": "排骨飯", "title": "好吃便當"}
            )

            with self.assertRaisesRegex(RuntimeError, "CONFIRMATION_REQUIRED"):
                cli.run_submit(root, record["token"], io.StringIO("yes\n"))

            saved = json.loads(
                cli.pending_order_path(root, record["token"]).read_text(encoding="utf-8")
            )
            self.assertEqual(saved["status"], "prepared")

    def test_submit_is_one_time_and_records_server_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = cli.create_pending_order(
                root, {"id": 101, "pdtname": "排骨飯", "title": "好吃便當"}
            )

            @contextmanager
            def fake_page(_root):
                yield object()

            current_item = {
                "id": 101,
                "pdtname": "排骨飯",
                "title": "好吃便當",
                "price": None,
                "storeid": None,
            }
            with patch.object(cli, "authenticated_page", fake_page), patch.object(
                cli, "fetch_menu_items", return_value=[current_item]
            ), patch.object(
                cli,
                "send_order_payload",
                return_value={"ok": True, "status": 200, "text": "accepted"},
            ):
                self.assertEqual(
                    cli.run_submit(root, record["token"], io.StringIO("YES\n")), 0
                )

            saved = json.loads(
                cli.pending_order_path(root, record["token"]).read_text(encoding="utf-8")
            )
            self.assertEqual(saved["status"], "submitted")
            with self.assertRaisesRegex(RuntimeError, "禁止重複送出"):
                cli.run_submit(root, record["token"], io.StringIO("YES\n"))

    def test_auth_failure_before_post_keeps_order_prepared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = cli.create_pending_order(
                root, {"id": 101, "pdtname": "排骨飯", "title": "好吃便當"}
            )

            @contextmanager
            def auth_required(_root):
                raise cli.AuthRequiredError("AUTH_REQUIRED")
                yield

            with patch.object(cli, "authenticated_page", auth_required):
                with self.assertRaises(cli.AuthRequiredError):
                    cli.run_submit(root, record["token"], io.StringIO("YES\n"))

            saved = json.loads(
                cli.pending_order_path(root, record["token"]).read_text(encoding="utf-8")
            )
            self.assertEqual(saved["status"], "prepared")

    def test_changed_menu_marks_order_stale_without_post(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = cli.create_pending_order(
                root,
                {
                    "id": 101,
                    "pdtname": "排骨飯",
                    "title": "好吃便當",
                    "price": 100,
                    "storeid": 9,
                },
            )

            @contextmanager
            def fake_page(_root):
                yield object()

            with patch.object(cli, "authenticated_page", fake_page), patch.object(
                cli,
                "fetch_menu_items",
                return_value=[
                    {
                        "id": 101,
                        "pdtname": "排骨飯",
                        "title": "好吃便當",
                        "price": 110,
                        "storeid": 9,
                    }
                ],
            ), patch.object(cli, "send_order_payload") as sender:
                with self.assertRaisesRegex(RuntimeError, "ORDER_CHANGED"):
                    cli.run_submit(root, record["token"], io.StringIO("YES\n"))

            sender.assert_not_called()
            saved = json.loads(
                cli.pending_order_path(root, record["token"]).read_text(encoding="utf-8")
            )
            self.assertEqual(saved["status"], "stale")

    def test_install_skill_uses_project_local_platform_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()

            codex_target = cli.install_skill(root, "codex")
            claude_target = cli.install_skill(root, "claude")

            self.assertEqual(
                codex_target, root / ".agents" / "skills" / cli.SKILL_NAME / "SKILL.md"
            )
            self.assertEqual(
                claude_target, root / ".claude" / "skills" / cli.SKILL_NAME / "SKILL.md"
            )
            self.assertIn("name: dtri-office-lunch", codex_target.read_text(encoding="utf-8"))
            with self.assertRaisesRegex(RuntimeError, "--force"):
                cli.install_skill(root, "codex")


if __name__ == "__main__":
    unittest.main()
