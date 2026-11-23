"""
월간 실거래 리포트 HTML 생성. 숫자는 report_stats.compute() 로 data/trades.json 에서 다시 계산하고,
해설 문장은 data/report/YYYY-MM.json(월간 리포트 워크플로가 작성)에서 읽어 함께 싣는다.

사용:
    python build_report.py                    # out/report.html (기본 달은 report_stats 와 같음)
    python build_report.py --month 2026-09 --strict
    REPORT_OUT=docs/report.html python build_report.py   # 웹/클라우드: 추적 경로로 내보냄

--strict 는 해설에 통계에 없는 숫자나 금지 문장부호(가운뎃점, 줄표, 쌍점)가 있으면 실패(종료코드 3)한다.
"""
import argparse
import html
import json
import os
import re
import sys

import report_stats as rs

COMMENTARY_DIR = "data/report"
OUT_PATH = os.environ.get("REPORT_OUT", "out/report.html")
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]  # 구 순서 고정(categorical slot 1~3)

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
# 단위가 붙은 값은 통계의 *_fmt 문자열과 글자 그대로 맞아야 한다(반올림, '약' 표기 차단)
TYPED = [("금액", re.compile(r"\d+억(?:\s?[\d,]+만원|원)?|[\d,]+만원")),
         ("비율", re.compile(r"[+-]?\d+(?:\.\d+)?%")),
         ("건수", re.compile(r"[\d,]+건"))]
BANNED = {"·": "가운뎃점", "—": "줄표", "–": "줄표", ":": "쌍점"}


# ---------- 해설 점검 ----------
def _canon(tok):
    x = float(tok.replace(",", ""))
    return ("%f" % x).rstrip("0").rstrip(".")


def numbers_in(text):
    return {_canon(t) for t in NUM_RE.findall(text)}


def commentary_texts(c):
    yield "종합", c["summary"]["headline"]
    for p in c["summary"]["paragraphs"]:
        yield "종합", p
    for gu, s in c["sections"].items():
        yield gu, s["headline"]
        for p in s["paragraphs"]:
            yield gu, p


