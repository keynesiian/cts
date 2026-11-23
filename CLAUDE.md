# 아파트 실거래가 지도

국토교통부 아파트 매매 실거래가 수집 → 카카오 지오코딩으로 좌표 결합 → 인터랙티브 HTML 지도 생성 파이프라인.
지도 엔진은 **카카오 지도**(기본, JS 키 있을 때)와 **Leaflet+OSM**(키 불필요) 둘이다. `MAP_ENGINE=kakao|leaflet`로 고르고, 없으면 `KAKAO_JS_API_KEY`가 있을 때 kakao, 없으면 leaflet.

## 파일 역할
- `pipeline.py` : 핵심. 실거래가 조회(fetch_trades) + 카카오 지오코딩(geocode, 캐시) + 주소조립(address_for) + 좌표결합(enrich) + 내보내기(export)
- `collect.py` : 여러 구·여러 달 수집 → `out/trades.{json,csv,geojson}` 저장. 상단 TARGETS/MONTHS만 수정. 좌표까지 붙인 결과는 추적되는 `data/trades.json`에 월 누적(수집한 구·월만 교체, 나머지 월 유지)
- `lawd_codes.py` : 시군구코드(LAWD_CD 5자리) → "시도 시군구" 매핑. 없는 지역은 dict에 추가
- `build_map.py` : 지도 생성 진입점(MAP_ENGINE으로 엔진 선택)
- `build_kakao_map.py` / `kakao_map.html` : 카카오 지도 JS SDK + MarkerClusterer. 템플릿 DATA/GUS/YMS와 앱키 자리(`__KAKAO_JS_KEY__`)를 치환. 키는 `KAKAO_JS_API_KEY`, 없으면 오류 종료
- `build_leaflet_map.py` / `leaflet_map.html` : 템플릿 DATA/GUS/YMS 치환 → 산출 HTML
- `report_stats.py` : `data/trades.json` → 월간 리포트용 구별 통계 `out/report/stats.json`. 숫자는 전부 여기서 계산(기본 달은 데이터 마지막 달의 전달, 마지막 달은 신고 중인 잠정치)
- `build_report.py` : 통계 + 해설(`data/report/YYYY-MM.json`) → 리포트 HTML. `--strict`는 해설에 통계에 없는 금액, 비율, 건수나 금지 문장부호가 있으면 실패
- `.claude/workflows/monthly-report.js` : 월간 리포트 워크플로(`/monthly-report`). 통계 계산 1 + 구별 초안 3 + 구별 반박 검증 3 + 발행 1, 에이전트 8개
- `secrets.env` : API 키. **절대 커밋 금지**(.gitignore 등록)

## 데이터 규칙
- `amount_manwon`=거래총액(만원), `area_m2`=전용면적, `pyeong`=평(㎡/3.3058), `ppy`=평당가(만원), `date`=YYYY-MM-DD, `ym`=YYYY-MM
- 좌표는 지번 중심점 → 같은 단지 여러 거래가 한 점에 겹칠 수 있음(클러스터링으로 묶임)
- 해제(취소) 거래(API `cdealType`="O")는 `collect.py`가 수집 단계에서 제외. 해제 신고는 계약 뒤 늦게 들어오므로, 오래된 달도 가끔 다시 수집해야 반영됨

## 반드시 지킬 주의점
- 구 접두사는 `estateAgentSggNm`(중개업소 소재지)가 아니라 `sggCd`(매물 실제 구) 기준으로 조립. 안 그러면 지오코딩 성공률 급락
- data.go.kr WAF는 UA 없는 요청 차단 → 항상 `UA="Mozilla/5.0"` 지정, 4xx 대비 재시도/백오프 유지
- `fetch_trades`의 `num_rows`는 크게(기본 1000) 둘 것. 작게 주면 totalCount까지 그 크기로 페이지네이션해 매우 느려짐
- 카카오 지오코딩(REST 키)은 캐시 적용(같은 지번 1회만 호출 = 일일 할당량 절약). REST는 도메인 등록 불필요
- 코드 수정은 최소 변경 위주, 기존 디자인/동작 보존

## 실행 (로컬)
```
python collect.py        # out/trades.{json,csv,geojson}
python build_map.py      # out/kakao_map.html 또는 out/leaflet_map.html
```

## 월간 리포트
```
/monthly-report                                   # Claude Code에서. 결과 data/report/YYYY-MM.json, docs/report.html
REPORT_OUT=docs/report.html python build_report.py --strict   # 해설은 두고 표와 차트만 다시 그릴 때
```
- 해설 규칙: 숫자는 stats의 `*_fmt` 문자열 그대로, 데이터에 없는 원인 추측 금지, 잠정 달은 비교 근거로 쓰지 않음
- 일괄 거래: 한 단지에서 같은 날 10건 이상 신고된 거래(`BULK_MIN`)는 `bulk`로 분리하고 제외 수치 `ex_bulk`를 함께 계산. 청년주택 같은 소형 일괄 거래 하나가 구 합계와 중위값을 뒤집을 수 있음(2026년 9월 송파해링턴타워 170건)

## 카카오 지도 주의점
- 카카오 개발자 콘솔의 앱 > 플랫폼 > Web에 `https://keynesiian.github.io`를 등록해야 지도가 뜬다. 미등록이면 SDK 인증 오류.
- JS 키는 산출 `docs/index.html`에 그대로 들어가 공개 저장소에 노출된다. 보호 수단은 Web 도메인 제한뿐이다.
- 이 샌드박스에서는 카카오 SDK 인증과 github.io가 막혀 실제 지도 렌더링은 확인하지 못했다. 마커 갱신 로직은 SDK 모킹으로만 검증.

## 실행 (Claude Code 웹/클라우드 세션)
클라우드 샌드박스는 연결된 GitHub repo로 돌며 `secrets.env`/`out/`은 gitignore라 부재한다. 다음 전제로 동작한다.

- **키**: 파일이 아니라 세션 환경변수(secret)로 주입 — `APT_TRADE_ENDPOINT`, `APT_TRADE_API_KEY`, `KAKAO_REST_API_KEY`(지오코딩용, 필수), `KAKAO_JS_API_KEY`(카카오 지도 SDK용 JavaScript 키). 네이티브 앱 키는 웹 지도와 REST에 쓰이지 않는다. GitHub Actions에도 같은 이름의 secret 등록이 필요하다. `load_env`가 파일 없으면 env에서 읽는다.
- **출력 수신**: `MAP_OUT=docs/index.html` 환경변수를 주면 최종 HTML이 추적되는 `docs/`로 떨어진다 → 커밋/PR에 포함, GitHub Pages로 폰에서 열람.
- **네트워크 허용 도메인**: `apis.data.go.kr`, `data.go.kr`, `dapi.kakao.com`, `github.com`
- 차단 시 응답 헤더 `x-deny-reason`으로 막힌 도메인 확인 후 허용 목록에 추가.

권장 세션 명령:
```
MAP_OUT=docs/index.html python collect.py && MAP_OUT=docs/index.html python build_map.py
```
