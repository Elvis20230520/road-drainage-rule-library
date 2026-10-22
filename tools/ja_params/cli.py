# -*- coding: utf-8 -*-
"""本机脚本。操作者平时只发「按编号…去执行，项目编号…」。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.ja_params.builder import InputError, run_items
from tools.ja_params.order import (
    OrderError,
    parse_data_dir,
    parse_instruction_source,
    parse_order,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.ja_params",
        description="交安资料参数的本机脚本（JA-001 交通标志、JA-002 路面标线、JA-003 波形护栏）。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="生成参数表")
    run.add_argument(
        "items",
        nargs="*",
        help="分项编号，例如 JA-001，或 JA-001 JA-002 JA-003",
    )
    run.add_argument("--project", help="项目编号，写入输出文件名")
    run.add_argument(
        "--order",
        help="整句吩咐，例如：按编号JA-001去执行，项目编号001。可另写「用线上文件」或「用本地文件」",
    )
    run.add_argument(
        "--data-dir",
        help="本机必要文件路径。台账和导线点及水准点在这里；「用本地文件」或未指定来源时，执行说明也在这里",
    )
    run.add_argument(
        "--template",
        help="参数样板.xlsx。省略时先用项目目录中的同名文件，没有则用仓库 share/参数样板.xlsx",
    )
    run.add_argument(
        "--instruction-source",
        choices=("online", "local"),
        help="执行说明来源。online 即「用线上文件」，local 即「用本地文件」。省略时只看本机必要文件路径，没有则用内置规则",
    )

    parse = sub.add_parser("parse", help="把一句吩咐解析成分项编号、项目编号和执行说明来源")
    parse.add_argument(
        "order",
        help="例如：按编号 JA-001、JA-002 去执行，项目编号 001。可另写「用线上文件」或「用本地文件」",
    )
    return parser


def _items_and_project(args) -> tuple[list[str], str]:
    if args.order:
        if args.items or args.project:
            raise OrderError("使用 --order 时不必再写分项编号和 --project。")
        return parse_order(args.order)
    if not args.items or not args.project:
        raise OrderError("请给出分项编号和 --project，或使用 --order。")
    return list(args.items), args.project


def _shell_quote(path: str) -> str:
    if any(ch.isspace() for ch in path):
        return '"' + path.replace('"', '\\"') + '"'
    return path


def _resolve_instruction_source(args) -> str | None:
    named = getattr(args, "instruction_source", None) or None
    embedded = parse_instruction_source(args.order) if getattr(args, "order", None) else None
    if named and embedded and named != embedded:
        raise OrderError(
            "命令行的执行说明来源和吩咐里的「用线上文件」或「用本地文件」不一致。"
        )
    return named or embedded


def _resolve_data_dir(args) -> str:
    named = (args.data_dir or "").strip()
    embedded = parse_data_dir(args.order) if getattr(args, "order", None) else None
    # 命令行上的路径就是本机当场指定的目录。
    if named:
        return named
    if embedded:
        return embedded
    raise OrderError(
        "请给出本机必要文件路径。"
        "可以写 --data-dir，或在吩咐里写「本机必要文件路径：...」。"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "parse":
            items, project = parse_order(args.order)
            line = " ".join(items) + f" --project {project}"
            data_dir = parse_data_dir(args.order)
            if data_dir:
                line += " --data-dir " + _shell_quote(data_dir)
            source = parse_instruction_source(args.order)
            if source:
                line += " --instruction-source " + source
            print(line)
            return 0
        if args.command == "run":
            items, project = _items_and_project(args)
            data_dir = _resolve_data_dir(args)
            source = _resolve_instruction_source(args)
            template = Path(args.template) if args.template else None
            run_items(
                items,
                project,
                Path(data_dir),
                template,
                instruction_source=source,
            )
            return 0
    except (InputError, OrderError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    parser.error(f"未知命令: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
