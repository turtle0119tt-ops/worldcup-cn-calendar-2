import os
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "worldcup2026_cn.ics"

UPSTREAM_ICS_URL = os.getenv("UPSTREAM_ICS_URL", "").strip()
TITLE_PREFIX = "世界杯"


TEAM_MAP = {
    "Mexico": "墨西哥",
    "South Africa": "南非",
    "Canada": "加拿大",
    "United States": "美国",
    "USA": "美国",
    "Argentina": "阿根廷",
    "Brazil": "巴西",
    "England": "英格兰",
    "France": "法国",
    "Germany": "德国",
    "Spain": "西班牙",
    "Portugal": "葡萄牙",
    "Netherlands": "荷兰",
    "Belgium": "比利时",
    "Italy": "意大利",
    "Croatia": "克罗地亚",
    "Uruguay": "乌拉圭",
    "Colombia": "哥伦比亚",
    "Ecuador": "厄瓜多尔",
    "Japan": "日本",
    "South Korea": "韩国",
    "Korea Republic": "韩国",
    "Australia": "澳大利亚",
    "Iran": "伊朗",
    "Saudi Arabia": "沙特阿拉伯",
    "Qatar": "卡塔尔",
    "Morocco": "摩洛哥",
    "Tunisia": "突尼斯",
    "Egypt": "埃及",
    "Ghana": "加纳",
    "Senegal": "塞内加尔",
    "Algeria": "阿尔及利亚",
    "Switzerland": "瑞士",
    "Austria": "奥地利",
    "Scotland": "苏格兰",
    "Norway": "挪威",
    "Sweden": "瑞典",
    "Türkiye": "土耳其",
    "Turkey": "土耳其",
    "New Zealand": "新西兰",
    "Uzbekistan": "乌兹别克斯坦",
    "Jordan": "约旦",
    "Iraq": "伊拉克",
    "Ivory Coast": "科特迪瓦",
    "Côte d'Ivoire": "科特迪瓦",
    "Panama": "巴拿马",
    "Paraguay": "巴拉圭",
    "Haiti": "海地",
    "Curaçao": "库拉索",
    "Cape Verde": "佛得角",
    "Czech Republic": "捷克",
    "DR Congo": "刚果（金）",
    "Bosnia & Herzegovina": "波黑",
    "TBD": "待定球队",
    "TBC": "待定球队",
    "To be decided": "待定球队",
}


VENUE_MAP = {
    "Estadio Azteca": "阿兹特克体育场",
    "BMO Field": "BMO球场",
    "BMO Stadium": "BMO球场",
    "MetLife Stadium": "大都会人寿体育场",
    "SoFi Stadium": "SoFi体育场",
    "AT&T Stadium": "AT&T体育场",
    "Mercedes-Benz Stadium": "梅赛德斯-奔驰体育场",
    "Hard Rock Stadium": "硬石体育场",
    "Gillette Stadium": "吉列体育场",
    "Lincoln Financial Field": "林肯金融球场",
    "NRG Stadium": "NRG体育场",
    "Levi's Stadium": "李维斯体育场",
    "Lumen Field": "流明球场",
    "BC Place": "BC Place体育场",
    "Estadio Akron": "阿克伦体育场",
    "Estadio BBVA": "BBVA体育场",
    "Arrowhead Stadium": "箭头体育场",
}


def unfold_ics(text):
    """
    处理 ICS 折行：以空格或 Tab 开头的行属于上一行。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result = []

    for line in lines:
        if line.startswith(" ") or line.startswith("\t"):
            if result:
                result[-1] += line[1:]
        else:
            result.append(line)

    return result


def parse_ics_events(text):
    lines = unfold_ics(text)
    events = []
    current = None

    for line in lines:
        if line == "BEGIN:VEVENT":
            current = []
        elif line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
        elif current is not None:
            current.append(line)

    return events


def split_prop(line):
    """
    把 SUMMARY;LANGUAGE=en:xxx 这类属性拆成 key, value。
    """
    if ":" not in line:
        return line, ""

    left, value = line.split(":", 1)
    key = left.split(";", 1)[0].upper()
    return key, value


def get_prop(event, key):
    key = key.upper()

    for line in event:
        k, v = split_prop(line)
        if k == key:
            return v

    return ""


def ics_unescape(value):
    return (
        str(value or "")
        .replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def ics_escape(value):
    text = str(value or "")
    text = text.replace("\\", "\\\\")
    text = text.replace("\n", "\\n")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    return text


def fold(line):
    """
    ICS 建议单行不要太长。这里做简单折行，提升兼容性。
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


