"""
핵심 파이프라인: 국토교통부 아파트 매매 실거래가 조회 + 카카오 지오코딩.

구성
  load_env / env   : secrets.env 로드
  fetch_trades     : 실거래가 조회 (WAF 재시도 + 페이지네이션)
  geocode          : 카카오 주소→좌표 (캐시 적용)
  address_for      : 거래 1건의 지오코딩용 주소 조립 (구 접두사는 sggCd 기준)
  enrich           : 거래 목록에 좌표 부여
  export           : CSV / GeoJSON 내보내기
"""
import os
import csv
import json
import time
import requests
import xml.etree.ElementTree as ET

from lawd_codes import region_name

# data.go.kr WAF가 User-Agent 없는 요청을 차단하므로 항상 지정한다.
UA = "Mozilla/5.0"


# ---------- 설정 ----------
def load_env(path=None):
    path = path or os.environ.get("SECRETS_PATH", "secrets.env")
    out = {}
    if os.path.exists(path):                      # 로컬: secrets.env 있으면 기존대로 읽음
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    # 클라우드/웹 세션: 파일이 없거나 일부 키만 있을 때 환경변수(secret)로 보강·덮어쓰기
    for k in ("APT_TRADE_ENDPOINT", "APT_TRADE_API_KEY", "KAKAO_REST_API_KEY"):
        if os.environ.get(k):
            out[k] = os.environ[k]
    return out


_ENV = None
def env():
    global _ENV
    if _ENV is None:
        _ENV = load_env()
    return _ENV


# ---------- 1) 실거래가 조회 ----------
def fetch_trades(lawd_cd, deal_ymd, num_rows=1000, tries=5):
    """LAWD_CD(시군구 5자리), DEAL_YMD(YYYYMM)의 전체 거래를 리스트로 반환."""
    e = env()
    items, page = [], 1
    while True:
        r = None
        for attempt in range(tries):
            try:
                r = requests.get(
                    f"{e['APT_TRADE_ENDPOINT']}/getRTMSDataSvcAptTrade",
                    params={
                        "serviceKey": e["APT_TRADE_API_KEY"],
                        "LAWD_CD": lawd_cd,
                        "DEAL_YMD": deal_ymd,
                        "numOfRows": num_rows,
                        "pageNo": page,
                    },
                    headers={"User-Agent": UA},
                    timeout=20,
                )
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == tries - 1:
                    raise
                time.sleep(3 * (attempt + 1))  # WAF/일시 오류 백오프

        root = ET.fromstring(r.content)
        code = root.findtext(".//resultCode")
        if code and code != "000":
            raise RuntimeError(f"API 오류: {root.findtext('.//resultMsg')}")

        page_items = root.findall(".//item")
        if not page_items:
            break
        for it in page_items:
            g = lambda t: (it.findtext(t) or "").strip()
            items.append({
                "apt": g("aptNm"),
                "sgg": g("estateAgentSggNm"),  # 중개업소 소재지(매물 위치 아님)
                "sgg_cd": g("sggCd"),          # 매물의 실제 시군구 코드
                "umd": g("umdNm"),
                "jibun": g("jibun"),
                "amount_manwon": int(g("dealAmount").replace(",", "") or 0),
                "area_m2": float(g("excluUseAr") or 0),
                "floor": g("floor"),
                "build_year": g("buildYear"),
                "date": f"{g('dealYear')}-{int(g('dealMonth')):02d}-{int(g('dealDay')):02d}",
            })
        total = int(root.findtext(".//totalCount") or 0)
        if page * num_rows >= total:
            break
        page += 1
        time.sleep(0.3)
    return items


# ---------- 2) 카카오 지오코딩 (캐시) ----------
_geo_cache = {}

def geocode(address):
    if address in _geo_cache:
        return _geo_cache[address]
    e = env()
    r = requests.get(
        "https://dapi.kakao.com/v2/local/search/address.json",
        params={"query": address},
        headers={"Authorization": f"KakaoAK {e['KAKAO_REST_API_KEY']}"},
        timeout=10,
    )
    r.raise_for_status()
    docs = r.json().get("documents", [])
    res = (float(docs[0]["y"]), float(docs[0]["x"])) if docs else (None, None)
    _geo_cache[address] = res
    return res


# ---------- 3) 주소 조립 + 결합 ----------
def _clean_sgg(sgg):
    # "서울 강남구, 서울 송파구" 같은 복합값은 앞부분만 사용
    return sgg.split(",")[0].strip()

def address_for(t):
    """구 접두사는 sggCd(매물 실제 구) 기준. 매핑에 없으면 중개업소 소재지로 폴백."""
    prefix = region_name(t.get("sgg_cd")) or _clean_sgg(t.get("sgg", ""))
    return f"{prefix} {t['umd']} {t['jibun']}".strip()

def enrich(trades, pause=0.02):
    for t in trades:
        t["address"] = address_for(t)
        t["lat"], t["lng"] = geocode(t["address"])
        time.sleep(pause)
    return trades


# ---------- 4) 내보내기 ----------
EXPORT_COLS = ["apt", "address", "gu", "ym", "amount_manwon", "area_m2",
               "pyeong", "ppy", "floor", "build_year", "date", "lat", "lng"]

def export(trades, csv_path, geojson_path):
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(trades)
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [t["lng"], t["lat"]]},
        "properties": {k: t.get(k) for k in EXPORT_COLS if k not in ("lat", "lng")},
    } for t in trades if t.get("lat") is not None]
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, ensure_ascii=False, indent=2)
