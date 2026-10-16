"""API 키 없이 화면을 확인하기 위한 예시 데이터 생성기. 실제 검색량이 아닙니다.
사용법: python3 collector/demo_data.py
"""
import datetime as dt
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "config" / "brands.json").read_text(encoding="utf-8"))
rng = random.Random(7)
end = dt.date.today() - dt.timedelta(days=1)
start = end - dt.timedelta(days=730)
profiles = {"mine": (180, 0.0018), "greenpunch": (1400, 0.0004)}  # 기본 일 검색 수, 일 성장률

groups, series = [], {}
for g in cfg["groups"]:
    base, growth = profiles.get(g["id"], (600, 0.0006))
    days, d, vals = [], start, []
    while d <= end:
        t = (d - start).days
        weekly = 1.18 if d.weekday() in (0, 1) else (0.82 if d.weekday() == 5 else 1.0)
        season = 1 + 0.22 * math.sin(2 * math.pi * (d.timetuple().tm_yday - 100) / 365)
        spike = 1.9 if rng.random() < 0.01 else 1.0
        v = base * math.exp(growth * t) * weekly * season * spike * rng.uniform(0.88, 1.12)
        days.append(d.isoformat()); vals.append(v); d += dt.timedelta(days=1)
    mx = max(vals)
    series[g["id"]] = [[day, round(v / mx * 100, 4), round(v, 1)] for day, v in zip(days, vals)]
    meta = {k: g.get(k) for k in ("id", "name", "is_mine", "color")}
    meta["keywords"] = g.get("keywords") or ["(예시)"]
    meta["monthly_searches"] = round(sum(vals[-30:]))
    groups.append(meta)

out = {
    "updated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="minutes"),
    "demo": True, "has_absolute": True, "range": [start.isoformat(), end.isoformat()],
    "groups": groups, "series": series,
}
p = ROOT / "docs" / "data" / "daily.json"
p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("예시 데이터 저장:", p.relative_to(ROOT))
