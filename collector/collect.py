"""네이버 검색량 수집기.

두 가지 네이버 API를 합쳐 '일별 추정 검색량'을 만든다.
- 검색어 트렌드(Search Trend) API: 일별 상대 지수(0~100). 실제 검색 수가 아님.
  2026년부터 네이버 개발자센터에서 네이버 클라우드 플랫폼의 NAVER API HUB로 이관됨.
- 검색광고 키워드도구 API: 최근 30일 실제 검색 수(PC+모바일).
브랜드마다 데이터랩을 따로 호출해 지수를 받고,
  배율 = 최근 30일 실제 검색 수 / 최근 30일 지수 합
으로 지수를 실제 검색 수 규모로 환산한다.

필요한 환경변수
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET          (API HUB 앱의 Client ID/Secret, 필수)
  SEARCHAD_API_KEY, SEARCHAD_SECRET, SEARCHAD_CUSTOMER_ID  (검색광고, 없으면 지수만 저장)

사용법: python3 collector/collect.py
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "brands.json"
OUT = ROOT / "docs" / "data" / "daily.json"
SNAPSHOTS = ROOT / "docs" / "data" / "searchad_snapshots.json"

# NAVER API HUB 검색어 트렌드. 기존 개발자센터 키를 쓰는 경우 DATALAB_URL=https://openapi.naver.com/v1/datalab/search
DATALAB_URL = os.environ.get("DATALAB_URL", "https://naverapihub.apigw.ntruss.com/search-trend/v1/search")
SEARCHAD_URL = "https://api.searchad.naver.com"


class ApiError(Exception):
    pass


def http_json(req):
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise ApiError(f"HTTP {e.code} {req.full_url.split('?')[0]} 응답: {body}") from None


def env(key):
    return os.environ.get(key, "").strip()


def _datalab_headers():
    cid, secret = env("NAVER_CLIENT_ID"), env("NAVER_CLIENT_SECRET")
    if "openapi.naver.com" in DATALAB_URL:  # 이관 전 개발자센터 방식
        auth = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    else:  # NAVER API HUB 방식
        auth = {"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": secret}
    return {**auth, "Content-Type": "application/json"}


def datalab_daily(keywords, name, start, end):
    """한 브랜드만 넣어 호출해서, 그 브랜드 기간 내 최댓값=100 기준 일별 지수를 받는다."""
    body = {
        "startDate": start,
        "endDate": end,
        "timeUnit": "date",
        "keywordGroups": [{"groupName": name, "keywords": keywords[:20]}],
    }
    req = urllib.request.Request(
        DATALAB_URL,
        data=json.dumps(body).encode("utf-8"),
        headers=_datalab_headers(),
        method="POST",
    )
    res = http_json(req)
    points = res["results"][0]["data"]
    # 검색이 거의 없는 날은 응답에서 빠지므로 0으로 채운다.
    by_date = {p["period"]: float(p["ratio"]) for p in points}
    out = []
    d = dt.date.fromisoformat(start)
    last = dt.date.fromisoformat(end)
    while d <= last:
        key = d.isoformat()
        out.append([key, by_date.get(key, 0.0)])
        d += dt.timedelta(days=1)
    return out


def _searchad_headers(method, uri):
    ts = str(int(time.time() * 1000))
    msg = f"{ts}.{method}.{uri}".encode("utf-8")
    sig = base64.b64encode(
        hmac.new(env("SEARCHAD_SECRET").encode("utf-8"), msg, hashlib.sha256).digest()
    ).decode()
    return {
        "X-Timestamp": ts,
        "X-API-KEY": env("SEARCHAD_API_KEY"),
        "X-Customer": env("SEARCHAD_CUSTOMER_ID"),
        "X-Signature": sig,
    }


def _count(v):
    # 검색 수가 아주 적으면 "< 10" 같은 문자열로 온다. 중간값 5로 본다.
    if isinstance(v, (int, float)):
        return int(v)
    return 5


def _norm(k):
    return k.replace(" ", "").upper()


def searchad_monthly(keywords):
    """키워드별 최근 30일 검색 수(PC, 모바일). 공백 제거 기준으로 같은 키워드는 한 번만 센다."""
    uniq = []
    for k in keywords:
        n = _norm(k)
        if n not in uniq:
            uniq.append(n)
    result = {}
    for i in range(0, len(uniq), 5):  # 한 번에 최대 5개
        chunk = uniq[i : i + 5]
        uri = "/keywordstool"
        qs = urllib.parse.urlencode({"hintKeywords": ",".join(chunk), "showDetail": "1"})
        req = urllib.request.Request(
            f"{SEARCHAD_URL}{uri}?{qs}", headers=_searchad_headers("GET", uri)
        )
        res = http_json(req)
        for row in res.get("keywordList", []):
            n = _norm(row["relKeyword"])
            if n in chunk:
                result[n] = {
                    "pc": _count(row.get("monthlyPcQcCnt")),
                    "mobile": _count(row.get("monthlyMobileQcCnt")),
                }
        time.sleep(0.3)
    return result


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    for key in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"):
        if not env(key):
            sys.exit(f"환경변수 {key} 가 없습니다. README의 'API 키 발급'을 확인하세요.")
    has_searchad = all(
        env(k) for k in ("SEARCHAD_API_KEY", "SEARCHAD_SECRET", "SEARCHAD_CUSTOMER_ID")
    )

    today = dt.date.today()
    end = (today - dt.timedelta(days=1)).isoformat()  # 오늘 데이터는 아직 불완전
    start = cfg.get("start_date", "2016-01-01")

    snapshots = json.loads(SNAPSHOTS.read_text(encoding="utf-8")) if SNAPSHOTS.exists() else {}
    groups_out, series, searchad_errors = [], {}, []

    for g in cfg["groups"]:
        meta = {k: g.get(k) for k in ("id", "name", "is_mine", "color")}
        meta["keywords"] = g.get("keywords", [])
        groups_out.append(meta)
        if not g.get("keywords"):
            print(f"[건너뜀] {g['name']}: 키워드가 비어 있음")
            continue

        print(f"[수집] {g['name']} 데이터랩 {start}~{end}")
        try:
            ratios = datalab_daily(g["keywords"], g["name"], start, end)
        except ApiError as e:
            # 한 브랜드가 실패해도 나머지는 저장한다.
            print(f"[경고] {g['name']} 검색어 트렌드 실패, 건너뜁니다: {e}")
            searchad_errors.append(str(e))
            continue

        monthly = None
        if has_searchad:
            try:
                per_kw = searchad_monthly(g["keywords"])
            except ApiError as e:
                # 검색광고 API가 실패해도 데이터랩 지수는 저장한다.
                print(f"[경고] 검색광고 API 실패, 지수만 저장합니다: {e}")
                searchad_errors.append(str(e))
            else:
                monthly = sum(v["pc"] + v["mobile"] for v in per_kw.values())
                meta["searchad"] = per_kw
                snapshots.setdefault(g["id"], {})[end] = monthly
                print(f"       최근 30일 실제 검색 수 {monthly:,}")

        last30 = sum(r for _, r in ratios[-30:])
        scale = (monthly / last30) if (monthly is not None and last30 > 0) else None
        meta["monthly_searches"] = monthly
        meta["scale"] = scale
        series[g["id"]] = [
            [d, round(r, 4), (round(r * scale, 1) if scale is not None else None)]
            for d, r in ratios
        ]

    out = {
        "updated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="minutes"),
        "demo": False,
        "has_absolute": any(s[0][2] is not None for s in series.values() if s),
        "range": [start, end],
        "groups": groups_out,
        "series": series,  # id -> [[날짜, 데이터랩 지수, 추정 검색 수], ...]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    SNAPSHOTS.write_text(json.dumps(snapshots, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[완료] {OUT.relative_to(ROOT)} 저장")
    if searchad_errors:
        # 데이터는 저장하되, 실패를 알 수 있게 작업은 실패로 끝낸다.
        sys.exit("API 오류가 있었습니다. 위 [경고]를 확인하세요.")


if __name__ == "__main__":
    main()
