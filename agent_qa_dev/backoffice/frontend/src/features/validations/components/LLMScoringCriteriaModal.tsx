import { Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { StandardModal } from '../../../components/common/StandardModal';
import {
  SCORING_CRITERIA_EXCEPTION_RULES,
  SCORING_CRITERIA_ROWS,
  SCORING_CRITERIA_TOTAL_SCORE_RULE_TEXT,
  SCORING_CRITERIA_VERSION_TEXT,
  type ScoringCriteriaRow,
} from '../constants/scoringCriteria';

const TOTAL_SCORE_INCLUDED_COLOR: Record<
  ScoringCriteriaRow['totalScoreIncluded'],
  string
> = {
  포함: 'green',
  '조건부 포함': 'gold',
  제외: 'default',
};

const columns: ColumnsType<ScoringCriteriaRow> = [
  {
    key: 'metricLabel',
    title: '지표',
    dataIndex: 'metricLabel',
    width: 120,
  },
  {
    key: 'meaning',
    title: '의미',
    dataIndex: 'meaning',
    width: 280,
  },
  {
    key: 'scoreRange',
    title: '점수 범위',
    dataIndex: 'scoreRange',
    width: 110,
  },
  {
    key: 'aggregationTarget',
    title: '집계 대상',
    dataIndex: 'aggregationTarget',
    width: 310,
  },
  {
    key: 'totalScoreIncluded',
    title: '최종 점수 반영',
    dataIndex: 'totalScoreIncluded',
    width: 150,
    render: (value: ScoringCriteriaRow['totalScoreIncluded']) => (
      <Tag color={TOTAL_SCORE_INCLUDED_COLOR[value]}>{value}</Tag>
    ),
  },
];

export function LLMScoringCriteriaModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <StandardModal
      title="LLM 평가 기준표"
      open={open}
      onCancel={onClose}
      onOk={onClose}
      okText="닫기"
      cancelButtonProps={{ style: { display: 'none' } }}
      width="min(920px, calc(100vw - 24px))"
      contentHeight="80vh"
      // bodyPadding={16}
      destroyOnHidden
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div>
          <Typography.Title
            level={5}
            style={{ marginTop: 16, marginBottom: 8 }}
          >
            지표 요약
          </Typography.Title>
          <Table<ScoringCriteriaRow>
            rowKey="key"
            size="small"
            tableLayout="fixed"
            pagination={false}
            columns={columns}
            dataSource={SCORING_CRITERIA_ROWS}
            scroll={{ x: 940 }}
          />
        </div>

        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            최종 점수 계산 방식
          </Typography.Title>
          <Typography.Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
            {SCORING_CRITERIA_TOTAL_SCORE_RULE_TEXT}
          </Typography.Paragraph>
          <Typography.Paragraph
            type="secondary"
            style={{ marginTop: 6, marginBottom: 0 }}
          >
            응답 속도 점수(싱글/멀티)는 참고 지표로만 사용되며, 최종 점수에는
            반영되지 않습니다.
          </Typography.Paragraph>
        </div>

        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            예외 상황 안내
          </Typography.Title>
          <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
            {SCORING_CRITERIA_EXCEPTION_RULES.map((rule) => (
              <li key={rule}>
                <Typography.Text>{rule}</Typography.Text>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            기준 정보
          </Typography.Title>
          <Typography.Paragraph
            type="secondary"
            style={{ marginTop: 8, marginBottom: 0 }}
          >
            {SCORING_CRITERIA_VERSION_TEXT}
          </Typography.Paragraph>
        </div>
      </div>
    </StandardModal>
  );
}
