#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

REPO = "yunhugy/test-node-repo"
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATE_DIR = ROOT / "state"
OUT_JSON = ROOT / "m.json"
OUT_SUB = ROOT / "sub.txt"
OUT_REPORT = ROOT / "report.json"
OUT_DIFF = ROOT / "diff_report.json"
STATE_HEALTH = STATE_DIR / "health_history.json"
TMP_DIR = Path("/tmp/refresh_workdir")
UPSTREAM_REPO = "https://github.com/fishforks/ol.git"
UPSTREAM_DIR = TMP_DIR / "ol"

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
MAX_DYNAMIC_SITES = int(os.getenv("MAX_DYNAMIC_SITES", "6"))
MIN_SITE_COUNT = int(os.getenv("MIN_SITE_COUNT", "10"))
ROLLBACK_MIN_RATIO = float(os.getenv("ROLLBACK_MIN_RATIO", "0.7"))
HEALTH_HISTORY_LIMIT = int(os.getenv("HEALTH_HISTORY_LIMIT", "20"))

DEFAULT_LIVES = [
    {
        "name": "范明明IPv6",
        "type": 0,
        "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u",
        "playerType": 1,
        "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
        "logo": "https://epg.112114.xyz/logo/{name}.png",
    },
    {
        "name": "YueChan综合",
        "type": 0,
        "url": "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
        "playerType": 1,
        "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
        "logo": "https://epg.112114.xyz/logo/{name}.png",
    },
]

DEFAULT_PARSES = [
    {"name": "线路1", "type": 0, "url": "https://jx.jsonplayer.com/player/?url="},
    {"name": "线路2", "type": 0, "url": "https://jx.xmflv.com/?url="},
    {"name": "线路3", "type": 0, "url": "https://jx.bajiecaiji.com/jiexi/?url="},
]

DEFAULT_FLAGS = [
    "youku", "qq", "iqiyi", "qiyi", "letv", "sohu", "tudou", "pptv", "mgtv", "wasu", "bilibili"
]


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clone_or_update_upstream() -> Tuple[Optional[Path], List[str]]:
    logs: List[str] = []
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if (UPSTREAM_DIR / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(UPSTREAM_DIR), "pull", "--ff-only"],
            capture_output=True,
            text=True,
            check=False,
        )
        logs.append(f"git pull exit={result.returncode}")
        if result.stdout.strip():
            logs.append(result.stdout.strip())
        if result.stderr.strip():
            logs.append(result.stderr.strip())
        if result.returncode == 0:
            return UPSTREAM_DIR, logs
    else:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", UPSTREAM_REPO, str(UPSTREAM_DIR)],
            capture_output=True,
            text=True,
            check=False,
        )
        logs.append(f"git clone exit={result.returncode}")
        if result.stdout.strip():
            logs.append(result.stdout.strip())
        if result.stderr.strip():
            logs.append(result.stderr.strip())
        if result.returncode == 0:
            return UPSTREAM_DIR, logs

    return None, logs


def normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def site_endpoint_for_check(site: Dict[str, Any]) -> Optional[str]:
    if site.get("type") == 1:
        api = normalize_url(site.get("api", ""))
        return api or None

    ext = site.get("ext")
    if isinstance(ext, str):
        if ext.startswith("./"):
            return None
        if "$$$" in ext:
            for part in ext.split("$$$"):
                part = part.strip()
                if part.startswith("http://") or part.startswith("https://"):
                    return normalize_url(part)
        if ext.startswith("http://") or ext.startswith("https://"):
            return normalize_url(ext)
    elif isinstance(ext, dict):
        for key in ("site", "siteUrl", "url"):
            value = ext.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return normalize_url(value)
    return None


def request_ok(url: str) -> Tuple[bool, str, Optional[int], Optional[str]]:
    try:
        head_resp = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if head_resp.status_code < 400:
            return True, "HEAD", head_resp.status_code, None
        if head_resp.status_code not in (403, 405):
            return False, "HEAD", head_resp.status_code, None
    except requests.RequestException as exc:
        head_error = str(exc)
    else:
        head_error = None

    try:
        get_resp = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, stream=True)
        ok = get_resp.status_code < 400
        status = get_resp.status_code
        get_resp.close()
        return ok, "GET", status, None if ok else f"HTTP {status}"
    except requests.RequestException as exc:
        return False, "GET", None, head_error or str(exc)


