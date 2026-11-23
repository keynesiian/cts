"""
out/trades.json 을 읽어 카카오맵 기반 지도(out/kakao_map.html)를 생성한다.
같은 폴더의 kakao_map.html 을 템플릿으로 삼아 DATA/GUS/YMS/DEFAULT_YM 과 JavaScript 키를 채운다.

Leaflet 판과 다른 점
- 카카오 JavaScript 키(KAKAO_JS_API_KEY)가 필요하다. REST 키와 다르다.
- 카카오 디벨로퍼스에서 그 앱의 카카오맵 사용 설정을 켜고, JavaScript 키의 SDK 도메인에
  지도를 열 주소(예: https://<계정>.github.io)를 등록해야 지도가 뜬다. file:// 로는 열리지 않는다.
- JavaScript 키는 페이지 소스에 그대로 들어간다(카카오 JS 키는 원래 공개되는 키이고 도메인 등록으로 막는다).

환경변수
  MAP_OUT : 산출 경로(기본 out/kakao_map.html, 웹/클라우드 세션은 docs/kakao.html 권장)
  MAP_IN  : 입력 경로(기본 out/trades.json, 수집 없이 누적본으로 그릴 때 data/trades.json)
  MAP_YM  : 처음 열 때 고를 거래월 YYYY-MM(기본 데이터의 마지막 달, "all" 이면 전체)
"""
import json
import os

import build_leaflet_map as base
from pipeline import load_env

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "kakao_map.html")
IN_PATH = os.environ.get("MAP_IN", base.IN_PATH)
OUT_PATH = os.environ.get("MAP_OUT", "out/kakao_map.html")
KEY_TOKEN = "__KAKAO_JS_API_KEY__"


def main():
    key = load_env().get("KAKAO_JS_API_KEY")
    if not key:
        raise SystemExit("KAKAO_JS_API_KEY 가 없습니다. secrets.env 나 환경변수에 카카오 JavaScript 키를 넣어 주세요.")

    pts = json.load(open(IN_PATH, encoding="utf-8"))
    slim = [base.slim_one(p) for p in pts if p.get("lat") is not None]
    gus = sorted(set(p["gu"] for p in slim))
    yms = sorted(set(p["ym"] for p in slim))
    ym = os.environ.get("MAP_YM") or (yms[-1] if yms else "all")
    if ym != "all" and ym not in yms:
        raise SystemExit(f"MAP_YM={ym} 거래가 없습니다. 있는 달은 {', '.join(yms)}")

    html = open(TEMPLATE, encoding="utf-8").read()

    start = html.index(base.DATA_START)
    end = html.index(base.DATA_END) + len(base.DATA_END)
    block = (
        base.DATA_START + " (build_kakao_map.py 가 이 구간을 교체) ==== */\n"
        "const DATA = " + json.dumps(slim, ensure_ascii=False) + ";\n"
        "const GUS = " + json.dumps(gus, ensure_ascii=False) + ";\n"
        "const YMS = " + json.dumps(yms, ensure_ascii=False) + ";\n"
        "const DEFAULT_YM = " + json.dumps(ym) + ";\n"
        + base.DATA_END
    )
    html = html[:start] + block + html[end:]
    html = html.replace(KEY_TOKEN, key)

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    open(OUT_PATH, "w", encoding="utf-8").write(html)
    n_ym = sum(1 for p in slim if p["ym"] == ym)
    print(f"생성 완료 → {OUT_PATH} ({len(slim)}건, {len(gus)}개 구, {len(yms)}개월, "
          f"처음 화면 {ym} {n_ym if ym != 'all' else len(slim)}건) · 카카오 SDK 도메인 등록 필요")


if __name__ == "__main__":
    main()
