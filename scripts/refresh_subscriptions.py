#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, base64, os, sys, subprocess, datetime, hashlib
from pathlib import Path
import requests

TOKEN = os.getenv("GITHUB_TOKEN")          # CI 环境自动注入
REPO = "yunhugy/test-node-repo"            # 你的仓库
WORKDIR = Path("/tmp/refresh_workdir")
OUT_DIR = Path(".")                        # 仓库根目录（与 workflow 中的 run 命令同级）

# ---------- 1️⃣ 下载 fishforks/ol 仓库 ----------
def clone_ol():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    repo_dir = WORKDIR / "ol"
    if repo_dir.is_dir():
        subprocess.run(["git", "pull"], cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["git", "clone", "--depth", "1",
                        "https://github.com/fishforks/ol.git"], cwd=repo_dir)
    return repo_dir

# ---------- 2️⃣ 过滤 & 验证可用的 type=1 接口 ----------
VALID_SITES = []
def detect_sites(root: Path):
    """
    遍历 *.txt，找出形如：
        "api": "https://xxx/xxx.txt"
    并通过一次 HEAD 请求确保能访问（200 OK）。
    """
    for txt_path in root.glob("*.txt"):
        try:
            data = json.loads(txt_path.read_text(encoding="utf-8"))
            api = data.get("api") or data.get("url")
            if not api:
                continue
            # 必须是完整的 HTTP(S) URL，且指向 .txt 文件
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
        except Exception as e:
            continue

# ---------- 3️⃣ 构造标准 JSON（m.json） ----------
def build_json():
    sites = VALID_SITES[:7]          # 最多保留 7 条，超出可自行截断
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
    OUT_DIR / "m.json".write_text(json.dumps(payload, ensure_ascii=False, indent=2))

# ---------- 4️⃣ 生成说明显文件（sub.txt） ----------
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
        "## 可用站点（全部为 type=1 接口）",
    ]
    for s in VALID_SITES:
        lines.append(f"- {s['name']}   {s['api']}")
    lines.extend([
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

# ---------- 5️⃣ Git 提交（仅在有变更时） ----------
def git_commit_and_push():
    # 配置 Git
    subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=False)
    subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=False)

    # 检查是否有改动
    status = subprocess.run(
        ["git", "diff", "--quiet"], capture_output=True
    )
    if status.returncode != 0:        # 有改动
        subprocess.run(["git", "add", "m.json", "sub.txt"])
        # 自动生成 commit message，带上日期
        cm = f"refreshed subscriptions on {datetime.datetime.utcnow().isoformat()}Z"
        subprocess.run(["git", "commit", "-m", cm])
        subprocess.run(["git", "push", "origin", "HEAD"])
        print("✅ 更新并推送完成")
    else:
        print("ℹ️ 无变更，无需提交")

# ---------- 6️⃣ 主流程 ----------
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