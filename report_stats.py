"""
data/trades.json(월 누적 실거래)으로 월간 리포트용 구별 통계를 계산해 out/report/stats.json 에 저장한다.
숫자는 모두 여기서 계산하고, 해설(에이전트)은 이 파일에 적힌 값만 인용한다.

사용:
    python report_stats.py                   # 기본: 신고 기한이 지난 최근 달(데이터 마지막 달의 전달)
    python report_stats.py --month 2026-09   # 특정 달

실거래 신고 기한은 계약 후 30일이라, 수집 시점의 마지막 달은 건수가 덜 잡힌다(provisional).
"""
import argparse
import json
import os
import statistics
from collections import Counter, defaultdict

IN_PATH = "data/trades.json"
OUT_PATH = "out/report/stats.json"

# 전용면적 구간: 60㎡ 이하 / 60㎡ 초과~85㎡ 이하 / 85㎡ 초과
BANDS = [("소형", "60㎡ 이하", 0, 60), ("중소형", "60~85㎡", 60, 85), ("중대형", "85㎡ 초과", 85, float("inf"))]
TOP_N = 5
RECORD_N = 10


# ---------- 표기 ----------
def won(manwon):
    """만원 → '39억 1,000만원' 표기."""
    eok, man = divmod(int(round(manwon)), 10000)
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{man:,}만원"


def pct(cur, prev):
    return None if not prev or cur is None else round((cur - prev) / prev * 100, 1)


def fpct(p):
    return "비교 불가" if p is None else f"{p:+.1f}%"


def median_int(vals):
    return round(statistics.median(vals)) if vals else None


def won_or_none(v):
    return won(v) if v is not None else "거래 없음"


def prev_ym(ym):
    y, m = int(ym[:4]), int(ym[5:])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


# ---------- 집계 ----------
def apt_key(t):
    """같은 단지·같은 전용면적(정수 ㎡)을 한 묶음으로 본다(신고가 비교용)."""
    return (t["gu"], t["umd"], t["jibun"], t["apt"], round(t["area_m2"]))


def month_block(ts, ym):
    ppys = [t["ppy"] for t in ts]
    amts = [t["amount_manwon"] for t in ts]
    mp, ma = median_int(ppys), median_int(amts)
    return {
        "ym": ym,
        "count": len(ts), "count_fmt": f"{len(ts):,}건",
        "median_ppy": mp, "median_ppy_fmt": won_or_none(mp),
        "median_amount": ma, "median_amount_fmt": won_or_none(ma),
    }


def band_of(area):
    return next(name for name, _, _, hi in BANDS if area <= hi)


def record_highs(ts_all, ym):
    """ym 거래 중, 데이터 기간 안에서 같은 단지·면적의 이전 최고가를 넘긴 거래."""
    best = {}  # key -> (amount, date) : ym 이전 최고가
    for t in sorted((t for t in ts_all if t["ym"] < ym), key=lambda t: t["date"]):
        k = apt_key(t)
        if k not in best or t["amount_manwon"] > best[k][0]:
            best[k] = (t["amount_manwon"], t["date"])
    comparable, items = 0, []
    for t in ts_all:
        if t["ym"] != ym or apt_key(t) not in best:
            continue
        comparable += 1
        pmax, pdate = best[apt_key(t)]
        if t["amount_manwon"] > pmax:
            d = pct(t["amount_manwon"], pmax)
            items.append({
                "apt": t["apt"], "dong": t["dong"], "area_m2": round(t["area_m2"], 2),
                "floor": t["floor"], "date": t["date"],
                "amount": t["amount_manwon"], "amount_fmt": won(t["amount_manwon"]),
                "prev_max": pmax, "prev_max_fmt": won(pmax), "prev_date": pdate,
                "diff_pct": d, "diff_pct_fmt": fpct(d),
            })
    items.sort(key=lambda x: -x["amount"])
    return {
        "count": len(items), "count_fmt": f"{len(items):,}건",
        "comparable": comparable, "comparable_fmt": f"{comparable:,}건",
        "share_pct": round(len(items) / comparable * 100, 1) if comparable else None,
        "share_pct_fmt": f"{len(items) / comparable * 100:.1f}%" if comparable else "비교 불가",
        "items": items[:RECORD_N],
    }


