#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, hashlib, sys, subprocess, datetime, requests
from pathlib import Path
import os

TOKEN = os.getenv("GITHUB_TOKEN")          # GitHub 自动注入的 token
REPO = "yunhugy/test-node-repo"            # 你的仓库
WORKDIR = Path("/tmp/refresh_workdir")
OUT_DIR = Path(".")                        # 与工作流中路径保持一致

# --------------------------------------------------------------
# 1️⃣ 克隆 fishforks/ol 仓库（增量更新）
# --------------------------------------------------------------
def clone_ol():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    repo_dir = WORKDIR / "ol"
    if repo_dir.is_dir():
        subprocess.run(["git", "pull"], cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["git", "clone", "--depth", "1",
                        "https://github.com/fishforks/ol.git"], cwd=repo_dir)
    return repo_dir

# --------------------------------------------------------------
# 2️⃣ 过滤并验证可用的 type=1 接口 + 特殊站
# --------------------------------------------------------------
VALID_SITES = []

def detect_sites(root: Path):
    # ---- 2.1 自动遍历所有 *.txt，寻找 type=1 接口 ----
    for txt_path in root.glob("*.txt"):
        try:
            data = json.loads(txt_path.read_text(encoding="utf-8"))
            api = data.get("api") or data.get("url")
            if not api:
                continue
            # 必须是完整的 HTTP(S) URL 且以 .txt 结尾
            if not api.startswith("https://") or not api.lower().endswith(".txt"):
                continue
            # HEAD 检查可达性
            r = requests.head(api, timeout=8, allow_redirects=True)
            if r.status_code == 200:
                VALID_SITES.append({
                    "key": hashlib.sha1(api.encode()).hexdigest()[:8],
                    "name": txt_path.stem,
                    "type": 1,
                    "api": api,
                    "searchable": 1,
                    "quickSearch": 1,
                    "filterable": 1
                })
        except Exception:
            continue

    # ---- 2.2 专门处理 木偶、玩偶、豆瓣、网盘登录（来自 fishforks/ol 已知路径）----
    extra_candidates = {
        "木偶（哥哥）": "https://raw.githubusercontent.com/fishforks/ol/main/PG.txt",
        "玩偶（哥哥）": "https://raw.githubusercontent.com/fishforks/ol/main/小马.txt",
        "豆瓣（电影）": "https://raw.githubusercontent.com/fishforks/ol/main/云星日记.txt",
        "网盘登录（alist）": "https://raw.githubusercontent.com/fishforks/ol/main/老刘备.txt",
    }
    for key, url in extra_candidates.items():
        if any(s["api"] == url for s in VALID_SITES):
            continue
        try:
            r = requests.head(url, timeout=8, allow_redirects=True)
            if r.status_code == 200:
                VALID_SITES.append({
                    "key": hashlib.sha1(url.encode()).hexdigest()[:8],
                    "name": key,
                    "type": 1,
                    "api": url,
                    "searchable": 1,
                    "quickSearch": 1,
                    "filterable": 1
                })
            else:
                print(f"[DEBUG] {key} ({url}) unreachable, skip.")
        except Exception as e:
            print(f"[DEBUG] {key} ({url}) error: {e}, skip.")

