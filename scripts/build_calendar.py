import os, json, html, hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = ROOT / 'worldcup2026_cn.ics'
CACHE = DATA / 'fixtures_cache.json'
TEAM_ZH = json.loads((DATA/'team_zh_map.json').read_text(encoding='utf-8'))
VENUE_ZH = json.loads((DATA/'venue_zh_map.json').read_text(encoding='utf-8'))

API_KEY = os.getenv('API_FOOTBALL_KEY', '')
LEAGUE_ID = os.getenv('API_FOOTBALL_LEAGUE_ID', '1')
SEASON = os.getenv('API_FOOTBALL_SEASON', '2026')
TIMEZONE = os.getenv('CALENDAR_TIMEZONE', 'Asia/Shanghai')
TITLE_PREFIX = os.getenv('TITLE_PREFIX', '世界杯')

STATUS_ZH = {
    'TBD': '待定', 'NS': '未开始', '1H': '上半场', 'HT': '中场休息', '2H': '下半场',
    'ET': '加时赛', 'BT': '加时中场', 'P': '点球大战', 'SUSP': '暂停', 'INT': '中断',
    'FT': '已完赛', 'AET': '加时完赛', 'PEN': '点球完赛', 'PST': '已推迟', 'CANC': '已取消',
    'ABD': '已腰斩', 'AWD': '判定结果', 'WO': '弃权', 'LIVE': '进行中'
}

def esc(s):
    return str(s or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')

def fold(line):
    # ICS requires lines <=75 octets; this simple fold is enough for common calendar clients.
    raw = line.encode('utf-8')
    if len(raw) <= 73:
        return line
    parts, cur = [], ''
    for ch in line:
        if len((cur + ch).encode('utf-8')) > 73:
            parts.append(cur)
            cur = ' ' + ch
        else:
            cur += ch
    parts.append(cur)
    return '\r\n'.join(parts)

def dt_utc(value):
    if not value:
        return None
    value = value.replace('Z', '+00:00')
    return datetime.fromisoformat(value).astimezone(timezone.utc)

def fmt_dt(dt):
    return dt.strftime('%Y%m%dT%H%M%SZ')

def zh_team(name):
    return TEAM_ZH.get(name or '', name or '待定球队')

def zh_venue(name):
    return VENUE_ZH.get(name or '', name or '')

def stable_uid(fx):
    fid = fx.get('fixture', {}).get('id') or fx.get('id')
    if fid:
        return f'worldcup2026-match-{fid}@worldcup-cn-calendar'
    raw = json.dumps(fx, sort_keys=True, ensure_ascii=False)
    return 'worldcup2026-match-' + hashlib.md5(raw.encode()).hexdigest() + '@worldcup-cn-calendar'

def fetch_fixtures():
    if not API_KEY:
        if CACHE.exists():
            return json.loads(CACHE.read_text(encoding='utf-8'))
        raise SystemExit('缺少 API_FOOTBALL_KEY，且没有 data/fixtures_cache.json 缓存。')
    url = 'https://v3.football.api-sports.io/fixtures'
    headers = {'x-apisports-key': API_KEY}
    params = {'league': LEAGUE_ID, 'season': SEASON, 'timezone': 'UTC'}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if payload.get('errors'):
        raise SystemExit(f"API 返回错误：{payload['errors']}")
    fixtures = payload.get('response', [])
    CACHE.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding='utf-8')
    return fixtures

def event_from_fixture(fx):
    fixture = fx.get('fixture', {})
    league = fx.get('league', {})
    teams = fx.get('teams', {})
    goals = fx.get('goals', {}) or {}
    score = fx.get('score', {}) or {}
    status = fixture.get('status', {}) or {}
    home = teams.get('home', {}) or {}
    away = teams.get('away', {}) or {}
    home_name, away_name = zh_team(home.get('name')), zh_team(away.get('name'))
    elapsed_status = status.get('short') or 'NS'
    status_cn = STATUS_ZH.get(elapsed_status, status.get('long') or elapsed_status)
    start = dt_utc(fixture.get('date'))
    if not start:
        return None
    end = start.replace(hour=start.hour+2) if start.hour <= 21 else start
    # safer duration handling
    from datetime import timedelta
    end = start + timedelta(hours=2)
    gh, ga = goals.get('home'), goals.get('away')
    finished = elapsed_status in {'FT','AET','PEN'} or (gh is not None and ga is not None and elapsed_status not in {'NS','TBD','PST'})
    if finished:
        summary = f'{TITLE_PREFIX}：{home_name} {gh}-{ga} {away_name}'
    else:
        summary = f'{TITLE_PREFIX}：{home_name} vs {away_name}'
    venue = fixture.get('venue', {}) or {}
    venue_txt = zh_venue(venue.get('name'))
    city = venue.get('city') or ''
    location = '，'.join([x for x in [venue_txt, city] if x])
    lines = [
        f'赛事：2026年美加墨世界杯',
        f'阶段：{league.get("round") or "待定"}',
        f'状态：{status_cn}',
        f'对阵：{home_name} vs {away_name}',
    ]
    if finished:
        lines.append(f'比分：{home_name} {gh}-{ga} {away_name}')
        pen_home = score.get('penalty', {}).get('home') if isinstance(score.get('penalty'), dict) else None
        pen_away = score.get('penalty', {}).get('away') if isinstance(score.get('penalty'), dict) else None
        if pen_home is not None and pen_away is not None:
            lines.append(f'点球：{pen_home}-{pen_away}')
    lines.append('说明：本日历源每日自动更新；实际显示时间取决于你的日历客户端刷新频率。')
    uid = stable_uid(fx)
    now = datetime.now(timezone.utc)
    return [
        'BEGIN:VEVENT',
        f'UID:{esc(uid)}',
        f'DTSTAMP:{fmt_dt(now)}',
        f'DTSTART:{fmt_dt(start)}',
        f'DTEND:{fmt_dt(end)}',
        f'SUMMARY:{esc(summary)}',
        f'LOCATION:{esc(location)}',
        f'DESCRIPTION:{esc("\\n".join(lines))}',
        'END:VEVENT'
    ]

def build():
    fixtures = fetch_fixtures()
    events = []
    for fx in fixtures:
        ev = event_from_fixture(fx)
        if ev:
            events.extend(ev)
    cal = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//WorldCup CN Calendar//ChatGPT MVP//ZH',
        'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', f'X-WR-CALNAME:{TITLE_PREFIX}2026中文赛程赛果',
        f'X-WR-TIMEZONE:{TIMEZONE}', 'REFRESH-INTERVAL;VALUE=DURATION:PT6H', 'X-PUBLISHED-TTL:PT6H'
    ] + events + ['END:VCALENDAR']
    OUT.write_text('\r\n'.join(fold(x) for x in cal) + '\r\n', encoding='utf-8')
    print(f'生成完成：{OUT}，事件数：{len(events)//9}')

if __name__ == '__main__':
    build()
