"""
out/trades.json 을 읽어 Leaflet+OSM 기반 지도(out/leaflet_map.html)를 생성한다.
같은 폴더의 leaflet_map.html 을 템플릿으로 삼아 DATA/GUS/YMS 만 교체한다.

특징
- 카카오와 달리 API 키·웹 도메인 등록·로컬 서버가 필요 없다.
  생성된 HTML 은 파일 더블클릭(file://) 만으로 바로 열린다.
- 지도 타일은 표준 OpenStreetMap (키 불필요).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "leaflet_map.html")
IN_PATH = "out/trades.json"
# 기본은 기존대로. 웹/클라우드 세션에선 MAP_OUT=docs/index.html 로 추적 경로에 내보냄
OUT_PATH = os.environ.get("MAP_OUT", "out/leaflet_map.html")

# 템플릿 DATA 구간 마커 (이 두 줄 사이를 통째로 교체)
DATA_START = "/* ==== DATA START"
DATA_END = "/* ==== DATA END ==== */"


def slim_one(p):
    """collect.py 스키마 → 템플릿이 쓰는 경량 스키마."""
    return {
        "apt": p.get("apt", ""),
        "gu": p.get("gu", ""),
        "ym": p.get("ym", ""),
        "dong": p.get("dong", ""),
        "amt": p.get("amount_manwon", 0),
        "py": p.get("pyeong", 0),
        "ppy": p.get("ppy", 0),
        "ar": p.get("area_m2", 0),
        "fl": p.get("floor", ""),
        "by": p.get("build_year", ""),
        "date": p.get("date", ""),
        "lat": round(p["lat"], 6),
        "lng": round(p["lng"], 6),
    }


def main():
    pts = json.load(open(IN_PATH, encoding="utf-8"))
    slim = [slim_one(p) for p in pts if p.get("lat") is not None]
    gus = sorted(set(p["gu"] for p in slim))
    yms = sorted(set(p["ym"] for p in slim))

    html = open(TEMPLATE, encoding="utf-8").read()

    # DATA 구간을 새 데이터로 교체
    start = html.index(DATA_START)
    end = html.index(DATA_END) + len(DATA_END)
    block = (
        DATA_START + " (build_leaflet_map.py 가 이 구간을 교체) ==== */\n"
        "const DATA = " + json.dumps(slim, ensure_ascii=False) + ";\n"
        "const GUS = " + json.dumps(gus, ensure_ascii=False) + ";\n"
        "const YMS = " + json.dumps(yms, ensure_ascii=False) + ";\n"
        + DATA_END
    )
    html = html[:start] + block + html[end:]

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    open(OUT_PATH, "w", encoding="utf-8").write(html)
    print(f"생성 완료 → {OUT_PATH} "
          f"({len(slim)}건, {len(gus)}개 구, {len(yms)}개월) · 키/도메인 등록 불필요")


if __name__ == "__main__":
    main()