def build_json():
    # --------------------------------------------------------------
    # 3️⃣ 专门加入 木偶哥哥 实际可用的 CSP/JSON 接口（多个候选项）
    # --------------------------------------------------------------
    # 木偶哥哥常用的JSON接口（从已知TVBox配置中提取）
    wogg_candidates = [
        {
            "name": "木偶哥哥（csp）",
            "key": "csp_wogg",
            "type": 3,
            "api": "csp_Wogg",
            "ext": "https://666.666291.xyz/",
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1
        },
        {
            "name": "木偶全站",
            "key": "wogg_full",
            "type": 3,
            "api": "csp_Wogg",
            "ext": "https://www.wogg.net/",
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1
        }
    ]
    # 先取现有的 type=1 站点，最多保留7个
    sites = VALID_SITES[:7] + wogg_candidates

    # --------------------------------------------------------------
    # lives 与 parses 保持不变
    # --------------------------------------------------------------
    lives = [
        {
            "name": "范明明IPv6",
            "type": 0,
            "url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u",
            "playerType": 1,
            "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
            "logo": "https://epg.112114.xyz/logo/{name}.png"
        },
        {
            "name": "悠然综合",
            "type": 0,
            "url": "https://raw.githubusercontent.com/fishforks/ol/main/悠然综合.txt",
            "playerType": 1,
            "epg": "https://epg.112114.xyz/?ch={name}&date={date}",
            "logo": "https://epg.112114.xyz/logo/{name}.png"
        }
    ]
    parses = [
        {"name": "线路1", "type": 0, "url": "https://jx.jsonplayer.com/player/?url="},
        {"name": "线路2", "type": 0, "url": "https://jx.xmflv.com/?url="},
        {"name": "线路3", "type": 0, "url": "https://jx.bajiecaiji.com/jiexi/?url="}
    ]

    payload = {
        "homepage": f"https://github.com/{REPO}",
        "wallpaper": "https://bing.img.run/rand.php",
        "sites": sites,
        "lives": lives,
        "parses": parses,
        "flags": [
            "youku","qq","iqiyi","qiyi","letv","sohu","tudou","pptv","mgtv","wasu","bilibili"
        ]
    }
    OUT_DIR / "m.json".write_text(
        json.dumps(payload, ensure_ascii=False, indent=2)
    )

# --------------------------------------------------------------
# 4️⃣ 生成使用说明文档（sub.txt）
# --------------------------------------------------------------
def build_sub_txt():
    lines = [
        "# OK影视·自动刷新版订阅（基于 fishforks/ol）",
        "",
        "## 主配置",
        "https://cdn.jsdelivr.net/gh/yunhugy/test-node-repo@main/m.json",
        "",
        "## 备用直链",
        "https://raw.githubusercontent.com/yunhugy/test-node-repo/main/m.json",
        "",
        "## 加速备用（ghproxy）",
        "https://ghproxy.net/https://raw.githubusercontent.com/yunhugy/test-node-repo/main/m.json",
        "",
        "## 可用站点（type=1 + type=3 混合）",
    ]

    for s in sorted(VALID_SITES, key=lambda x: x["name"]):
        lines.append(f"- {s['name']}   {s['api']}")

    lines.extend([
        "",
        "## 木偶哥哥（666.666291.xyz）",
        "- 木偶哥哥（csp）   type=3, api=csp_Wogg, ext=https://666.666291.xyz/",
        "- 木偶全站         type=3, api=csp_Wogg, ext=https://www.wogg.net/",
        "",
        "## 直播源",
        "- 范明明IPv6   （已在 lives 中）",
        "",
        "## 解析源（3 条）",
        "1. 线路1 → https://jx.jsonplayer.com/player/?url=",
        "2. 线路2 → https://jx.xmflv.com/?url=",
        "3. 线路3 → https://jx.bajiecaiji.com/jiexi/?url=",
        "",
        "⚠️ 注意：直接把上表中的任意一条链接填入 OK 影视的「订阅地址」即可，"
        "若出现空白请检查是否复制了多余的空格或换行。"
    ])

    (OUT_DIR / "sub.txt").write_text("\n".join(lines), encoding="utf-8")

# --------------------------------------------------------------
# 5️⃣ Git 提交（仅在有变动时）
# --------------------------------------------------------------
def git_commit_and_push():
    subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=False)
    subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=False)

    status = subprocess.run(["git", "diff", "--quiet"], capture_output=True)
    if status.returncode != 0:
        subprocess.run(["git", "add", "m.json", "sub.txt"])
        cm = f"refreshed subscriptions on {datetime.datetime.utcnow().isoformat()}Z"
        subprocess.run(["git", "commit", "-m", cm])
        subprocess.run(["git", "push", "origin", "HEAD"])
        print("✅ 更新并推送完成")
    else:
        print("ℹ️ 无变动，跳过提交")

def main():
    root = clone_ol()
    detect_sites(root)
    if not VALID_SITES:
        print("❌ 未检测到可用的 type=1 接口")
        sys.exit(1)

    build_json()
    build_sub_txt()
    git_commit_and_push()

if __name__ == "__main__":
    main()