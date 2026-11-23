"""
지도 생성 진입점. 엔진은 MAP_ENGINE=kakao|leaflet 로 고른다.
기본은 KAKAO_JS_API_KEY 가 있으면 kakao, 없으면 leaflet.

사용:
    python build_map.py        # out/kakao_map.html 또는 out/leaflet_map.html 생성
                               # (웹/클라우드: MAP_OUT=docs/index.html 로 추적 경로에 내보냄)

입력은 out/trades.json (먼저 python collect.py 로 생성).
Leaflet+OSM 은 키·도메인 등록이 필요 없고, 카카오는 JS 키와 콘솔의 Web 도메인 등록이 필요하다.
"""
import os

import build_kakao_map
import build_leaflet_map


def main():
    engine = os.environ.get("MAP_ENGINE", "").strip().lower()
    if not engine:
        engine = "kakao" if os.environ.get("KAKAO_JS_API_KEY", "").strip() else "leaflet"
    if engine == "kakao":
        build_kakao_map.main()
    elif engine == "leaflet":
        build_leaflet_map.main()
    else:
        raise SystemExit(f"MAP_ENGINE 은 kakao 또는 leaflet 이어야 합니다: {engine}")


if __name__ == "__main__":
    main()
