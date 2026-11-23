export const meta = {
  name: 'monthly-report',
  description: '월간 실거래 리포트: 구별 해설 초안, 숫자 반박 검증, docs/report.html 생성',
  whenToUse: 'data/trades.json 이 갱신된 뒤 구별 시장 해설을 붙인 월간 리포트를 만들 때. args 로 {"month": "YYYY-MM"} 를 주면 그 달, 없으면 신고 기한이 지난 최근 달.',
  phases: [
    { title: 'Prep', detail: 'report_stats.py 로 통계 계산' },
    { title: 'Draft', detail: '구마다 분석 에이전트가 해설 초안' },
    { title: 'Verify', detail: '구마다 검증 에이전트가 숫자와 주장을 통계와 대조' },
    { title: 'Publish', detail: '종합 요약, build_report.py --strict 통과까지 반복' },
  ],
}

// 숫자는 스크립트가 계산하고(report_stats.py), 에이전트는 out/report/stats.json 의 값만 인용해 해설을 쓴다.
const month = (args && (args.month || (typeof args === 'string' ? args : ''))) || ''

const RULES = `
규칙
1. 숫자는 out/report/stats.json 에 있는 값만 쓰고, *_fmt 문자열을 글자 그대로 옮긴다(예: "1억 1,778만원", "+25.0%", "125건"). 새로 계산하거나 반올림하거나 "약"으로 뭉개지 않는다. 변화율은 stats 에 있는 *_pct_fmt 만 쓴다.
2. 데이터에 없는 원인(정책, 금리, 재건축 기대 등)은 쓰지 않는다. 데이터로 확인되는 사실만 쓰고, 원인을 말해야 할 자리에서는 데이터만으로는 알 수 없다고 밝힌다.
3. 중위 평당가는 그 달에 어느 동, 어느 면적대가 많이 거래됐는지에 따라 움직인다. 중위값 변화를 시세 상승이나 하락으로 단정하지 말고, 구성 변화(bands, top_dongs)를 함께 본다.
4. meta.provisional_months 의 달은 신고가 덜 들어온 잠정치라 비교 근거로 쓰지 않는다.
5. 문장부호. 가운뎃점(·), 줄표(—, –), 쌍점(:)을 쓰지 않는다. 열거는 쉼표나 '와/과'로 잇고, 범위는 물결표(~)를 쓴다.
6. 평서문 '~다' 체로 쓰고, 단지명은 데이터 표기 그대로 쓴다.`

