"""
지도 생성 진입점. 엔진은 Leaflet+OSM 하나만 사용한다(키·도메인 등록·웹서버 불필요).

사용:
    python build_map.py        # out/leaflet_map.html 생성
                               # (웹/클라우드: MAP_OUT=docs/index.html 로 추적 경로에 내보냄)

입력은 out/trades.json (먼저 python collect.py 로 생성).
"""
import build_leaflet_map


def main():
    build_leaflet_map.main()


if __name__ == "__main__":
    main()