def strings_in(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from strings_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings_in(v)
    elif isinstance(obj, str):
        yield obj


def _norm(tok):
    return tok.replace(" ", "").lstrip("+-")   # 공백과 부호는 따지지 않는다


def check_commentary(c, stats):
    """통계(stats)에 없는 숫자와 금지 문장부호를 찾아 [(위치, 문제, 문장)] 로 돌려준다."""
    allowed = numbers_in(json.dumps(stats, ensure_ascii=False))
    allowed |= {str(i) for i in range(1, 13)}        # 'N월'
    fmts = list(strings_in(stats))
    typed_ok = {name: {_norm(t) for f in fmts for t in rx.findall(f)} for name, rx in TYPED}
    problems = []
    for where, text in commentary_texts(c):
        for name, rx in TYPED:
            for t in rx.findall(text):
                if _norm(t) not in typed_ok[name]:
                    problems.append((where, f"통계에 없는 {name} '{t}'", text))
        for n in sorted(numbers_in(text) - allowed):
            problems.append((where, f"통계에 없는 숫자 {n}", text))
        for ch, name in BANNED.items():
            if ch in text:
                problems.append((where, f"금지 문장부호({name}) '{ch}'", text))
    return problems


# ---------- HTML ----------
e = html.escape


def ym_label(ym):
    return f"{ym[:4]}년 {int(ym[5:])}월"


def delta_cls(p):
    return "" if p is None else ("up" if p > 0 else "down" if p < 0 else "")


def kpi_card(title, s, color=None):
    m, ch, rh = s["month"], s["change"], s["record_highs"]
    sw = f'<span class="sw" style="background:{color}"></span>' if color else ""
    return f"""
    <div class="kpi">
      <div class="kpi-t">{sw}{e(title)}</div>
      <div class="kpi-row">
        <div><div class="n">{e(m['count_fmt'])}</div><div class="l">거래량 <b class="{delta_cls(ch['count_pct'])}">{e(ch['count_pct_fmt'])}</b></div></div>
        <div><div class="n">{e(m['median_ppy_fmt'])}</div><div class="l">중위 평당가 <b class="{delta_cls(ch['median_ppy_pct'])}">{e(ch['median_ppy_pct_fmt'])}</b></div></div>
      </div>
      <div class="l">신고가 {e(rh['count_fmt'])} (비교 가능 {e(rh['comparable_fmt'])} 중 {e(rh['share_pct_fmt'])})</div>{bulk_line(s)}
    </div>"""


def bulk_line(s):
    b, x = s["bulk"], s["ex_bulk"]
    if not (b["count"] or b["prev_count"]):
        return ""
    return (f'<div class="l bulk">일괄 거래 {e(b["count_fmt"])} 제외 시 {e(x["month"]["count_fmt"])} '
            f'<b class="{delta_cls(x["change"]["count_pct"])}">{e(x["change"]["count_pct_fmt"])}</b>, '
            f'중위 평당가 {e(x["month"]["median_ppy_fmt"])} '
            f'<b class="{delta_cls(x["change"]["median_ppy_pct"])}">{e(x["change"]["median_ppy_pct_fmt"])}</b></div>')


def table(head, rows, num_cols=()):
    th = "".join(f'<th class="{"num" if i in num_cols else ""}">{e(h)}</th>' for i, h in enumerate(head))
    body = "".join(
        "<tr>" + "".join(f'<td class="{"num" if i in num_cols else ""}">{e(str(v))}</td>' for i, v in enumerate(r)) + "</tr>"
        for r in rows
    ) or f'<tr><td colspan="{len(head)}" class="empty">해당 거래 없음</td></tr>'
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def paragraphs(block):
    if not block:
        return '<p class="pending">해설이 아직 작성되지 않았다. 월간 리포트 워크플로를 돌리면 채워진다.</p>'
    return (f'<p class="headline">{e(block["headline"])}</p>'
            + "".join(f"<p>{e(p)}</p>" for p in block["paragraphs"]))


def gu_section(gu, s, block, color, pm):
    bands = table(["면적대", "거래", f"전월({int(pm[5:])}월)", "중위 평당가", "전월", "증감"],
                  [[f"{b['band']} {b['label']}", b["count_fmt"], b["prev_count_fmt"],
                    b["median_ppy_fmt"], b["prev_median_ppy_fmt"], b["ppy_pct_fmt"]] for b in s["bands"]],
                  num_cols=(1, 2, 3, 4, 5))
    dongs = table(["동", "거래", "중위 평당가"],
                  [[d["dong"], d["count_fmt"], d["median_ppy_fmt"]] for d in s["top_dongs"]], num_cols=(1, 2))
    apts = table(["단지", "동", "거래"],
                 [[t["apt"], t["dong"], t["count_fmt"]] for t in s["top_apts"]], num_cols=(2,))
    tops = table(["단지", "동", "전용", "층", "거래금액", "평당가", "계약일"],
                 [[t["apt"], t["dong"], f"{t['area_m2']}㎡", t["floor"], t["amount_fmt"], t["ppy_fmt"], t["date"]]
                  for t in s["top_trades"]], num_cols=(2, 3, 4, 5))
    rh = s["record_highs"]
    bulk = ""
    if s["bulk"]["items"]:
        bulk = ('<h3>일괄 거래 <span class="h3s">한 단지에서 같은 날 '
                f'{rs.BULK_MIN}건 이상 신고</span></h3>'
                + table(["단지", "동", "계약일", "건수", "전용", "중위 거래금액"],
                        [[i["apt"], i["dong"], i["date"], i["count_fmt"], i["area_fmt"], i["median_amount_fmt"]]
                         for i in s["bulk"]["items"]], num_cols=(3, 4, 5)))
    recs = table(["단지", "동", "전용", "거래금액", "직전 최고가", "상승률", "계약일"],
                 [[r["apt"], r["dong"], f"{r['area_m2']}㎡", r["amount_fmt"],
                   f"{r['prev_max_fmt']} ({r['prev_date']})", r["diff_pct_fmt"], r["date"]] for r in rh["items"]],
                 num_cols=(2, 3, 4, 5))
    more = f" 중 금액 상위 {len(rh['items'])}건" if rh["count"] > len(rh["items"]) else ""
    review = (block or {}).get("review") or {}
    rv = (f'<p class="review">검증 에이전트가 초안에서 고친 곳 {review.get("issues", 0)}건</p>'
          if block else "")
    return f"""
  <section class="gu" id="{e(gu)}">
    <h2><span class="sw" style="background:{color}"></span>{e(gu)}</h2>
    <div class="prose">{paragraphs(block)}{rv}</div>
    {bulk}<h3>면적대별</h3>{bands}
    <div class="grid2">
      <div><h3>거래 많은 동</h3>{dongs}</div>
      <div><h3>거래 많은 단지</h3>{apts}</div>
    </div>
    <h3>거래금액 상위</h3>{tops}
    <h3>신고가 거래 <span class="h3s">{e(rh['count_fmt'])}{e(more)}</span></h3>{recs}
  </section>"""


def render(stats, c):
    m = stats["meta"]
    ym, pm, gus = m["report_month"], m["prev_month"], m["gus"]
    color = {g: COLORS[i % len(COLORS)] for i, g in enumerate(gus)}
    o = stats["overall"]
    yms = [x["ym"] for x in o["series"]]
    series = {
        "gus": gus, "colors": [color[g] for g in gus], "yms": yms, "reportYm": ym,
        "provisional": [x["provisional"] for x in o["series"]],
        "bulk": {g: [x["bulk"] for x in stats["gus"][g]["series"]] for g in gus},
        "count": {g: [x["count"] for x in stats["gus"][g]["series"]] for g in gus},
        "countFmt": {g: [x["count_fmt"] for x in stats["gus"][g]["series"]] for g in gus},
        "ppy": {g: [x["median_ppy"] for x in stats["gus"][g]["series"]] for g in gus},
        "ppyFmt": {g: [x["median_ppy_fmt"] for x in stats["gus"][g]["series"]] for g in gus},
    }
    region = " ".join(gus) if len(gus) <= 3 else f"{len(gus)}개 구"
    kpis = kpi_card(f"{len(gus)}개 구 합계", o) + "".join(kpi_card(g, stats["gus"][g], color[g]) for g in gus)
    sections = "".join(gu_section(g, stats["gus"][g], (c or {}).get("sections", {}).get(g), color[g], pm)
                       for g in gus)
    table_rows = "".join(
        f"<tr><td>{e(ym_label(y))}{' (잠정)' if series['provisional'][i] else ''}</td>"
        + "".join(f'<td class="num">{e(series["countFmt"][g][i])}</td><td class="num">{e(series["ppyFmt"][g][i])}</td>'
                  for g in gus) + "</tr>"
        for i, y in enumerate(yms))
    table_head = "".join(f"<th class='num'>{e(g)} 거래</th><th class='num'>{e(g)} 평당가</th>" for g in gus)
    notes = "".join(f"<li>{e(n)}</li>" for n in m["notes"])
    prov = ", ".join(ym_label(y) for y in m["provisional_months"])

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>월간 실거래 리포트 {e(ym_label(ym))}</title>
<style>
  :root{{
    --ink:#16243b; --ink-soft:#52607a; --line:#e4e0d6; --grid:#ece8df;
    --paper:#f7f4ec; --card:#fff; --accent:#b8503a; --up:#b8503a; --down:#2a62b8;
  }}
  *{{box-sizing:border-box}}
  html,body{{margin:0;background:var(--paper);color:var(--ink);
    font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;-webkit-text-size-adjust:100%}}
  .wrap{{max-width:980px;margin:0 auto;padding:28px 16px 48px}}
  .kicker{{font-size:11px;letter-spacing:.22em;color:var(--accent);font-weight:700}}
  h1{{font-size:28px;font-weight:800;letter-spacing:-.02em;margin:6px 0 6px;line-height:1.25}}
  .sub{{font-size:13px;color:var(--ink-soft);margin:0}}
  .sub a{{color:var(--accent);font-weight:700;text-decoration:none}}
  h2{{font-size:21px;font-weight:800;letter-spacing:-.02em;margin:0 0 12px;display:flex;align-items:center;gap:8px}}
  h3{{font-size:13px;font-weight:700;letter-spacing:.02em;color:var(--ink-soft);margin:22px 0 8px}}
  .h3s{{font-weight:600;margin-left:4px;color:var(--ink)}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 18px}}
  section{{margin-top:26px}}
  .prose p{{font-size:15.5px;line-height:1.75;margin:0 0 10px;word-break:keep-all}}
  .prose p.headline{{font-size:18px;font-weight:800;line-height:1.5;letter-spacing:-.01em}}
  .prose p.pending{{color:var(--ink-soft);font-size:14px}}
  .review{{font-size:12px!important;color:var(--ink-soft)}}
  .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin-top:20px}}
  .kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 14px}}
  .kpi-t{{font-size:12px;font-weight:700;color:var(--ink-soft);display:flex;align-items:center;gap:6px;margin-bottom:8px}}
  .kpi-row{{display:flex;flex-wrap:wrap;gap:6px 18px;margin-bottom:8px}}
  .n{{font-size:19px;font-weight:800;letter-spacing:-.02em;line-height:1.1;white-space:nowrap}}
  .l{{font-size:11.5px;color:var(--ink-soft);margin-top:3px}}
  .l.bulk{{border-top:1px dashed var(--line);padding-top:6px;margin-top:6px}}
  .l b{{font-weight:700;color:var(--ink)}} .l b.up{{color:var(--up)}} .l b.down{{color:var(--down)}}
  .sw{{display:inline-block;width:10px;height:10px;border-radius:3px;flex:none}}
  .charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}
  .chart-t{{font-size:14px;font-weight:800;margin:0 0 2px}}
  .chart-s{{font-size:11.5px;color:var(--ink-soft);margin:0 0 6px}}
  .legend{{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--ink-soft);margin:4px 0 2px}}
  .legend span{{display:flex;align-items:center;gap:5px}}
  .legend .dash{{width:16px;height:0;border-top:2px dashed var(--ink-soft)}}
  .chart{{position:relative;height:240px}}
  .chart svg{{display:block;width:100%;height:100%;overflow:visible}}
  .tip{{position:absolute;pointer-events:none;background:var(--ink);color:#f7f4ec;border-radius:8px;
    padding:8px 10px;font-size:12px;line-height:1.55;white-space:nowrap;opacity:0;transition:opacity .12s;z-index:2}}
  .tip b{{font-weight:800}} .tip .row{{display:flex;align-items:center;gap:6px}}
  details{{margin-top:10px}} summary{{cursor:pointer;font-size:12.5px;font-weight:700;color:var(--ink-soft)}}
  .tw{{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:10px;background:var(--card)}}
  table{{border-collapse:collapse;width:100%;font-size:13px}}
  th,td{{padding:8px 10px;border-bottom:1px solid var(--grid);text-align:left;white-space:nowrap}}
  th{{font-size:11.5px;color:var(--ink-soft);font-weight:700;background:#fbfaf6}}
  tr:last-child td{{border-bottom:0}}
  td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
  td.empty{{color:var(--ink-soft);text-align:center}}
  .grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:0 14px}}
  .gu{{border-top:1px solid var(--line);padding-top:24px}}
  footer{{margin-top:36px;border-top:1px dashed var(--line);padding-top:14px;font-size:12px;color:var(--ink-soft);line-height:1.7}}
  footer ul{{margin:4px 0 8px;padding-left:18px}}
  @media (max-width:520px){{ h1{{font-size:23px}} .prose p{{font-size:15px}} .prose p.headline{{font-size:17px}} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="kicker">월간 실거래 리포트</div>
    <h1>{e(region)} 아파트 매매 {e(ym_label(ym))}</h1>
    <p class="sub">국토교통부 실거래가 기준, 전월({e(ym_label(pm))})과 비교. <a href="index.html">지도에서 보기</a></p>
  </header>

  <section class="card prose">{paragraphs((c or {}).get("summary"))}</section>

  <div class="kpis">{kpis}</div>

  <section>
    <div class="charts">
      <div class="card">
        <p class="chart-t">월별 거래량</p>
        <p class="chart-s">{e(ym_label(yms[0]))}~{e(ym_label(yms[-1]))}, 계약일 기준</p>
        <div class="legend" data-legend></div>
        <div class="chart" id="chart-count"></div>
      </div>
      <div class="card">
        <p class="chart-t">월별 중위 평당가</p>
        <p class="chart-s">전용면적 3.3㎡당 거래금액의 중위값</p>
        <div class="legend" data-legend></div>
        <div class="chart" id="chart-ppy"></div>
      </div>
    </div>
    <details>
      <summary>표로 보기</summary>
      <div class="tw" style="margin-top:8px"><table><thead><tr><th>월</th>{table_head}</tr></thead><tbody>{table_rows}</tbody></table></div>
    </details>
  </section>
{sections}
  <footer>
    <b>읽는 법</b>
    <ul>{notes}<li>{e(prov)}은 신고가 끝나지 않아 차트에 점선(잠정)으로 표시했다.</li></ul>
    해설 문장은 Claude Code 월간 리포트 워크플로가 작성했다. 구마다 분석 에이전트가 초안을 쓰고,
    검증 에이전트가 문장의 숫자를 위 통계와 대조해 고쳤다. 통계와 표는 스크립트가 데이터에서 직접 계산한 값이다.
  </footer>
</div>
<script>
const S = {json.dumps(series, ensure_ascii=False)};
const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent) {{
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}}
function niceTicks(lo, hi, n) {{
  const span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => span / s <= n) || 10 * mag;
  const t0 = Math.floor(lo / step) * step, out = [];
  for (let v = t0; v <= hi + step * 0.001; v += step) out.push(+v.toFixed(6));
  if (out[out.length - 1] < hi) out.push(out[out.length - 1] + step);
  return out;
}}
const fmtCount = v => v.toLocaleString("ko-KR");
const fmtPpy = v => v >= 10000 ? (v / 10000).toFixed(v % 10000 ? 1 : 0) + "억" : v.toLocaleString("ko-KR") + "만";
const mLabel = ym => +ym.slice(5) + "월";

