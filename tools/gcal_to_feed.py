#!/usr/bin/env python3
"""Turn Google Calendar list_events dumps into luke-calendar-feed.json.

Usage: python3 tools/gcal_to_feed.py OUT.json PAGE1.json [PAGE2.json ...]

Each PAGE file is a raw Google Calendar list_events result (JSON with an
"events" array, or a tool-result wrapper [{"text": "<json>"}]).
The feed is public (GitHub Pages), so private / sensitive events are dropped.
"""
import json, re, sys
from datetime import datetime, timedelta, timezone

PRIVATE = re.compile(r"therap|doctor|dentist|dermat|psychiat|counsel|medic|pharmac|prescri|\bdate w/|\bdate with\b", re.I)

# Luke asked for these to show on all calendars, under a short title (no notes/location).
MASK = re.compile(r"\brice\b|\btherapy\b", re.I)

CATS = [
    (r"class|marketing|branding|operations|cross-cultural|consumer|analysis|exam|quiz|final|hutter|zile|fordham|lecture|study", "School"),
    (r"ai business|2x|client|meeting|call|interview|profound|work|pitch", "Work"),
    (r"gym|krav|workout|shower|run\b|lift|yoga|sleep", "Health"),
    (r"flight|travel|train|cape|trip|airport|nantucket|spain", "Travel"),
    (r"holiday|thanksgiving|christmas|new year", "Holiday"),
]


def load(path):
    d = json.load(open(path))
    if isinstance(d, list) and d and isinstance(d[0], dict) and "text" in d[0]:
        d = json.loads(d[0]["text"])
    return d.get("events", []) if isinstance(d, dict) else []


def category(title):
    for pat, cat in CATS:
        if re.search(pat, title, re.I):
            return cat
    return "Personal"


def write_ics(feed, path):
    """Same events as an .ics file Apple/Google Calendar can subscribe to."""
    def esc(t):
        return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Christopher//Luke Calendar//EN", "CALSCALE:GREGORIAN",
         "X-WR-CALNAME:Luke (Christopher sync)", "X-WR-TIMEZONE:America/New_York",
         "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H"]
    for i, e in enumerate(feed):
        d = e["date"].replace("-", "")
        L += ["BEGIN:VEVENT", f"UID:{e.get('gid') or i}-{d}@luke-calendar", f"DTSTAMP:{now}", f"SUMMARY:{esc(e['title'])}"]
        if e["time"]:
            end = e["endTime"] or e["time"]
            L += [f"DTSTART;TZID=America/New_York:{d}T{e['time'].replace(':', '')}00",
                  f"DTEND;TZID=America/New_York:{d}T{end.replace(':', '')}00"]
        else:
            nd = (datetime.fromisoformat(e["date"]) + timedelta(days=1)).strftime("%Y%m%d")
            L += [f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{nd}", "TRANSP:TRANSPARENT"]
        if e.get("location"):
            L.append(f"LOCATION:{esc(e['location'])}")
        L.append("END:VEVENT")
    L.append("END:VCALENDAR")
    open(path, "w").write("\r\n".join(L) + "\r\n")


def main():
    out, pages = sys.argv[1], sys.argv[2:]
    seen, feed = set(), []
    for p in pages:
        for e in load(p):
            if e.get("status") == "cancelled":
                continue
            title = (e.get("summary") or "").strip()
            blob = " ".join([title, e.get("description") or "", e.get("location") or ""])
            if MASK.search(title):
                title = "Tim Rice (Zoom)" if re.search(r"zoom", blob, re.I) else "Tim Rice"
                e = dict(e, location="")
            elif e.get("visibility") == "private" or not title or PRIVATE.search(blob):
                continue
            s, en = e.get("start", {}), e.get("end", {})
            if "dateTime" in s:
                sd = datetime.fromisoformat(s["dateTime"])
                ed = datetime.fromisoformat(en.get("dateTime", s["dateTime"]))
                items = [(sd.strftime("%Y-%m-%d"), sd.strftime("%H:%M"), ed.strftime("%H:%M"))]
            elif "date" in s:
                d0 = datetime.fromisoformat(s["date"]).date()
                d1 = datetime.fromisoformat(en.get("date", s["date"])).date()
                items, d = [], d0
                while d < max(d1, d0 + timedelta(days=1)):
                    items.append((d.isoformat(), "", ""))
                    d += timedelta(days=1)
            else:
                continue
            for date, t, et in items:
                key = (e.get("id"), date)
                if key in seen:
                    continue
                seen.add(key)
                ev = {"date": date, "time": t, "endTime": et, "title": title,
                      "category": category(title), "src": "gcal", "gid": e.get("id", "")}
                if e.get("location"):
                    ev["location"] = e["location"]
                feed.append(ev)
    feed.sort(key=lambda x: (x["date"], x["time"] or "99", x["title"]))
    dates = [x["date"] for x in feed]
    json.dump({
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Google Calendar (lsullivan59@fordham.edu) via Christopher",
        "from": min(dates) if dates else None, "to": max(dates) if dates else None,
        "events": feed,
    }, open(out, "w"), indent=0, ensure_ascii=False)
    write_ics(feed, out.rsplit(".", 1)[0].replace("-feed", "") + ".ics")
    print(json.dumps({"events": len(feed), "from": min(dates) if dates else None, "to": max(dates) if dates else None}))


if __name__ == "__main__":
    main()
