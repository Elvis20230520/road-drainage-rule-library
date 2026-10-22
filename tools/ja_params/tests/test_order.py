# -*- coding: utf-8 -*-
"""「按编号…去执行，项目编号…」的解析。"""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from tools.ja_params.cli import main
from tools.ja_params.order import OrderError, parse_data_dir, parse_order


class OrderTests(unittest.TestCase):
    def test_single_code(self):
        items, project = parse_order("按编号JA-001去执行，项目编号001")
        self.assertEqual(items, ["JA-001"])
        self.assertEqual(project, "001")

    def test_three_codes_with_spaces(self):
        items, project = parse_order("按编号 JA-001、JA-002、JA-003 去执行，项目编号 001")
        self.assertEqual(items, ["JA-001", "JA-002", "JA-003"])
        self.assertEqual(project, "001")

    def test_sentence_can_follow_a_repo_url(self):
        text = (
            "https://github.com/Elvis20230520/road-drainage-rule-library\n"
            "「按编号JA-001去执行，项目编号001」"
        )
        self.assertEqual(parse_order(text), (["JA-001"], "001"))

    def test_colon_and_english_comma(self):
        items, project = parse_order("按编号 JA-001, JA-002 去执行, 项目编号：001")
        self.assertEqual(items, ["JA-001", "JA-002"])
        self.assertEqual(project, "001")

    def test_reject_unstructured_text(self):
        with self.assertRaises(OrderError):
            parse_order("请做 JA-001")

    def test_explicit_local_path_is_separate_from_the_sample(self):
        text = "\n".join(
            [
                "https://github.com/Elvis20230520/road-drainage-rule-library",
                "按编号 JA-001、JA-002、JA-003 去执行，项目编号 001",
                r"本机必要文件路径：D:\资料\某项目",
            ]
        )
        self.assertEqual(
            parse_order(text),
            (["JA-001", "JA-002", "JA-003"], "001"),
        )
        self.assertEqual(parse_data_dir(text), r"D:\资料\某项目")
        self.assertIsNone(parse_data_dir("按编号JA-001去执行，项目编号001"))

    def test_parse_command_prints_cli_args(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["parse", "按编号 JA-001、JA-003 去执行，项目编号 001"])
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue().strip(), "JA-001 JA-003 --project 001")

    def test_parse_command_includes_the_given_path(self):
        text = "按编号 JA-001 去执行，项目编号 001\n本机必要文件路径：D:\\资料\\某项目"
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["parse", text])
        self.assertEqual(code, 0)
        self.assertEqual(
            buffer.getvalue().strip(),
            "JA-001 --project 001 --data-dir D:\\资料\\某项目",
        )

    def test_run_without_a_path_is_rejected(self):
        self.assertEqual(
            main(["run", "--order", "按编号JA-001去执行，项目编号001"]),
            2,
        )
        self.assertEqual(main(["run", "JA-001", "--project", "001"]), 2)


if __name__ == "__main__":
    unittest.main()