document.querySelectorAll("[data-legend]").forEach(L => {{
  L.innerHTML = S.gus.map((g, i) => `<span><i class="sw" style="background:${{S.colors[i]}}"></i>${{g}}</span>`).join("")
    + `<span><i class="dash"></i>잠정</span>`;
}});

function lineChart(box, key, fmtKey, tickFmt, zero) {{
  box.innerHTML = "";
  const W = box.clientWidth, H = box.clientHeight;
  const m = {{l: 44, r: 58, t: 14, b: 26}};
  const pw = W - m.l - m.r, ph = H - m.t - m.b, n = S.yms.length;
  const all = S.gus.flatMap(g => S[key][g]).filter(v => v != null);
  let lo = zero ? 0 : Math.min(...all), hi = Math.max(...all);
  const ticks = niceTicks(lo, hi, 4);
  lo = ticks[0]; hi = ticks[ticks.length - 1];
  const x = i => m.l + (n === 1 ? pw / 2 : i * pw / (n - 1));
  const y = v => m.t + ph - (v - lo) / (hi - lo) * ph;
  const svg = el("svg", {{viewBox: `0 0 ${{W}} ${{H}}`, role: "img"}}, box);
  const ri = S.yms.indexOf(S.reportYm);
  if (ri >= 0) el("rect", {{x: x(ri) - pw / (n - 1) / 2, y: m.t, width: pw / (n - 1), height: ph, fill: "#f3efe4"}}, svg);
  ticks.forEach(t => {{
    el("line", {{x1: m.l, x2: m.l + pw, y1: y(t), y2: y(t), stroke: "#ece8df", "stroke-width": 1}}, svg);
    el("text", {{x: m.l - 8, y: y(t) + 4, "text-anchor": "end", "font-size": 11, fill: "#52607a"}}, svg).textContent = tickFmt(t);
  }});
  const every = pw / n < 30 ? 2 : 1, anchor = ri >= 0 ? ri : n - 1;  // 좁은 화면에서도 보고 월 라벨은 남긴다
  S.yms.forEach((ym, i) => {{
    if ((anchor - i) % every) return;
    const t = el("text", {{x: x(i), y: H - 6, "text-anchor": "middle", "font-size": 11,
      fill: i === ri ? "#16243b" : "#52607a", "font-weight": i === ri ? 800 : 400}}, svg);
    t.textContent = mLabel(ym);
  }});
  const ends = [];
  S.gus.forEach((g, gi) => {{
    const vals = S[key][g], c = S.colors[gi];
    const solid = vals.map((v, i) => [i, v]).filter(([i, v]) => v != null && !S.provisional[i]);
    const prov = vals.map((v, i) => [i, v]).filter(([i, v]) => v != null && S.provisional[i]);
    const path = pts => pts.map(([i, v], k) => (k ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1)).join("");
    el("path", {{d: path(solid), fill: "none", stroke: c, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round"}}, svg);
    if (prov.length && solid.length) {{
      el("path", {{d: path([solid[solid.length - 1], ...prov]), fill: "none", stroke: c, "stroke-width": 2, "stroke-dasharray": "4 4"}}, svg);
      prov.forEach(([i, v]) => el("circle", {{cx: x(i), cy: y(v), r: 4, fill: "#fff", stroke: c, "stroke-width": 2}}, svg));
    }}
    if (ri >= 0 && vals[ri] != null) el("circle", {{cx: x(ri), cy: y(vals[ri]), r: 4, fill: c, stroke: "#fff", "stroke-width": 2}}, svg);
    const last = [...solid, ...prov].pop();
    if (last) ends.push({{g, c, y: y(last[1]), x: x(last[0])}});
  }});
  ends.sort((a, b) => a.y - b.y);
  for (let k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 14) ends[k].y = ends[k - 1].y + 14;
  ends.forEach(d => {{
    el("text", {{x: d.x + 9, y: d.y + 4, "font-size": 11.5, "font-weight": 700, fill: "#16243b"}}, svg).textContent = d.g;
  }});
  const cross = el("line", {{y1: m.t, y2: m.t + ph, stroke: "#16243b", "stroke-width": 1, opacity: 0}}, svg);
  const tip = document.createElement("div");
  tip.className = "tip"; box.appendChild(tip);
  const hit = el("rect", {{x: m.l - 10, y: 0, width: pw + 20, height: H, fill: "transparent"}}, svg);
  const show = ev => {{
    const r = svg.getBoundingClientRect();
    const px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    const i = Math.max(0, Math.min(n - 1, Math.round((px - m.l) / (pw / (n - 1)))));
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("opacity", .35);
    tip.innerHTML = `<b>${{S.yms[i].slice(0, 4)}}년 ${{mLabel(S.yms[i])}}${{S.provisional[i] ? " (잠정)" : ""}}</b>`
      + S.gus.map((g, gi) => `<div class="row"><i class="sw" style="background:${{S.colors[gi]}}"></i>${{g}} ${{S[fmtKey][g][i]}}${{S.bulk[g][i] ? ` <span style="opacity:.7">(일괄 ${{S.bulk[g][i]}}건 포함)</span>` : ""}}</div>`).join("");
    tip.style.opacity = 1;
    const tw = tip.offsetWidth, left = x(i) + 12 + tw > W ? x(i) - 12 - tw : x(i) + 12;
    tip.style.left = Math.max(0, left) + "px"; tip.style.top = m.t + "px";
  }};
  const hide = () => {{ tip.style.opacity = 0; cross.setAttribute("opacity", 0); }};
  hit.addEventListener("pointermove", show); hit.addEventListener("pointerdown", show);
  hit.addEventListener("pointerleave", hide);
}}
function draw() {{
  lineChart(document.getElementById("chart-count"), "count", "countFmt", fmtCount, true);
  lineChart(document.getElementById("chart-ppy"), "ppy", "ppyFmt", fmtPpy, false);
}}
draw();
let rt; addEventListener("resize", () => {{ clearTimeout(rt); rt = setTimeout(draw, 120); }});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="YYYY-MM (기본: report_stats 기본 달)")
    ap.add_argument("--strict", action="store_true", help="해설 점검에 걸리면 실패")
    a = ap.parse_args()

    stats = rs.compute(a.month)
    ym = stats["meta"]["report_month"]
    cpath = os.path.join(COMMENTARY_DIR, f"{ym}.json")
    c = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else None
    if c is None:
        print(f"주의: {cpath} 가 없어 해설 없이 만든다")
    else:
        problems = check_commentary(c, stats)
        for where, what, text in problems:
            print(f"[점검] {where}: {what}\n        {text}")
        if problems and a.strict:
            sys.exit(3)

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    open(OUT_PATH, "w", encoding="utf-8").write(render(stats, c))
    print(f"생성 완료 → {OUT_PATH} ({ym}, 해설 {'있음' if c else '없음'})")


if __name__ == "__main__":
    main()