def validate_site(site: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = site_endpoint_for_check(site)
    if not endpoint:
        return {"ok": True, "method": "SKIP", "status": None, "endpoint": None, "error": None}
    ok, method, status, error = request_ok(endpoint)
    return {"ok": ok, "method": method, "status": status, "endpoint": endpoint, "error": error}


def make_site_key(name: str, url: str) -> str:
    base = f"{name}|{normalize_url(url)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]


def load_static_sites() -> List[Dict[str, Any]]:
    return load_json(DATA_DIR / "static_sites.json", default=[])


def load_dynamic_candidates() -> List[Dict[str, Any]]:
    return load_json(DATA_DIR / "dynamic_candidates.json", default=[])


def load_existing_payload() -> Optional[Dict[str, Any]]:
    return load_json(OUT_JSON, default=None)


def load_health_history() -> Dict[str, Any]:
    return load_json(STATE_HEALTH, default={"sites": {}})


def save_health_history(history: Dict[str, Any]) -> None:
    save_json(STATE_HEALTH, history)


def update_health_history(history: Dict[str, Any], checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    sites = history.setdefault("sites", {})
    timestamp = utc_now_iso()

    for check in checks:
        endpoint = check.get("endpoint") or f"virtual:{check.get('name')}"
        item = sites.setdefault(endpoint, {"name": check.get("name"), "history": []})
        item["name"] = check.get("name")
        item.setdefault("history", []).append({
            "at": timestamp,
            "ok": bool(check.get("ok")),
            "method": check.get("method"),
            "status": check.get("status"),
        })
        item["history"] = item["history"][-HEALTH_HISTORY_LIMIT:]

        total = len(item["history"])
        success = sum(1 for row in item["history"] if row.get("ok"))
        item["success_rate"] = round(success / total, 4) if total else 0.0
        item["checks"] = total
        item["last_ok"] = any(row.get("ok") for row in reversed(item["history"]))
        item["last_checked_at"] = timestamp

    return history


def health_bonus(endpoint: Optional[str], history: Dict[str, Any]) -> int:
    if not endpoint:
        return 0
    site_info = history.get("sites", {}).get(endpoint)
    if not site_info:
        return 0
    rate = site_info.get("success_rate", 0)
    checks = site_info.get("checks", 0)
    if checks < 2:
        return 0
    return int(rate * 10)


def discover_dynamic_sites(upstream_root: Optional[Path], health_history: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    discovered: List[Dict[str, Any]] = []
    logs: List[Dict[str, Any]] = []
    candidates = load_dynamic_candidates()

    for item in candidates:
        candidate_url = item["url"]
        site = {
            "key": make_site_key(item["name"], candidate_url),
            "name": item["name"],
            "type": item.get("type", 1),
            "api": candidate_url,
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1,
            "priority": item.get("priority", 50),
            "category": item.get("category", "dynamic"),
        }
        result = validate_site(site)
        endpoint = result.get("endpoint")
        site["priority"] += health_bonus(endpoint, health_history)
        logs.append({"name": site["name"], **result, "priority": site["priority"]})
        if result["ok"]:
            discovered.append(site)

    if upstream_root and upstream_root.exists():
        existing_dynamic_endpoints = {normalize_url(item["api"]) for item in discovered if item.get("api")}
        for candidate_file in upstream_root.glob("*.json"):
            if len(discovered) >= MAX_DYNAMIC_SITES:
                break
            try:
                data = json.loads(candidate_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            api = data.get("api") or data.get("url")
            if not isinstance(api, str):
                continue
            api = normalize_url(api)
            if not api.startswith(("http://", "https://")):
                continue
            if api in existing_dynamic_endpoints:
                continue
            site = {
                "key": make_site_key(candidate_file.stem, api),
                "name": candidate_file.stem,
                "type": 1,
                "api": api,
                "searchable": 1,
                "quickSearch": 1,
                "filterable": 1,
                "priority": 40 + health_bonus(api, health_history),
                "category": "dynamic-auto",
            }
            result = validate_site(site)
            logs.append({"name": site["name"], **result, "priority": site["priority"]})
            if result["ok"]:
                discovered.append(site)
                existing_dynamic_endpoints.add(api)

    discovered.sort(key=lambda item: (-item.get("priority", 0), item.get("name", "")))
    return discovered[:MAX_DYNAMIC_SITES], logs


def deduplicate_sites(sites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_endpoint: Dict[str, Dict[str, Any]] = {}

    for site in sites:
        endpoint = site_endpoint_for_check(site) or f"virtual:{site.get('key')}"
        current = best_by_endpoint.get(endpoint)
        if current is None or site.get("priority", 0) > current.get("priority", 0):
            best_by_endpoint[endpoint] = site

    deduped = list(best_by_endpoint.values())
    deduped.sort(key=lambda item: (-item.get("priority", 0), item.get("name", "")))
    return deduped


def strip_internal_fields(site: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(site)
    clean.pop("priority", None)
    clean.pop("category", None)
    return clean


def build_payload(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "spider": "",
        "wallpaper": "https://bing.img.run/rand.php",
        "homepage": f"https://github.com/{REPO}",
        "sites": [strip_internal_fields(site) for site in sites],
        "lives": DEFAULT_LIVES,
        "parses": DEFAULT_PARSES,
        "flags": DEFAULT_FLAGS,
    }


def summarize_diff(old_payload: Optional[Dict[str, Any]], new_payload: Dict[str, Any]) -> Dict[str, Any]:
    old_sites = old_payload.get("sites", []) if isinstance(old_payload, dict) else []
    new_sites = new_payload.get("sites", []) if isinstance(new_payload, dict) else []

    def to_map(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        mapped = {}
        for item in items:
            endpoint = site_endpoint_for_check(item) or f"virtual:{item.get('key')}"
            mapped[endpoint] = item
        return mapped

    old_map = to_map(old_sites)
    new_map = to_map(new_sites)
    old_keys = set(old_map)
    new_keys = set(new_map)

    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    same = sorted(old_keys & new_keys)
    changed = []

    for key in same:
        old_item = old_map[key]
        new_item = new_map[key]
        if json.dumps(old_item, ensure_ascii=False, sort_keys=True) != json.dumps(new_item, ensure_ascii=False, sort_keys=True):
            changed.append(key)

    return {
        "old_site_count": len(old_sites),
        "new_site_count": len(new_sites),
        "added": [{"endpoint": key, "name": new_map[key].get("name")} for key in added],
        "removed": [{"endpoint": key, "name": old_map[key].get("name")} for key in removed],
        "changed": [{"endpoint": key, "name": new_map[key].get("name")} for key in changed],
    }


def should_rollback(old_payload: Optional[Dict[str, Any]], new_payload: Dict[str, Any], errors: List[str]) -> Tuple[bool, str]:
    if errors:
        return True, "payload 校验失败"
    if not isinstance(old_payload, dict):
        return False, "无历史产物，跳过回滚判断"

    old_count = len(old_payload.get("sites", []))
    new_count = len(new_payload.get("sites", []))
    if old_count <= 0:
        return False, "历史站点数为空，跳过回滚判断"

    ratio = new_count / old_count
    if ratio < ROLLBACK_MIN_RATIO:
        return True, f"站点数量下降过多：{new_count}/{old_count} < {ROLLBACK_MIN_RATIO:.2f}"

    return False, "站点数量正常"


def build_subscription_text(sites: List[Dict[str, Any]], report: Dict[str, Any], diff_report: Dict[str, Any]) -> str:
    lines = [
        "# OK影视增强版订阅",
        "",
        "主配置：",
        f"https://cdn.jsdelivr.net/gh/{REPO}@main/m.json",
        "",
        "备用直链：",
        f"https://raw.githubusercontent.com/{REPO}/main/m.json",
        "",
        "加速备用：",
        f"https://ghproxy.net/https://raw.githubusercontent.com/{REPO}/main/m.json",
        "",
        "站点统计：",
        f"- 总站点数：{report['site_count']}",
        f"- 稳定源：{report['stats']['stable_sites']}",
        f"- 公益/工具源：{report['stats']['public_sites']}",
        f"- 动态补充源：{report['stats']['dynamic_sites']}",
        "",
        "本次变化：",
        f"- 新增：{len(diff_report['added'])}",
        f"- 移除：{len(diff_report['removed'])}",
        f"- 变更：{len(diff_report['changed'])}",
        "",
        "当前保留站点：",
    ]

    for site in sites:
        endpoint = site_endpoint_for_check(site)
        label = site.get("name", "未知站点")
        if endpoint:
            lines.append(f"- {label}: {endpoint}")
        else:
            lines.append(f"- {label}: {site.get('api', '内置/本地配置')}")

    removed = report.get("removed_candidates", [])
    lines.extend(["", "失效或未纳入动态候选："])
    if removed:
        for item in removed:
            lines.append(f"- {item['name']}: {item.get('endpoint') or 'N/A'}")
    else:
        lines.append("- 无")

    lines.extend([
        "",
        "说明：",
        "- 可直接把上方主配置链接填入 OK 影视订阅地址",
        "- 仓库已加入健康度记录、去重、校验、差异报告、失败回滚保护",
        "- 若自动刷新异常，将优先保留现有可用主配置，避免坏数据覆盖",
    ])
    return "\n".join(lines) + "\n"


def validate_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    sites = payload.get("sites")
    if not isinstance(sites, list) or not sites:
        errors.append("sites 不能为空")
        return errors

    if len(sites) < MIN_SITE_COUNT:
        errors.append(f"sites 数量过少：{len(sites)} < {MIN_SITE_COUNT}")

    seen = set()
    for index, site in enumerate(sites):
        if not isinstance(site, dict):
            errors.append(f"sites[{index}] 不是对象")
            continue
        key = site.get("key")
        name = site.get("name")
        if not key or not name:
            errors.append(f"sites[{index}] 缺少 key/name")
        endpoint = site_endpoint_for_check(site) or f"virtual:{key}"
        if endpoint in seen:
            errors.append(f"发现重复站点端点：{endpoint}")
        seen.add(endpoint)
    return errors


def git_commit_and_push() -> None:
    subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=False)
    subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=False)
    subprocess.run(["git", "add", "m.json", "sub.txt", "report.json", "diff_report.json", "state/health_history.json"], cwd=ROOT, check=False)

    status = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False)
    if status.returncode == 0:
        print("ℹ️ 无变动，跳过提交")
        return

    commit_message = f"refresh subscriptions {utc_now_iso()}"
    subprocess.run(["git", "commit", "-m", commit_message], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "HEAD"], cwd=ROOT, check=True)
    print("✅ 更新并推送完成")


def main() -> None:
    old_payload = load_existing_payload()
    health_history = load_health_history()
    upstream_root, upstream_logs = clone_or_update_upstream()
    static_sites = load_static_sites()
    dynamic_sites, dynamic_logs = discover_dynamic_sites(upstream_root, health_history)
    health_history = update_health_history(health_history, dynamic_logs)

    merged_sites = deduplicate_sites(static_sites + dynamic_sites)
    payload = build_payload(merged_sites)
    errors = validate_payload(payload)
    diff_report = summarize_diff(old_payload, payload)
    rollback, rollback_reason = should_rollback(old_payload, payload, errors)

    stats = {
        "stable_sites": sum(1 for item in merged_sites if item.get("category") == "stable"),
        "public_sites": sum(1 for item in merged_sites if item.get("category") == "public"),
        "dynamic_sites": sum(1 for item in merged_sites if str(item.get("category", "")).startswith("dynamic")),
    }

    removed_candidates = [item for item in dynamic_logs if not item.get("ok")]
    report = {
        "generated_at": utc_now_iso(),
        "repo": REPO,
        "site_count": len(payload["sites"]),
        "stats": stats,
        "upstream": {
            "available": bool(upstream_root),
            "logs": upstream_logs,
        },
        "dynamic_checks": dynamic_logs,
        "removed_candidates": removed_candidates,
        "validation_errors": errors,
        "rollback": {
            "triggered": rollback,
            "reason": rollback_reason,
        },
    }

    save_health_history(health_history)
    save_json(OUT_DIFF, diff_report)

    if rollback:
        print("⚠️ 触发回滚保护：", rollback_reason)
        save_json(OUT_REPORT, report)
        if errors:
            sys.exit(1)
        print("ℹ️ 保留现有 m.json / sub.txt，不覆盖")
        return

    save_json(OUT_JSON, payload)
    OUT_SUB.write_text(build_subscription_text(merged_sites, report, diff_report), encoding="utf-8")
    save_json(OUT_REPORT, report)

    if os.getenv("GITHUB_ACTIONS") == "true":
        git_commit_and_push()
    else:
        print("✅ 本地生成完成（未执行 push）")


if __name__ == "__main__":
    main()
