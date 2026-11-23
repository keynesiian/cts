"""
out/trades.json 을 읽어 카카오 지도 기반 지도(out/kakao_map.html)를 생성한다.
kakao_map.html 템플릿의 DATA/GUS/YMS 와 앱키 자리만 교체한다.

- 앱키는 환경변수 KAKAO_JS_API_KEY (JavaScript 키). 없으면 오류로 종료.
- 카카오 콘솔의 플랫폼 Web 에 지도를 띄울 도메인을 등록해야 지도가 뜬다.
- JS 키는 산출 HTML 에 그대로 들어간다. 보호 수단은 도메인 제한뿐이다.
"""
import json
import os
import sys

from build_leaflet_map import slim_one, DATA_START, DATA_END

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "kakao_map.html")
IN_PATH = "out/trades.json"
OUT_PATH = os.environ.get("MAP_OUT", "out/kakao_map.html")
KEY_TOKEN = "__KAKAO_JS_KEY__"


def main():
    key = os.environ.get("KAKAO_JS_API_KEY", "").strip()
    if not key:
        sys.exit("오류: 환경변수 KAKAO_JS_API_KEY(카카오 JavaScript 키)가 없습니다.")

    pts = json.load(open(IN_PATH, encoding="utf-8"))
    slim = [slim_one(p) for p in pts if p.get("lat") is not None]
    gus = sorted(set(p["gu"] for p in slim))
    yms = sorted(set(p["ym"] for p in slim))

    html = open(TEMPLATE, encoding="utf-8").read()
    start = html.index(DATA_START)
    end = html.index(DATA_END) + len(DATA_END)
    block = (
        DATA_START + " (build_kakao_map.py 가 이 구간을 교체) ==== */\n"
        "const DATA = " + json.dumps(slim, ensure_ascii=False) + ";\n"
        "const GUS = " + json.dumps(gus, ensure_ascii=False) + ";\n"
        "const YMS = " + json.dumps(yms, ensure_ascii=False) + ";\n"
        + DATA_END
    )
    html = html[:start] + block + html[end:]
    if html.count(KEY_TOKEN) != 1:
        sys.exit(f"오류: 템플릿에 {KEY_TOKEN} 자리가 정확히 1개여야 합니다.")
    html = html.replace(KEY_TOKEN, key)

    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    open(OUT_PATH, "w", encoding="utf-8").write(html)
    print(f"생성 완료 → {OUT_PATH} ({len(slim)}건, {len(gus)}개 구, {len(yms)}개월)")


if __name__ == "__main__":
    main()
