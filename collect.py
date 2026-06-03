"""
여러 구 · 여러 달 실거래가를 수집하고 좌표를 붙여 out/ 에 저장한다.

사용:
    python collect.py
    SECRETS_PATH=/path/to/secrets.env python collect.py

수집 대상은 아래 TARGETS / MONTHS 만 바꾸면 된다.
구 코드는 lawd_codes.py 참고 (없는 코드는 거기 추가).
"""
import os
import json
import statistics

import pipeline as pl
from lawd_codes import region_name

# ===== 수집 설정 =====
TARGETS = ["11680", "11650", "11710"]   # 강남 · 서초 · 송파
MONTHS = ["202512", "202601"]           # YYYYMM
OUT_DIR = "out"
PY = 3.3058  # 1평 = 3.3058㎡


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_trades = []
    for lawd in TARGETS:
        gu = (region_name(lawd) or lawd).split()[-1]
        for ym in MONTHS:
            t = pl.fetch_trades(lawd, ym)
            for x in t:
                x["gu"] = gu
                x["ym"] = f"{ym[:4]}-{ym[4:]}"
            all_trades += t
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

    json.dump(clean, open(f"{OUT_DIR}/trades.json", "w"), ensure_ascii=False)
    pl.export(clean, f"{OUT_DIR}/trades.csv", f"{OUT_DIR}/trades.geojson")
    print(f"저장 완료 → {OUT_DIR}/trades.json, trades.csv, trades.geojson")


if __name__ == "__main__":
    main()