def zh_text(text):
    result = str(text or "")

    # 先替换长名称，避免 South Africa 被 South 之类误伤。
    for en in sorted(TEAM_MAP.keys(), key=len, reverse=True):
        result = re.sub(rf"\b{re.escape(en)}\b", TEAM_MAP[en], result)

    for en in sorted(VENUE_MAP.keys(), key=len, reverse=True):
        result = result.replace(en, VENUE_MAP[en])

    replacements = {
        "FIFA World Cup 2026": "2026年美加墨世界杯",
        "World Cup 2026": "2026年世界杯",
        "World Cup": "世界杯",
        "Group Stage": "小组赛",
        "Group stage": "小组赛",
        "Round of 32": "32强赛",
        "Round of 16": "16强赛",
        "Quarter-finals": "1/4决赛",
        "Quarterfinals": "1/4决赛",
        "Semi-finals": "半决赛",
        "Semifinals": "半决赛",
        "Third-place match": "三四名决赛",
        "Final": "决赛",
        "Match": "比赛",
    }

    for old, new in replacements.items():
        result = result.replace(old, new)

    return result.strip()


def normalize_summary(summary):
    """
    把上游标题改成统一中文标题。
    尽量保留比分，例如 Mexico 2-1 South Africa。
    """
    s = ics_unescape(summary)

    s = re.sub(r"FIFA\s+World\s+Cup\s+2026\s*[:\-–]?\s*", "", s, flags=re.I)
    s = re.sub(r"World\s+Cup\s+2026\s*[:\-–]?\s*", "", s, flags=re.I)
    s = re.sub(r"World\s+Cup\s*[:\-–]?\s*", "", s, flags=re.I)
    s = re.sub(r"Match\s+\d+\s*[:\-–]?\s*", "", s, flags=re.I)

    s = zh_text(s).strip()

    if not s:
        s = "待定比赛"

    if not s.startswith(TITLE_PREFIX):
        s = f"{TITLE_PREFIX}：{s}"

    return s


def stable_uid(event):
    uid = get_prop(event, "UID")

    if uid:
        return "cn-" + uid

    raw = "\n".join(event)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return f"worldcup2026-{digest}@worldcup-cn-calendar"


def convert_event(event):
    dtstart = get_prop(event, "DTSTART")
    dtend = get_prop(event, "DTEND")
    summary = get_prop(event, "SUMMARY")
    location = get_prop(event, "LOCATION")
    description = get_prop(event, "DESCRIPTION")

    uid = stable_uid(event)

    summary_cn = normalize_summary(summary)
    location_cn = zh_text(ics_unescape(location))

    desc_raw = ics_unescape(description)
    desc_cn = zh_text(desc_raw)

    # 不直接照搬上游描述，避免广告、英文长说明、来源杂讯。
    clean_description = "\n".join(
        [
            "赛事：2026年美加墨世界杯",
            f"赛程：{summary_cn.replace(TITLE_PREFIX + '：', '')}",
            f"球场：{location_cn}" if location_cn else "球场：待定",
            "说明：本日历由公开赛程源自动同步并中文化；每天北京时间9点更新源文件，实际显示时间取决于你的日历客户端刷新频率。",
        ]
    )

    # 如果上游描述里有比分/状态等信息，也简单追加一行，方便后续赛果保留。
    if desc_cn:
        clean_description += f"\n上游信息：{desc_cn}"

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{ics_escape(uid)}",
        f"DTSTAMP:{now}",
    ]

    if dtstart:
        lines.append(f"DTSTART:{dtstart}")

    if dtend:
        lines.append(f"DTEND:{dtend}")

    lines.extend(
        [
            f"SUMMARY:{ics_escape(summary_cn)}",
            f"LOCATION:{ics_escape(location_cn)}",
            f"DESCRIPTION:{ics_escape(clean_description)}",
            "END:VEVENT",
        ]
    )

    return lines


def build():
    if not UPSTREAM_ICS_URL:
        raise RuntimeError("没有配置 UPSTREAM_ICS_URL。请在 GitHub Secrets 里添加上游 ICS 链接。")

    print(f"开始抓取上游 ICS：{UPSTREAM_ICS_URL}")

    response = requests.get(
        UPSTREAM_ICS_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 WorldCupCNCalendar/1.0"
        },
    )
    response.raise_for_status()

    text = response.text

    if "BEGIN:VCALENDAR" not in text:
        raise RuntimeError("上游链接返回的不是 ICS 日历内容，请检查 UPSTREAM_ICS_URL。")

    events = parse_ics_events(text)
    print(f"上游事件数：{len(events)}")

    output = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//WorldCup CN Calendar//Public ICS Translator//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:2026世界杯中文赛程赛果",
        "X-WR-TIMEZONE:Asia/Shanghai",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]

    for event in events:
        output.extend(convert_event(event))

    output.append("END:VCALENDAR")

    OUT.write_text(
        "\r\n".join(fold(line) for line in output) + "\r\n",
        encoding="utf-8",
    )

    print(f"生成完成：{OUT}")
    print(f"输出事件数：{len(events)}")


if __name__ == "__main__":
    build()
