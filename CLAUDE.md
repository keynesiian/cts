# 아파트 실거래가 지도

국토교통부 아파트 매매 실거래가 수집 → 카카오 지오코딩으로 좌표 결합 → 인터랙티브 HTML 지도 생성 파이프라인.
지도 엔진은 **Leaflet+OSM** 하나만 사용한다(키·도메인 등록·웹서버 불필요).

## 파일 역할
- `pipeline.py` : 핵심. 실거래가 조회(fetch_trades) + 카카오 지오코딩(geocode, 캐시) + 주소조립(address_for) + 좌표결합(enrich) + 내보내기(export)
- `collect.py` : 여러 구·여러 달 수집 → `out/trades.{json,csv,geojson}` 저장. 상단 TARGETS/MONTHS만 수정
- `lawd_codes.py` : 시군구코드(LAWD_CD 5자리) → "시도 시군구" 매핑. 없는 지역은 dict에 추가
- `build_map.py` : 지도 생성 진입점(Leaflet 전용)
- `build_leaflet_map.py` / `leaflet_map.html` : 템플릿 DATA/GUS/YMS 치환 → 산출 HTML
- `secrets.env` : API 키. **절대 커밋 금지**(.gitignore 등록)

## 데이터 규칙
- `amount_manwon`=거래총액(만원), `area_m2`=전용면적, `pyeong`=평(㎡/3.3058), `ppy`=평당가(만원), `date`=YYYY-MM-DD, `ym`=YYYY-MM
- 좌표는 지번 중심점 → 같은 단지 여러 거래가 한 점에 겹칠 수 있음(클러스터링으로 묶임)

## 반드시 지킬 주의점
- 구 접두사는 `estateAgentSggNm`(중개업소 소재지)가 아니라 `sggCd`(매물 실제 구) 기준으로 조립. 안 그러면 지오코딩 성공률 급락
- data.go.kr WAF는 UA 없는 요청 차단 → 항상 `UA="Mozilla/5.0"` 지정, 4xx 대비 재시도/백오프 유지
- `fetch_trades`의 `num_rows`는 크게(기본 1000) 둘 것. 작게 주면 totalCount까지 그 크기로 페이지네이션해 매우 느려짐
- 카카오 지오코딩(REST 키)은 캐시 적용(같은 지번 1회만 호출 = 일일 할당량 절약). REST는 도메인 등록 불필요
- 코드 수정은 최소 변경 위주, 기존 디자인/동작 보존

## 실행 (로컬)
```
python collect.py        # out/trades.{json,csv,geojson}
python build_map.py      # out/leaflet_map.html
```

## 실행 (Claude Code 웹/클라우드 세션)
클라우드 샌드박스는 연결된 GitHub repo로 돌며 `secrets.env`/`out/`은 gitignore라 부재한다. 다음 전제로 동작한다.

- **키**: 파일이 아니라 세션 환경변수(secret)로 주입 — `APT_TRADE_ENDPOINT`, `APT_TRADE_API_KEY`, `KAKAO_REST_API_KEY`(지오코딩용, 필수). `load_env`가 파일 없으면 env에서 읽는다.
- **출력 수신**: `MAP_OUT=docs/index.html` 환경변수를 주면 최종 HTML이 추적되는 `docs/`로 떨어진다 → 커밋/PR에 포함, GitHub Pages로 폰에서 열람.
- **네트워크 허용 도메인**: `apis.data.go.kr`, `data.go.kr`, `dapi.kakao.com`, `github.com`
- 차단 시 응답 헤더 `x-deny-reason`으로 막힌 도메인 확인 후 허용 목록에 추가.

권장 세션 명령:
```
MAP_OUT=docs/index.html python collect.py && MAP_OUT=docs/index.html python build_map.py
```
