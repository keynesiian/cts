"""
여러 구 · 여러 달 실거래가를 수집하고 좌표를 붙여 out/ 에 저장한다.

사용:
    python collect.py
    SECRETS_PATH=/path/to/secrets.env python collect.py

수집 대상은 아래 TARGETS / MONTHS 만 바꾸면 된다.
환경변수 TARGETS / MONTHS(공백·쉼표 구분)로 덮어쓸 수 있다(월간 자동 갱신용).

누적 저장: 좌표까지 붙인 결과를 data/trades.json(추적 대상)에 쌓는다.
이번에 수집한 (구, 월)은 새 값으로 교체하고, 수집하지 않은 월은 그대로 둔다.
지도(out/trades.json)에는 누적 전체가 들어간다.
구 코드는 lawd_codes.py 참고 (없는 코드는 거기 추가).
"""
import os
import json
import statistics

import pipeline as pl
from lawd_codes import region_name


def _envlist(name, default):
    """환경변수(공백/쉼표 구분)가 있으면 리스트로, 없으면 기본값."""
    raw = os.environ.get(name)
    return raw.replace(",", " ").split() if raw else default


# ===== 수집 설정 =====
TARGETS = _envlist("TARGETS", ["11680", "11650", "11710"])  # 강남 · 서초 · 송파
MONTHS = _envlist("MONTHS", [f"{y}{m:02d}" for y, m in
                             [(2025, 11), (2025, 12)] + [(2026, i) for i in range(1, 11)]])  # YYYYMM, 2025-11~2026-10
OUT_DIR = "out"
STORE_PATH = os.environ.get("STORE_PATH", "data/trades.json")  # 월 누적 저장소
PY = 3.3058  # 1평 = 3.3058㎡


def merge_store(new, collected):
    """기존 누적분에서 이번에 새로 받은 (구, 월)만 빼고 새 거래를 합친다."""
    old = []
    if os.path.exists(STORE_PATH):
        old = json.load(open(STORE_PATH, encoding="utf-8"))
    keep = [t for t in old if (t["gu"], t["ym"]) not in collected]
    merged = keep + new
    merged.sort(key=lambda t: (t["ym"], t["gu"], t.get("date", "")))
    return merged


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_trades = []
    collected = set()  # 건수가 있는 (구, 월)만 교체 대상. 0건은 수집 실패로 보고 기존값을 지키지 않는다
    for lawd in TARGETS:
        gu = (region_name(lawd) or lawd).split()[-1]
        for ym in MONTHS:
            t = pl.fetch_trades(lawd, ym)
            for x in t:
                x["gu"] = gu
                x["ym"] = f"{ym[:4]}-{ym[4:]}"
            all_trades += t
            if t:
                collected.add((gu, f"{ym[:4]}-{ym[4:]}"))
            print(f"{gu} {ym}: {len(t)}건", flush=True)

    print(f"총 {len(all_trades)}건 · 지오코딩 시작...", flush=True)
    pl.enrich(all_trades)

    clean = []
    for t in all_trades:
        if t.get("lat") is None:
            continue
        pyeong = t["area_m2"] / PY
        t["pyeong"] = round(pyeong, 1)
        t["ppy"] = round(t["amount_manwon"] / pyeong) if pyeong else 0
        t["dong"] = t["address"].split()[2] if len(t["address"].split()) > 2 else ""
        clean.append(t)

    ok = len(clean)
    print(f"좌표 성공 {ok}/{len(all_trades)} "
          f"({ok / max(len(all_trades),1) * 100:.1f}%) · 고유주소 {len(pl._geo_cache)}개",
          flush=True)

    if clean:
        ppys = [t["ppy"] for t in clean]
        print(f"평당가(만원) 최소 {min(ppys):,} / 중앙 {round(statistics.median(ppys)):,} "
              f"/ 최대 {max(ppys):,}", flush=True)

    merged = merge_store(clean, collected)
    os.makedirs(os.path.dirname(STORE_PATH) or ".", exist_ok=True)
    json.dump(merged, open(STORE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"누적 저장 → {STORE_PATH} (이번 {len(clean)}건, 누적 {len(merged)}건)", flush=True)

    json.dump(merged, open(f"{OUT_DIR}/trades.json", "w"), ensure_ascii=False)
    pl.export(merged, f"{OUT_DIR}/trades.csv", f"{OUT_DIR}/trades.geojson")
    print(f"저장 완료 → {OUT_DIR}/trades.json, trades.csv, trades.geojson")


if __name__ == "__main__":
    main()
