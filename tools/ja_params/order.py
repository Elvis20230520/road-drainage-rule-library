# -*- coding: utf-8 -*-
"""把「按编号…去执行，项目编号…」解析成分项编号、项目编号和执行说明来源。"""
from __future__ import annotations

import re

_ORDER_RE = re.compile(
    r"按编号\s*(?P<items>.*?)\s*去执行\s*[，,]\s*项目编号\s*[:：]?\s*"
    r"(?P<project>[A-Za-z0-9][A-Za-z0-9_-]{0,31})",
    re.DOTALL,
)
_ITEM_RE = re.compile(r"JA-\d{3}", re.IGNORECASE)
_PATH_RE = re.compile(
    r"(?:本机必要文件路径|必要文件路径|资料目录|项目目录)\s*[:：]\s*(?P<path>[^\r\n]+)"
)
# 紧挨在「不」后面的不算，避免把「不用线上文件」认成要用线上文件。
_SOURCE_ONLINE_RE = re.compile(r"(?<!不)用线上文件")
_SOURCE_LOCAL_RE = re.compile(r"(?<!不)用本地文件")


class OrderError(Exception):
    """这句话里没有可用的编号或项目编号。"""


def parse_order(text: str) -> tuple[list[str], str]:
    """从一整段吩咐里取出分项编号和项目编号。

    认这两种写法，前后可以有仓库地址或其他说明：

    - 按编号JA-001去执行，项目编号001
    - 按编号 JA-001、JA-002、JA-003 去执行，项目编号 001
    """
    match = _ORDER_RE.search(text or "")
    if not match:
        raise OrderError(
            "认不出执行吩咐。请写成：按编号JA-001去执行，项目编号001。"
            "多个编号用顿号隔开。"
        )
    found = _ITEM_RE.findall(match.group("items"))
    if not found:
        raise OrderError("按编号和去执行之间没有 JA-001 这样的分项编号。")
    items: list[str] = []
    seen = set()
    for raw in found:
        tag = raw.upper()
        if tag not in seen:
            seen.add(tag)
            items.append(tag)
    return items, match.group("project")


def parse_data_dir(text: str) -> str | None:
    """从吩咐里取出本机必要文件路径。没有这一行时返回 None。"""
    match = _PATH_RE.search(text or "")
    if not match:
        return None
    path = match.group("path").strip().strip("「」\"'")
    return path or None


def parse_instruction_source(text: str) -> str | None:
    """从吩咐里取出执行说明来源。

    - 「用线上文件」→ ``online``，只读规则库里的执行说明
    - 「用本地文件」→ ``local``，只读本机必要文件路径里的同名执行说明
    - 都没写 → ``None``，沿用原查找：只看本机路径，没有则用内置规则

    「不用线上文件」「不用本地文件」不计数。两句同时写上时拒绝执行。
    """
    raw = text or ""
    online = _SOURCE_ONLINE_RE.search(raw) is not None
    local = _SOURCE_LOCAL_RE.search(raw) is not None
    if online and local:
        raise OrderError(
            "吩咐里同时写了「用线上文件」和「用本地文件」，请只保留一个。"
        )
    if online:
        return "online"
    if local:
        return "local"
    return None
