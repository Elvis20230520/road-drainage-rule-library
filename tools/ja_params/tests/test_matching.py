# -*- coding: utf-8 -*-
"""锁池、2km 和参数样板查找的小用例。不依赖样例成果工作簿。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.ja_params.builder import (
    CANONICAL_TEMPLATE,
    ITEM_SPECS,
    REPO_INSTRUCTION_DIR,
    REPO_ROOT,
    InputError,
    clean_b,
    compute_zab,
    detect_side,
    extract_corridor,
    load_ledger_b,
    match_stations,
    parse_def,
    parse_ja002_constants,
    pick_ab_ja001,
    pick_ab_ja002,
    prepare_cfg,
    resolve_instruction_path,
    resolve_template,
)


def _instruction_with_def(sheet: str, d: str, e: str, f: str) -> str:
    return (
        "5，“参数样板”里的“"
        + sheet
        + "”D，E，F列分别写上“"
        + d
        + "”，“"
        + e
        + "”，“"
        + f
        + "”\n"
    )


def _point(name, prefix, num, pos, x=1.0, y=2.0, z=3.0):
    return {
        "name": name,
        "x": x,
        "y": y,
        "z": z,
        "prefix": prefix,
        "num": num,
        "pos": pos,
    }


class MatchingTests(unittest.TestCase):
    def test_spacing_tiers(self):
        self.assertEqual(pick_ab_ja001(50), 10)
        self.assertEqual(pick_ab_ja001(51), 20)
        self.assertEqual(pick_ab_ja001(70), 20)
        self.assertEqual(pick_ab_ja001(71), 40)
        self.assertEqual(pick_ab_ja002(50), 10)
        self.assertEqual(pick_ab_ja002(70), 20)
        self.assertEqual(pick_ab_ja002(200), 40)
        self.assertEqual(pick_ab_ja002(201), 100)

    def test_single_stake_rounds_to_10(self):
        z_val, aa_val, ab_val, adjusted, _note = compute_zab([123], pick_ab_ja001)
        self.assertEqual((z_val, aa_val, ab_val, adjusted), (120, 120, 0, True))

    def test_corridor_names_are_full_only(self):
        self.assertIsNone(extract_corridor("白岭大桥右侧"))
        self.assertIsNone(extract_corridor("修水西收费站"))
        self.assertEqual(extract_corridor("标志工程白岭互通A匝道右侧"), "白岭互通")
        self.assertEqual(extract_corridor("修水西枢纽"), "修水西枢纽")
        self.assertEqual(extract_corridor("铜鼓枢纽以远"), "铜鼓枢纽")
        for name in ("白岭互通", "石坳互通", "港口互通", "修水西枢纽", "铜鼓枢纽"):
            self.assertIn(name, extract_corridor(name))

    def test_corridor_pool_does_not_cross(self):
        traverse = [
            _point("BL1", "AK", 1000, "白岭互通A匝道AK1+000"),
            _point("BL2", "AK", 1200, "白岭互通A匝道AK1+200"),
            _point("SA1", "AK", 980, "石坳互通A匝道AK0+980"),
        ]
        levels = [
            _point("SZ-BL", "AK", 1100, "白岭互通水准", z=10),
            _point("SZ-SA", "AK", 980, "石坳互通水准", z=20),
        ]
        station, back, level, meta = match_stations(
            "标志工程白岭互通AK1+100右侧",
            "AK",
            1100,
            traverse,
            levels,
            {"白岭互通": 6500},
        )
        self.assertEqual(meta["path"], "corridor_stake")
        self.assertEqual({station["name"], back["name"]}, {"BL1", "BL2"})
        self.assertEqual(level["name"], "SZ-BL")
        self.assertFalse(meta["miss_t"])
        self.assertFalse(meta["miss_l"])

    def test_global_match_stops_at_2km(self):
        traverse = [
            _point("N1", "K", 1000, "主线K1+000"),
            _point("N2", "K", 1500, "主线K1+500"),
        ]
        levels = [_point("SZ", "K", 1200, "主线水准", z=8)]
        station, _back, level, meta = match_stations(
            "标志工程K10+000右侧",
            "K",
            10000,
            traverse,
            levels,
            {},
        )
        self.assertEqual(meta["path"], "global")
        self.assertIsNone(station)
        self.assertIsNone(level)
        self.assertTrue(meta["miss_t"])
        self.assertTrue(meta["miss_l"])

        station, back, level, meta = match_stations(
            "标志工程K1+200右侧",
            "K",
            1200,
            traverse,
            levels,
            {},
        )
        self.assertEqual(station["name"], "N1")
        self.assertEqual(back["name"], "N2")
        self.assertEqual(level["name"], "SZ")
        self.assertFalse(meta["miss_t"])

    def test_no_stake_uses_corridor_without_2km_cap(self):
        traverse = [
            _point("K1", "K", 6000, "辐射整个白岭互通"),
            _point("K2", "K", 7000, "白岭互通主线"),
        ]
        levels = [_point("SZ", "K", 6500, "辐射整个白岭互通", z=9)]
        station, back, level, meta = match_stations(
            "标志工程白岭互通单柱式标志A匝道右侧",
            "",
            None,
            traverse,
            levels,
            {"白岭互通": 6500.0},
        )
        self.assertEqual(meta["path"], "corridor_no_stake")
        self.assertTrue(meta["no_stake_corridor_fill"])
        self.assertEqual({station["name"], back["name"]}, {"K1", "K2"})
        self.assertEqual(level["name"], "SZ")

    def test_side_and_prefix_cleanup(self):
        raw = "标志工程K2+600单柱式标志-江西交通服务热线路线右侧"
        self.assertEqual(clean_b(raw, "标志工程"), "K2+600单柱式标志-江西交通服务热线")
        self.assertEqual(detect_side(raw), ("右幅", ""))

    def test_zuoxian_youxian_suffix_stripped_like_zuoce_youce(self):
        """词尾「左线」「右线」与「左侧」「右侧」同剥；C 仍为左幅/右幅。"""
        cases = [
            ("标志工程K2+600单柱式标志右线", "标志工程", "K2+600单柱式标志", "右幅"),
            ("标志工程K2+600单柱式标志左线", "标志工程", "K2+600单柱式标志", "左幅"),
            (
                "标线工程K0+000~K01+326路侧护栏-轮廓标右线",
                "标线工程",
                "K0+000~K01+326路侧护栏-轮廓标",
                "右幅",
            ),
            (
                "标线工程K0+000~K01+310路侧护栏-轮廓标左线",
                "标线工程",
                "K0+000~K01+310路侧护栏-轮廓标",
                "左幅",
            ),
            (
                "波形护栏工程K01+326~K01+349路侧护栏-路侧波形梁钢护栏右线",
                "波形护栏工程",
                "K01+326~K01+349路侧护栏-路侧波形梁钢护栏",
                "右幅",
            ),
            (
                "波形护栏工程K01+316~K01+339路侧护栏-路侧波形梁钢护栏左线",
                "波形护栏工程",
                "K01+316~K01+339路侧护栏-路侧波形梁钢护栏",
                "左幅",
            ),
            # 先有左线/右线、再接左侧/右侧：两侧别都剥掉，C 以左侧/右侧为准。
            (
                "标线工程K0+000~K01+326路侧护栏-轮廓标右线右侧",
                "标线工程",
                "K0+000~K01+326路侧护栏-轮廓标",
                "右幅",
            ),
            (
                "标线工程K0+000~K01+326路侧护栏-轮廓标右线左侧",
                "标线工程",
                "K0+000~K01+326路侧护栏-轮廓标",
                "左幅",
            ),
            (
                "标线工程K0+000~K01+310路侧护栏-轮廓标左线右侧",
                "标线工程",
                "K0+000~K01+310路侧护栏-轮廓标",
                "右幅",
            ),
            (
                "标线工程K0+000~K01+310路侧护栏-轮廓标左线左侧",
                "标线工程",
                "K0+000~K01+310路侧护栏-轮廓标",
                "左幅",
            ),
            (
                "波形护栏工程K01+326~K01+349路侧护栏-路侧波形梁钢护栏右线右侧",
                "波形护栏工程",
                "K01+326~K01+349路侧护栏-路侧波形梁钢护栏",
                "右幅",
            ),
            (
                "波形护栏工程K01+316~K01+339路侧护栏-路侧波形梁钢护栏左线左侧",
                "波形护栏工程",
                "K01+316~K01+339路侧护栏-路侧波形梁钢护栏",
                "左幅",
            ),
        ]
        for raw, prefix, expected_b, expected_side in cases:
            cleaned = clean_b(raw, prefix)
            self.assertNotIn("左线", cleaned, raw)
            self.assertNotIn("右线", cleaned, raw)
            self.assertNotIn("左侧", cleaned, raw)
            self.assertNotIn("右侧", cleaned, raw)
            self.assertEqual(cleaned, expected_b, raw)
            side, _note = detect_side(raw)
            self.assertEqual(side, expected_side, raw)

        # 方案 A 只剥词尾。中间的「右线/左线」属于构造描述，不整段删掉。
        mid = "标线工程K51+930主线标线、突起路钮右线-路面标线车道边缘线、车道分界线"
        mid_b = clean_b(mid, "标线工程")
        self.assertIn("右线-", mid_b)
        self.assertEqual(detect_side(mid)[0], "右幅")

    def test_sample_ledgers_strip_line_side_suffix(self):
        """仓库样例 JA-001/002/003：词尾左线/右线（可再接左侧/右侧）不留在 B。"""
        sample = REPO_ROOT / "share" / "ja-params-sample-001"
        tail = re.compile(r"(左线|右线)(左侧|右侧)?$")
        for tag in ("JA-001", "JA-002", "JA-003"):
            cfg = ITEM_SPECS[tag]
            rows = load_ledger_b(sample / cfg["ledger_name"], cfg["ledger_sheet"])
            matched = [raw for raw in rows if tail.search(raw)]
            self.assertGreater(len(matched), 0, tag)
            for raw in matched:
                cleaned = clean_b(raw, cfg["eng_prefix"])
                self.assertNotIn("左线", cleaned, raw)
                self.assertNotIn("右线", cleaned, raw)
                self.assertNotIn("左侧", cleaned, raw)
                self.assertNotIn("右侧", cleaned, raw)
                suffix = tail.search(raw).group(0)
                if suffix.endswith("右侧") or suffix.endswith("右线"):
                    expected = "右幅"
                else:
                    expected = "左幅"
                side, _note = detect_side(raw)
                self.assertEqual(side, expected, raw)

    def test_instruction_parser_on_sample(self):
        sample = REPO_ROOT / "share" / "ja-params-sample-001"
        text1 = (sample / "资料参数执行说明-JA-001.md").read_text(encoding="utf-8")
        text2 = (sample / "资料参数执行说明-JA-002.md").read_text(encoding="utf-8")
        text3 = (sample / "资料参数执行说明-JA-003.md").read_text(encoding="utf-8")
        self.assertEqual(parse_def(text1), ("交安工程", "交通标志", "交通标志"))
        self.assertEqual(parse_def(text2), ("交安工程", "路面标线", "安全设施"))
        self.assertEqual(parse_def(text3), ("交安工程", "波形护栏", "安全设施"))
        self.assertEqual(parse_ja002_constants(text2), (2.2, 0.1, 0.01))
        self.assertEqual(ITEM_SPECS["JA-003"]["template_sheet"], "波形护栏-JA-003")
        self.assertEqual(ITEM_SPECS["JA-003"]["stem"], "波形护栏-JA-003")

    def test_resolve_instruction_path_sticks_to_one_side(self):
        data_dir = Path("/tmp/project-data")
        name = "资料参数执行说明-JA-001.md"
        self.assertEqual(resolve_instruction_path(name, data_dir, None), data_dir / name)
        self.assertEqual(resolve_instruction_path(name, data_dir, "local"), data_dir / name)
        online = resolve_instruction_path(name, data_dir, "online")
        self.assertEqual(online, REPO_INSTRUCTION_DIR / name)
        self.assertEqual(online.parent, REPO_ROOT / "share" / "ja-params-sample-001")
        self.assertNotEqual(online.parent, data_dir)
        with self.assertRaises(InputError):
            resolve_instruction_path(name, data_dir, "both")

    def test_prepare_cfg_source_does_not_cross_sides(self):
        """用线上文件不读 data-dir；用本地文件和未指定都不读规则库。"""
        spec = ITEM_SPECS["JA-001"]
        name = spec["instruction_name"]
        local_text = _instruction_with_def(spec["template_sheet"], "本地甲", "本地乙", "本地丙")
        repo_text = _instruction_with_def(spec["template_sheet"], "线上甲", "线上乙", "线上丙")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            repo_dir = root / "repo"
            data_dir.mkdir()
            repo_dir.mkdir()
            (data_dir / name).write_text(local_text, encoding="utf-8")
            (repo_dir / name).write_text(repo_text, encoding="utf-8")

            with mock.patch("tools.ja_params.builder.REPO_INSTRUCTION_DIR", repo_dir):
                online = prepare_cfg(spec, "001", data_dir, "online")
                local = prepare_cfg(spec, "001", data_dir, "local")
                default = prepare_cfg(spec, "001", data_dir, None)
                (data_dir / name).unlink()
                local_missing = prepare_cfg(spec, "001", data_dir, "local")
                default_missing = prepare_cfg(spec, "001", data_dir, None)
                (data_dir / name).write_text(local_text, encoding="utf-8")
                (repo_dir / name).unlink()
                online_missing = prepare_cfg(spec, "001", data_dir, "online")

            self.assertEqual((online["D"], online["E"], online["F"]), ("线上甲", "线上乙", "线上丙"))
            self.assertIn("用线上文件", "\n".join(online["notes"]))
            self.assertNotIn("本地甲", "\n".join(online["notes"]))

            self.assertEqual((local["D"], local["E"], local["F"]), ("本地甲", "本地乙", "本地丙"))
            self.assertIn("用本地文件", "\n".join(local["notes"]))
            self.assertNotIn("线上甲", "\n".join(local["notes"]))

            self.assertEqual((default["D"], default["E"], default["F"]), ("本地甲", "本地乙", "本地丙"))
            self.assertIn("已读取执行说明: " + name, "\n".join(default["notes"]))
            self.assertNotIn("用线上文件", "\n".join(default["notes"]))
            self.assertNotIn("用本地文件", "\n".join(default["notes"]))

            builtin = (spec["D"], spec["E"], spec["F"])
            self.assertEqual((local_missing["D"], local_missing["E"], local_missing["F"]), builtin)
            self.assertIn("未改用规则库文件", "\n".join(local_missing["notes"]))
            self.assertNotIn("线上甲", "\n".join(local_missing["notes"]))

            self.assertEqual(
                (default_missing["D"], default_missing["E"], default_missing["F"]),
                builtin,
            )
            self.assertIn(
                "数据目录没有执行说明，D/E/F 与常量使用内置规则。",
                default_missing["notes"],
            )
            self.assertNotIn("线上甲", "\n".join(default_missing["notes"]))

            # 规则库没有这份说明、本机有另一份时，仍不改读本机文件。
            self.assertEqual(
                (online_missing["D"], online_missing["E"], online_missing["F"]),
                builtin,
            )
            self.assertIn("未改用本机文件", "\n".join(online_missing["notes"]))

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / name).write_text(local_text, encoding="utf-8")
            live = prepare_cfg(spec, "001", data_dir, "online")
        self.assertEqual(REPO_INSTRUCTION_DIR, REPO_ROOT / "share" / "ja-params-sample-001")
        self.assertTrue((REPO_INSTRUCTION_DIR / name).is_file())
        self.assertEqual((live["D"], live["E"], live["F"]), ("交安工程", "交通标志", "交通标志"))
        self.assertIn("用线上文件", "\n".join(live["notes"]))
        self.assertNotIn("本地甲", "\n".join(live["notes"]))

    def test_template_lookup_uses_data_dir_then_share(self):
        self.assertTrue(CANONICAL_TEMPLATE.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self.assertEqual(resolve_template(data_dir, None), CANONICAL_TEMPLATE.resolve())
            local = data_dir / "参数样板.xlsx"
            local.write_bytes(b"local-override")
            self.assertEqual(resolve_template(data_dir, None), local.resolve())
        hits = [path.relative_to(REPO_ROOT).as_posix() for path in REPO_ROOT.rglob("参数样板.xlsx")]
        self.assertEqual(hits, ["share/参数样板.xlsx"])
        sample = REPO_ROOT / "share" / "ja-params-sample-001"
        self.assertFalse((sample / "参数样板.xlsx").exists())


if __name__ == "__main__":
    unittest.main()
