import os
import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "worldcup2026_cn.ics"
CACHE = DATA / "fixtures_cache.json"

TEAM_ZH_PATH = DATA / "team_zh_map.json"
VENUE_ZH_PATH = DATA / "venue_zh_map.json"

TEAM_ZH = json.loads(TEAM_ZH_PATH.read_text(encoding="utf-8")) if TEAM_ZH_PATH.exists() else {}
VENUE_ZH = json.loads(VENUE_ZH_PATH.read_text(encoding="utf-8")) if VENUE_ZH_PATH.exists() else {}

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
LEAGUE_ID = os.getenv("API_FOOTBALL_LEAGUE_ID", "1")
SEASON = os.getenv("API_FOOTBALL_SEASON", "2026")
TIMEZONE_NAME = os.getenv("CALENDAR_TIMEZONE", "Asia/Shanghai")
TITLE_PREFIX = os.getenv("TITLE_PREFIX", "世界杯")

STATUS_ZH = {
    "TBD": "待定",
    "NS": "未开始",
    "1H": "上半场",
    "HT": "中场休息",
    "2H": "下半场",
    "ET": "加时赛",
    "BT": "加时中场",
    "P": "点球大战",
    "SUSP": "暂停",
    "INT": "中断",
    "FT": "已完赛",
    "AET": "加时完赛",
    "PEN": "点球完赛",
    "PST": "已推迟",
    "CANC": "已取消",
    "ABD": "已腰斩",
    "AWD": "判定结果",
    "WO": "弃权",
    "LIVE": "进行中",
}


def load_cache():
    if CACHE.exists():
        print("使用本地缓存 data/fixtures_cache.json 生成日历。")
        return json.loads(CACHE.read_text(encoding="utf-8"))
    print("没有找到本地缓存，生成空日历。")
    return []


def fetch_fixtures():
    """
    优先调用 API-FOOTBALL。
    如果免费计划暂不支持 2026，或 API 报错，则自动回退到本地缓存。
    """
    if not API_KEY:
        print("未配置 API_FOOTBALL_KEY，改用本地缓存。")
        return load_cache()

    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_KEY}
    params = {
        "league": LEAGUE_ID,
        "season": SEASON,
        "timezone": "UTC",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"API 请求失败，改用本地缓存。原因：{exc}")
        return load_cache()

    errors = payload.get("errors")
    if errors:
        print(f"API 返回错误，改用本地缓存。错误内容：{errors}")
        return load_cache()

    fixtures = payload.get("response", [])
    if not fixtures:
        print("API 返回空赛程，改用本地缓存。")
        return load_cache()

    CACHE.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"API 获取成功，已更新本地缓存，场次数：{len(fixtures)}")
    return fixtures


def esc(value):
    """
    ICS 字段转义。
    """
    text = str(value or "")
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    return text


def fold(line):
    """
    ICS 建议单行不要太长；这里做简单折行，兼容常见日历客户端。
    """
    raw = line.encode("utf-8")
    if len(raw) <= 73:
        return line

    parts = []
    current = ""

    for char in line:
        if len((current + char).encode("utf-8")) > 73:
            parts.append(current)
            current = " " + char
        else:
            current += char

    if current:
        parts.append(current)

    return "\r\n".join(parts)


def dt_utc(value):
    if not value:
        return None

    value = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def fmt_dt(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def zh_team(name):
    return TEAM_ZH.get(name or "", name or "待定球队")


def zh_venue(name):
    return VENUE_ZH.get(name or "", name or "")


def zh_status(short_status, long_status=""):
    return STATUS_ZH.get(short_status or "", long_status or short_status or "待定")


def stable_uid(fx):
    fixture = fx.get("fixture", {}) if isinstance(fx, dict) else {}
    fixture_id = fixture.get("id") or fx.get("id")

    if fixture_id:
        return f"worldcup2026-match-{fixture_id}@worldcup-cn-calendar"

    raw = json.dumps(fx, sort_keys=True, ensure_ascii=False)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"worldcup2026-match-{digest}@worldcup-cn-calendar"


def event_from_fixture(fx):
    fixture = fx.get("fixture", {})
    league = fx.get("league", {})
    teams = fx.get("teams", {})
    goals = fx.get("goals", {}) or {}
    score = fx.get("score", {}) or {}

    status = fixture.get("status", {}) or {}

    home_obj = teams.get("home", {}) or {}
    away_obj = teams.get("away", {}) or {}

    home_name = zh_team(home_obj.get("name"))
    away_name = zh_team(away_obj.get("name"))

    start = dt_utc(fixture.get("date"))
    if not start:
        return None

    end = start + timedelta(hours=2)

    short_status = status.get("short") or "NS"
    long_status = status.get("long") or ""
    status_cn = zh_status(short_status, long_status)

    home_goals = goals.get("home")
    away_goals = goals.get("away")

    finished = short_status in {"FT", "AET", "PEN"}

    if finished and home_goals is not None and away_goals is not None:
        summary = f"{TITLE_PREFIX}：{home_name} {home_goals}-{away_goals} {away_name}"
    else:
        summary = f"{TITLE_PREFIX}：{home_name} vs {away_name}"

    venue = fixture.get("venue", {}) or {}
    venue_name = zh_venue(venue.get("name"))
    venue_city = venue.get("city") or ""

    location_parts = [x for x in [venue_name, venue_city] if x]
    location = "，".join(location_parts)

    round_name = league.get("round") or "待定"

    description_lines = [
        "赛事：2026年美加墨世界杯",
        f"阶段：{round_name}",
        f"状态：{status_cn}",
        f"主队：{home_name}",
        f"客队：{away_name}",
    ]

    if location:
        description_lines.append(f"球场：{location}")

    if finished and home_goals is not None and away_goals is not None:
        description_lines.append(f"比分：{home_name} {home_goals}-{away_goals} {away_name}")

    penalty = score.get("penalty", {}) or {}
    if isinstance(penalty, dict):
        pen_home = penalty.get("home")
        pen_away = penalty.get("away")
        if pen_home is not None and pen_away is not None:
            description_lines.append(f"点球：{home_name} {pen_home}-{pen_away} {away_name}")

    description_lines.append(
        "说明：本日历源每日北京时间9点自动更新；实际显示时间取决于你的日历客户端刷新频率。"
    )

    description = "\n".join(description_lines)
    now = datetime.now(timezone.utc)

    return [
        "BEGIN:VEVENT",
        f"UID:{esc(stable_uid(fx))}",
        f"DTSTAMP:{fmt_dt(now)}",
        f"DTSTART:{fmt_dt(start)}",
        f"DTEND:{fmt_dt(end)}",
        f"SUMMARY:{esc(summary)}",
        f"LOCATION:{esc(location)}",
        f"DESCRIPTION:{esc(description)}",
        "END:VEVENT",
    ]


def build():
    fixtures = fetch_fixtures()

    events = []
    for fx in fixtures:
        event = event_from_fixture(fx)
        if event:
            events.extend(event)

    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//WorldCup CN Calendar//ChatGPT MVP//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(TITLE_PREFIX + '2026中文赛程赛果')}",
        f"X-WR-TIMEZONE:{esc(TIMEZONE_NAME)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]

    calendar_lines.extend(events)
    calendar_lines.append("END:VCALENDAR")

    OUT.write_text(
        "\r\n".join(fold(line) for line in calendar_lines) + "\r\n",
        encoding="utf-8",
    )

    print(f"生成完成：{OUT}")
    print(f"事件数：{len(events) // 9}")


if __name__ == "__main__":
    build()
