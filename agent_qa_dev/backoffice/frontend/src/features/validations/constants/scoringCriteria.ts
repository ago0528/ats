export type ScoringCriteriaRow = {
  key:
    | 'intent'
    | 'accuracy'
    | 'consistency'
    | 'latencySingle'
    | 'latencyMulti'
    | 'stability';
  metricLabel: string;
  meaning: string;
  scoreRange: string;
  aggregationTarget: string;
  totalScoreIncluded: '포함' | '조건부 포함' | '제외';
};

export const SCORING_CRITERIA_ROWS: ScoringCriteriaRow[] = [
  {
    key: 'intent',
    metricLabel: '의도 충족',
    meaning: '질의 의도와 요구사항 충족 수준',
    scoreRange: '0~5',
    aggregationTarget: '의도 충족 점수가 있는 질의',
    totalScoreIncluded: '포함',
  },
  {
    key: 'accuracy',
    metricLabel: '정확성',
    meaning: '핵심 정보 정확성 및 사실 일치 여부',
    scoreRange: '0~5',
    aggregationTarget: '정확성 점수가 있는 질의',
    totalScoreIncluded: '포함',
  },
  {
    key: 'consistency',
    metricLabel: '일관성',
    meaning: '같은 질문을 반복 실행했을 때의 답변 일관성',
    scoreRange: '0~5',
    aggregationTarget: '같은 질문을 2회 이상 실행한 항목',
    totalScoreIncluded: '조건부 포함',
  },
  {
    key: 'latencySingle',
    metricLabel: '응답 속도 (싱글)',
    meaning: '단일 도구 사용 기준 응답 속도 점수',
    scoreRange: '0~5',
    aggregationTarget: '응답 속도 타입이 "싱글"인 질의',
    totalScoreIncluded: '제외',
  },
  {
    key: 'latencyMulti',
    metricLabel: '응답 속도 (멀티)',
    meaning: '복수 도구 사용 기준 응답 속도 점수',
    scoreRange: '0~5',
    aggregationTarget: '응답 속도 타입이 "멀티"인 질의',
    totalScoreIncluded: '제외',
  },
  {
    key: 'stability',
    metricLabel: '안정성',
    meaning: '에러율/빈응답율 기반 안정성',
    scoreRange: '0~5',
    aggregationTarget: '전체 질의',
    totalScoreIncluded: '포함',
  },
];

export const SCORING_CRITERIA_TOTAL_SCORE_RULE_TEXT =
  '최종 점수는 의도 충족, 정확성, 안정성 점수를 평균해 계산합니다. 일관성 점수가 있으면 함께 평균합니다.';

export const SCORING_CRITERIA_EXCEPTION_RULES = [
  '같은 질문을 1회만 실행한 경우에는 일관성 점수를 계산하지 않습니다.',
  "LLM 응답 형식이 기준에 맞지 않으면 해당 항목은 '평가 오류'로 표시됩니다. (내부 상태값: DONE_WITH_LLM_ERROR)",
] as const;

export const SCORING_CRITERIA_VERSION_TEXT = '기준 버전: v2 (2026-02-26)';
