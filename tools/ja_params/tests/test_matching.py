# -*- coding: utf-8 -*-
"""锁池、2km 和参数样板查找的小用例。不依赖样例成果工作簿。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.ja_params.builder import (
    CANONICAL_TEMPLATE,
    ITEM_SPECS,
    REPO_ROOT,
    clean_b,
    compute_zab,
    detect_side,
    extract_corridor,
    match_stations,
    parse_def,
    parse_ja002_constants,
    pick_ab_ja001,
    pick_ab_ja002,
    resolve_template,
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
