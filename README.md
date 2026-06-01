# 2026 世界杯中文日历订阅 MVP（API-FOOTBALL 版）

这个项目用于生成一个可多人订阅的中文 `.ics` 日历 URL：

- 赛前显示：`世界杯：墨西哥 vs 南非`
- 赛后显示：`世界杯：墨西哥 2-1 南非`
- 每天北京时间 09:00 由 GitHub Actions 自动更新源文件
- 用户订阅 URL 后，会在日历客户端下一次刷新时看到更新


## 0. 关于 API Key 安全

不要把真实 API Key 写进代码或公开仓库。

正确方式是放到 GitHub Secrets：

```text
Settings → Secrets and variables → Actions → New repository secret
Name: API_FOOTBALL_KEY
Secret: 你的真实 Key
```

如果你已经在聊天、截图或公开页面暴露过 Key，建议在 API-SPORTS 后台重新生成/轮换一次，然后把新 Key 放到 Secrets。

## 1. 注册免费 API Key

推荐先用 API-FOOTBALL / API-SPORTS：

1. 注册账号
2. 获取 API Key
3. 在 GitHub 仓库设置里添加 Secret：`API_FOOTBALL_KEY`

项目默认使用：

```text
league=1
season=2026
```

即 FIFA World Cup 2026。

## 2. 上传到 GitHub

把本项目所有文件上传到一个公开仓库，例如：

```text
worldcup-cn-calendar
```

## 3. 开启 GitHub Pages

在仓库设置中：

```text
Settings → Pages → Deploy from a branch → main / root
```

开启后，你的订阅地址通常是：

```text
https://你的用户名.github.io/worldcup-cn-calendar/worldcup2026_cn.ics
```

## 4. 开启自动更新

GitHub Actions 已经配置：

```text
每天 UTC 01:00 自动运行，也就是北京时间 09:00
```

也可以在 Actions 页面手动点击 `Run workflow` 测试。

## 5. 本地测试

没有 API Key 时，脚本会使用 `data/fixtures_cache.json` 示例数据生成日历。

```bash
pip install -r requirements.txt
python scripts/build_calendar.py
```

如果你要在本地用真实 API Key 测试，可以这样做：

```bash
cp .env.example .env
# 编辑 .env，把 API_FOOTBALL_KEY 改成你的真实 Key
set -a
source .env
set +a
python scripts/build_calendar.py
```

注意：`.env` 已经加入 `.gitignore`，不要上传到 GitHub。

生成文件：

```text
worldcup2026_cn.ics
```

## 6. 重要限制

- 你可以保证每天 9 点更新 `.ics` 源文件。
- 但不能强制 Apple / Google / Outlook 在 9 点整刷新订阅日历。
- 小组赛球队、淘汰赛对阵会随着 API 数据更新而自动写入日历。
- 球队中文名依赖 `data/team_zh_map.json`，可随时补充。

## 7. 后续可扩展

可以继续扩展为多个订阅链接：

```text
/all.ics          全部比赛
/knockout.ics     淘汰赛
/argentina.ics    阿根廷队
/england.ics      英格兰队
/japan.ics        日本队
```
