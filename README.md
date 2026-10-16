# 브랜드 검색량 비교

우리 브랜드와 경쟁사의 네이버 검색량을 일·주·월 단위로 비교하는 HTML 웹앱입니다.

## 구조

| 경로 | 역할 |
|---|---|
| `config/brands.json` | 추적할 브랜드와 키워드 목록. 여기만 고치면 됩니다. |
| `collector/collect.py` | 네이버 API에서 검색량을 받아 `docs/data/daily.json`에 저장 (파이썬 기본 라이브러리만 사용) |
| `collector/demo_data.py` | API 키 없이 화면을 볼 수 있게 예시 데이터를 만듦 |
| `docs/index.html` | 대시보드 웹앱 (GitHub Pages로 공개) |
| `.github/workflows/collect.yml` | 매일 오전 9시 자동 수집 |

## 숫자를 만드는 방법

- **검색어 트렌드(Search Trend) API**: 날짜별 상대 지수(0~100). 2026년에 네이버 개발자센터에서 네이버 클라우드의 NAVER API HUB로 옮겨졌습니다.
- **검색광고 키워드도구 API**: 최근 30일 실제 검색 수(PC+모바일)

브랜드마다 `배율 = 최근 30일 실제 검색 수 ÷ 최근 30일 지수 합`을 구해 지수에 곱하면 일별 추정 검색 수가 됩니다.
검색광고 키가 없으면 지수만 저장되고, 대시보드는 '데이터랩 지수' 모드로만 동작합니다.

## API 키 발급 (둘 다 무료)

1. **검색어 트렌드 (NAVER API HUB)** — 네이버 개발자센터 신규 신청은 2026년 7월 31일에 닫혔습니다.
   https://www.ncloud.com 가입 → 콘솔 → Services → Application Service → **NAVER API HUB** 이용 신청 → Application 등록 시 **Search Trend** 선택 → 발급된 Client ID, Client Secret 복사.
   계정용 IAM Access Key(`ncp_iam_...`)가 아니라 앱에서 발급된 키를 써야 합니다. 현재는 한시적으로 무료이고, 월 5만 회까지 호출할 수 있습니다.
2. **검색광고** — https://searchad.naver.com 가입 → 광고시스템 → 도구 → API 사용 관리 → 'API 라이선스 발급' → 액세스라이선스(API_KEY), 비밀키(SECRET), CUSTOMER_ID 복사. 광고비를 쓰지 않아도 발급됩니다.

## 로컬에서 실행

```bash
# 예시 데이터로 화면 보기
python3 collector/demo_data.py
cd docs && python3 -m http.server 8000   # 브라우저에서 http://localhost:8000

# 실제 수집
export NAVER_CLIENT_ID=... NAVER_CLIENT_SECRET=...
export SEARCHAD_API_KEY=... SEARCHAD_SECRET=... SEARCHAD_CUSTOMER_ID=...
python3 collector/collect.py
```

## GitHub에 올려 매일 자동으로 돌리기

1. 이 폴더를 GitHub 저장소로 올립니다.
2. Settings → Secrets and variables → Actions 에 위 5개 키를 같은 이름으로 등록합니다.
3. Settings → Pages 에서 Branch를 `main`, 폴더를 `/docs`로 지정합니다.
4. Actions 탭에서 '네이버 검색량 수집'을 한 번 수동 실행하면 과거 데이터까지 채워집니다.

## 브랜드 추가·수정

`config/brands.json`의 `groups`에 항목을 추가합니다. `keywords`는 사람들이 실제로 검색하는 표현을 넣으세요(띄어쓰기 변형 포함, 최대 20개).
내 브랜드는 `is_mine: true`이며, 키워드가 비어 있는 동안은 수집을 건너뜁니다.

## 한계

- 데이터랩은 검색이 아주 적은 날을 0으로 돌려줍니다. 신생 브랜드는 초기 값이 들쭉날쭉할 수 있습니다.
- 추정치는 최근 30일 실제 검색 수를 기준으로 과거 전체를 환산하므로, 오래된 기간일수록 오차가 커질 수 있습니다.
- 데이터랩 API는 하루 1,000회 호출 제한이 있습니다. 브랜드 1곳당 하루 1회 호출합니다.
