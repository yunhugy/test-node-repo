# test-node-repo

## 豪华版影视订阅源

本仓库现已升级为 **静态基线 + 动态探测 + 健康度记录 + 校验保护 + 回滚保护** 的订阅生成模式，目标是：

- 保留当前优质稳定源，不被坏刷新覆盖
- 自动补充可用动态源，并记录健康度历史
- 生成统一的 `m.json` / `sub.txt` / `report.json` / `diff_report.json`
- 在 GitHub Actions 中定时刷新并自动校验

## 文件说明

| 类别 | 文件 | 主要功能 |
|------|------|----------|
| 主订阅 | `sub.txt` | 人类可读的订阅入口与站点摘要 |
| 主配置 | `m.json` | OK 影视订阅 JSON 主文件 |
| 报告 | `report.json` | 本次刷新结果、动态探测记录、回滚状态 |
| 差异报告 | `diff_report.json` | 与上次产物相比的新增/删除/变化 |
| 健康历史 | `state/health_history.json` | 动态站点健康度记录 |
| 静态基线 | `data/static_sites.json` | 手工维护的稳定/公益优质源 |
| 动态候选 | `data/dynamic_candidates.json` | 自动探测补充候选源 |
| 刷新脚本 | `scripts/refresh_subscriptions.py` | 合并、探活、去重、评分、生成产物 |
| 校验脚本 | `scripts/validate_output.py` | 校验输出结果是否可用 |

## 推荐链接

| 类别 | 工具 | 主要功能 |
|------|------|----------|
| 稳定订阅 | ghproxy | `https://ghproxy.net/https://raw.githubusercontent.com/yunhugy/test-node-repo/main/m.json` |
| 主配置 | jsDelivr | `https://cdn.jsdelivr.net/gh/yunhugy/test-node-repo@main/m.json` |
| 人类说明 | GitHub Raw | `https://raw.githubusercontent.com/yunhugy/test-node-repo/main/sub.txt` |
| 仓库 | GitHub | `https://github.com/yunhugy/test-node-repo` |

## 自动刷新

- 工作流：`.github/workflows/refresh.yml`
- 触发方式：每 6 小时一次 + 手动触发
- 安全策略：若生成结果不通过校验，或站点数量异常下降，将保留现有主配置

## 本地使用

```bash
pip install -r requirements.txt
python scripts/refresh_subscriptions.py
python scripts/validate_output.py
```

## 免责声明

仅供学习与测试，请遵守相关法律法规。
