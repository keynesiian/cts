"""
지도 생성 진입점. 기본 엔진은 Leaflet+OSM(키·도메인 등록·웹서버 불필요).
MAP_ENGINE=kakao 를 주면 카카오맵으로 만든다(카카오 JavaScript 키와 SDK 도메인 등록 필요).

사용:
    python build_map.py                      # out/leaflet_map.html 생성
                                             # (웹/클라우드: MAP_OUT=docs/index.html 로 추적 경로에 내보냄)
    MAP_ENGINE=kakao python build_map.py     # out/kakao_map.html 생성 (자세한 옵션은 build_kakao_map.py)

입력은 out/trades.json (먼저 python collect.py 로 생성).
"""
import os


def main():
    if os.environ.get("MAP_ENGINE", "leaflet").lower() == "kakao":
        import build_kakao_map
        build_kakao_map.main()
    else:
        import build_leaflet_map
        build_leaflet_map.main()


if __name__ == "__main__":
    main()