const PREP = {
  type: 'object',
  properties: {
    month: { type: 'string' },
    prev_month: { type: 'string' },
    gus: { type: 'array', items: { type: 'string' } },
    provisional: { type: 'boolean' },
  },
  required: ['month', 'prev_month', 'gus', 'provisional'],
}
const DRAFT = {
  type: 'object',
  properties: {
    headline: { type: 'string' },
    paragraphs: { type: 'array', items: { type: 'string' } },
  },
  required: ['headline', 'paragraphs'],
}
const VERIFIED = {
  type: 'object',
  properties: {
    headline: { type: 'string' },
    paragraphs: { type: 'array', items: { type: 'string' } },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: { quote: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' } },
        required: ['quote', 'problem', 'fix'],
      },
    },
  },
  required: ['headline', 'paragraphs', 'issues'],
}
const PUBLISHED = {
  type: 'object',
  properties: {
    summary_headline: { type: 'string' },
    check_runs: { type: 'number' },
    fixes: { type: 'array', items: { type: 'string' } },
    files: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary_headline', 'check_runs', 'fixes', 'files'],
}

phase('Prep')
const prep = await agent(
  `저장소 루트에서 \`python report_stats.py${month ? ' --month ' + month : ''}\` 를 실행하라. ` +
  `실패하면 오류 내용을 그대로 보고하고 멈춘다. 성공하면 out/report/stats.json 의 meta 에서 ` +
  `report_month, prev_month, gus, report_month_provisional 을 읽어 돌려준다. 다른 파일은 고치지 않는다.`,
  { label: 'stats', phase: 'Prep', schema: PREP, effort: 'low' },
)
if (!prep) throw new Error('통계 계산 단계가 실패했다')
const { month: ym, prev_month: pm, gus } = prep
log(`${ym} 리포트, 비교 ${pm}, 대상 ${gus.join(', ')}`)
if (prep.provisional) log(`주의: ${ym} 는 신고 기한이 지나지 않은 잠정치다`)

const sections = await pipeline(
  gus,
  gu => agent(
    `너는 ${gu} 아파트 매매 시장 해설을 쓰는 분석가다. 저장소 루트의 out/report/stats.json 을 읽어라. ` +
    `근거는 gus["${gu}"] (${ym} 통계, 전월 ${pm} 비교 change, 12개월 series, bands, top_dongs, top_apts, top_trades, record_highs) 와 meta 다.\n\n` +
    `${ym} ${gu} 시장 해설을 쓴다.\n` +
    `- headline: 이 달 ${gu}에서 가장 눈에 띄는 변화를 담은 한 문장(60자 이내).\n` +
    `- paragraphs: 2~3문단, 문단마다 2~4문장. 거래량과 전월 대비 변화, 12개월 흐름 속 중위 평당가, 면적대별 차이, ` +
    `거래가 몰린 동과 단지, 신고가 거래(record_highs.count 와 comparable, 대표 사례)를 다룬다.\n` + RULES,
    { label: `draft:${gu}`, phase: 'Draft', schema: DRAFT },
  ),
  (draft, gu) => draft && agent(
    `너는 ${gu} 해설 초안을 반박 검증하는 검토자다. 초안 작성자와 독립적으로, 틀린 곳이 있다고 가정하고 찾아라. ` +
    `근거는 저장소 루트 out/report/stats.json 의 gus["${gu}"] 와 meta 다.\n\n` +
    `점검 항목\n` +
    `1. 숫자. 문장 속 숫자 하나하나가 stats 의 어느 키 값과 같은지 찾는다. 없는 숫자, 반올림한 숫자, ` +
    `다른 달이나 다른 항목의 값을 잘못 붙인 경우(전월 값을 이번 달 값으로, 면적대 값을 구 전체 값으로 쓴 것 등)를 잡는다.\n` +
    `2. 방향과 비교. 증가와 감소, 최고와 최저, 순위, "가장" 같은 주장이 데이터와 맞는지 본다.\n` +
    `3. 근거 없는 원인 주장, 중위값 변화를 시세 변화로 단정한 표현.\n` +
    `4. 잠정 달 데이터를 비교 근거로 쓴 문장.\n` +
    `5. 금지 문장부호.\n\n` +
    `문제를 모두 고친 headline 과 paragraphs 를 돌려준다. 고칠 때도 아래 규칙을 지키고, 문제없는 문장은 그대로 둔다. ` +
    `issues 에는 실제로 고친 곳만 {quote: 원문 일부, problem: 무엇이 틀렸나, fix: 어떻게 고쳤나} 로 적는다.\n` + RULES +
    `\n\n초안\n${JSON.stringify(draft, null, 1)}`,
    { label: `verify:${gu}`, phase: 'Verify', schema: VERIFIED },
  ),
)

const done = {}
gus.forEach((gu, i) => { if (sections[i]) done[gu] = sections[i] })
const missing = gus.filter(gu => !done[gu])
if (missing.length) log(`해설을 만들지 못한 구: ${missing.join(', ')} (리포트에는 해설 없이 표만 실린다)`)
if (!Object.keys(done).length) throw new Error('구별 해설이 하나도 만들어지지 않았다')

const payload = {}
for (const gu of Object.keys(done)) {
  const s = done[gu]
  payload[gu] = {
    headline: s.headline,
    paragraphs: s.paragraphs,
    review: { issues: s.issues.length, notes: s.issues.map(x => `${x.problem} → ${x.fix}`) },
  }
}

phase('Publish')
const published = await agent(
  `너는 월간 실거래 리포트 편집자다. 검증을 마친 구별 해설과 저장소 루트 out/report/stats.json 의 overall, meta 로 리포트를 완성한다.\n\n` +
  `1. 종합 요약(summary)을 쓴다. headline 한 문장(60자 이내), paragraphs 2문단. ${gus.length}개 구 합계(overall)의 거래량과 ` +
  `중위 평당가 변화, 구별 차이를 묶어 말한다. 합계 중위 평당가는 구별 거래 비중에 따라 움직이므로(평당가가 낮은 구의 거래가 늘면 ` +
  `합계 중위값이 내려간다) 합계와 구별 방향이 다르면 그 점을 짚는다. 구별 숫자는 stats 의 gus 값을 쓴다.\n` +
  `2. data/report/${ym}.json 을 쓴다(디렉터리가 없으면 만들고, UTF-8 로 한글을 그대로 저장). 형식은 ` +
  `{"month": "${ym}", "summary": {"headline": ..., "paragraphs": [...]}, "sections": <아래 구별 해설 그대로>} 이다. ` +
  `구별 해설은 점검에 걸릴 때만 고친다.\n` +
  `3. \`REPORT_OUT=docs/report.html python build_report.py --month ${ym} --strict\` 를 실행한다. [점검] 줄과 함께 실패하면 ` +
  `지적된 문장을 고쳐(숫자는 stats 의 *_fmt 값으로, 문장부호는 규칙대로) JSON 을 다시 쓰고 통과할 때까지 반복한다. ` +
  `구별 해설을 고쳤다면 그 구 review.notes 에 한 줄 덧붙이고 review.issues 를 1 늘린다.\n` +
  `4. 이 두 파일(data/report/${ym}.json, docs/report.html) 말고는 건드리지 않고, 커밋하지 않는다.\n` + RULES +
  `\n\n돌려줄 것. 최종 summary headline, build_report.py 실행 횟수, 고친 내용 목록, 쓴 파일 경로.\n\n` +
  `구별 해설(검증 완료)\n${JSON.stringify(payload, null, 1)}`,
  { label: 'publish', phase: 'Publish', schema: PUBLISHED },
)
if (!published) throw new Error('발행 단계가 실패했다')

return {
  month: ym,
  prev_month: pm,
  reviewed: Object.fromEntries(Object.entries(payload).map(([gu, s]) => [gu, s.review])),
  missing,
  published,
}
