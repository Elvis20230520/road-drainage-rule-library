# -*- coding: utf-8 -*-
"""命令行：python -m tools.ja_params run JA-001 --project 001 --data-dir <path>"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.ja_params.builder import InputError, run_items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.ja_params",
        description="按分项编号生成交安资料参数表（JA-001 交通标志、JA-002 路面标线、JA-003 波形护栏）。",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="按一个或多个分项编号生成参数表")
    run.add_argument(
        "items",
        nargs="+",
        help="分项编号，例如 JA-001，或一次写出 JA-001 JA-002 JA-003",
    )
    run.add_argument("--project", required=True, help="项目编号，写入输出文件名")
    run.add_argument(
        "--data-dir",
        required=True,
        help="含资料台账、导线点及水准点、执行说明的目录",
    )
    run.add_argument(
        "--template",
        help="参数样板.xlsx。省略时先用数据目录中的同名文件，没有则用仓库 share/参数样板.xlsx",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.error(f"未知命令: {args.command}")
    template = Path(args.template) if args.template else None
    try:
        run_items(args.items, args.project, Path(args.data_dir), template)
    except InputError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
