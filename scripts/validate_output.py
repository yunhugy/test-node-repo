#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MJSON = ROOT / "m.json"
REPORT = ROOT / "report.json"
DIFF = ROOT / "diff_report.json"
HEALTH = ROOT / "state" / "health_history.json"


def main() -> None:
    payload = json.loads(MJSON.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    diff_report = json.loads(DIFF.read_text(encoding="utf-8"))
    health = json.loads(HEALTH.read_text(encoding="utf-8"))

    sites = payload.get("sites")
    if not isinstance(sites, list) or len(sites) < 10:
        raise SystemExit("m.json sites 数量异常")

    seen = set()
    for idx, site in enumerate(sites):
        if not isinstance(site, dict):
            raise SystemExit(f"sites[{idx}] 不是对象")
        if not site.get("key") or not site.get("name"):
            raise SystemExit(f"sites[{idx}] 缺少 key 或 name")
        fingerprint = json.dumps(site, ensure_ascii=False, sort_keys=True)
        if fingerprint in seen:
            raise SystemExit(f"sites[{idx}] 重复")
        seen.add(fingerprint)

    if report.get("validation_errors"):
        raise SystemExit("report.json 存在 validation_errors")

    if not isinstance(diff_report.get("added"), list):
        raise SystemExit("diff_report.json 缺少 added 列表")

    if not isinstance(health.get("sites"), dict):
        raise SystemExit("health_history.json 结构异常")

    print("validation ok")


if __name__ == "__main__":
    main()