def area_stats(ts_all, ym, pm, yms, provisional, with_lists=True):
    cur = [t for t in ts_all if t["ym"] == ym]
    prv = [t for t in ts_all if t["ym"] == pm]
    mb, pb = month_block(cur, ym), month_block(prv, pm)
    out = {
        "month": mb,
        "prev": pb,
        "change": {
            "count_pct": pct(mb["count"], pb["count"]),
            "count_pct_fmt": fpct(pct(mb["count"], pb["count"])),
            "median_ppy_pct": pct(mb["median_ppy"], pb["median_ppy"]),
            "median_ppy_pct_fmt": fpct(pct(mb["median_ppy"], pb["median_ppy"])),
        },
        "series": [
            dict(month_block([t for t in ts_all if t["ym"] == y], y), provisional=y in provisional)
            for y in yms
        ],
        "bands": [],
        "record_highs": record_highs(ts_all, ym),
    }
    for name, label, _, _ in BANDS:
        c = [t["ppy"] for t in cur if band_of(t["area_m2"]) == name]
        p = [t["ppy"] for t in prv if band_of(t["area_m2"]) == name]
        mc, mpv = median_int(c), median_int(p)
        out["bands"].append({
            "band": name, "label": label,
            "count": len(c), "count_fmt": f"{len(c):,}건",
            "prev_count": len(p), "prev_count_fmt": f"{len(p):,}건",
            "median_ppy": mc, "median_ppy_fmt": won_or_none(mc),
            "prev_median_ppy": mpv, "prev_median_ppy_fmt": won_or_none(mpv),
            "ppy_pct": pct(mc, mpv), "ppy_pct_fmt": fpct(pct(mc, mpv)),
        })
    if not with_lists:
        return out

    by_dong = defaultdict(list)
    for t in cur:
        by_dong[t["dong"]].append(t["ppy"])
    out["top_dongs"] = [
        {"dong": d, "count": len(v), "count_fmt": f"{len(v):,}건",
         "median_ppy": median_int(v), "median_ppy_fmt": won(median_int(v))}
        for d, v in sorted(by_dong.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:TOP_N]
    ]
    apt_cnt = Counter((t["apt"], t["dong"]) for t in cur)
    out["top_apts"] = [
        {"apt": a, "dong": d, "count": n, "count_fmt": f"{n:,}건"}
        for (a, d), n in sorted(apt_cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]
    ]
    out["top_trades"] = [
        {"apt": t["apt"], "dong": t["dong"], "area_m2": round(t["area_m2"], 2), "pyeong": t["pyeong"],
         "floor": t["floor"], "date": t["date"],
         "amount": t["amount_manwon"], "amount_fmt": won(t["amount_manwon"]),
         "ppy": t["ppy"], "ppy_fmt": won(t["ppy"])}
        for t in sorted(cur, key=lambda t: (-t["amount_manwon"], t["date"]))[:TOP_N]
    ]
    return out


def compute(month=None, trades=None):
    ts = trades if trades is not None else json.load(open(IN_PATH, encoding="utf-8"))
    yms = sorted({t["ym"] for t in ts})
    if not yms:
        raise SystemExit(f"{IN_PATH} 에 거래가 없다")
    latest = yms[-1]
    provisional = [latest]          # 수집 시점의 마지막 달은 신고가 덜 들어와 있다
    ym = month or (yms[-2] if len(yms) > 1 else latest)
    if ym not in yms:
        raise SystemExit(f"{ym} 거래가 데이터에 없다 (데이터 기간 {yms[0]}~{latest})")
    pm = prev_ym(ym)
    gus = sorted({t["gu"] for t in ts})

    stats = {
        "meta": {
            "source": "국토교통부 아파트 매매 실거래가 (" + IN_PATH + ")",
            "data_range": [yms[0], latest],
            "report_month": ym,
            "prev_month": pm,
            "prev_available": pm in yms,
            "provisional_months": provisional,
            "report_month_provisional": ym in provisional,
            "gus": gus,
            "bands": [{"band": b[0], "label": b[1]} for b in BANDS],
            "notes": [
                "실거래 신고 기한은 계약 후 30일이라 데이터 마지막 달은 건수가 덜 잡힌 잠정치다.",
                f"신고가는 데이터 기간({yms[0]}~) 안에서 같은 단지, 같은 전용면적(㎡ 정수)의 직전 최고가를 넘긴 거래다.",
                "평당가와 거래금액은 중위값이다. 해제(취소) 신고된 거래가 섞여 있을 수 있다.",
            ],
        },
        "overall": area_stats(ts, ym, pm, yms, provisional, with_lists=False),
        "gus": {g: area_stats([t for t in ts if t["gu"] == g], ym, pm, yms, provisional) for g in gus},
    }
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="YYYY-MM (기본: 데이터 마지막 달의 전달)")
    a = ap.parse_args()
    stats = compute(a.month)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    json.dump(stats, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    m = stats["meta"]
    o = stats["overall"]
    print(f"저장 완료 → {OUT_PATH} ({m['report_month']} 기준, 비교 {m['prev_month']}, "
          f"{len(m['gus'])}개 구, 거래 {o['month']['count_fmt']}, 신고가 {o['record_highs']['count_fmt']})")
    if m["report_month_provisional"]:
        print(f"주의: {m['report_month']} 는 신고 기한이 안 지난 잠정치다")


if __name__ == "__main__":
    main()
