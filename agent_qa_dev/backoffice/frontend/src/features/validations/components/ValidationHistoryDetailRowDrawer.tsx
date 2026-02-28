import {
  Collapse,
  Descriptions,
  Drawer,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd';

import type { HistoryDetailTab } from '../types';
import type {
  HistoryRowView,
  ResultsRowView,
} from '../utils/historyDetailRows';
import { getRunItemStatusColor } from '../utils/historyDetailDisplay';
import { tryPrettyJson } from '../../../shared/utils/json';

function renderTextBlock(value: string) {
  return (
    <Typography.Paragraph
      copyable
      style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}
    >
      {value}
    </Typography.Paragraph>
  );
}

export function ValidationHistoryDetailRowDrawer({
  open,
  activeTab,
  historyRow,
  resultsRow,
  resultsLatencyClassSaving,
  onChangeResultsLatencyClass,
  onClose,
}: {
  open: boolean;
  activeTab: HistoryDetailTab;
  historyRow: HistoryRowView | null;
  resultsRow: ResultsRowView | null;
  resultsLatencyClassSaving?: boolean;
  onChangeResultsLatencyClass?: (
    nextLatencyClass: 'SINGLE' | 'MULTI' | 'UNCLASSIFIED',
  ) => void;
  onClose: () => void;
}) {
  const row = activeTab === 'results' ? resultsRow : historyRow;
  const item = row?.item;

  return (
    <Drawer
      open={open}
      placement="right"
      width={680}
      title={activeTab === 'results' ? '평가 결과 상세' : '질문 결과 상세'}
      onClose={onClose}
    >
      {item ? (
        <Collapse
          defaultActiveKey={['summary']}
          items={[
            {
              key: 'summary',
              label: '요약',
              children: (
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="상태">
                    {'status' in row ? (
                      <Tag color={getRunItemStatusColor(row.status)}>
                        {row.statusLabel}
                      </Tag>
                    ) : (
                      item.llmEvaluation?.status || '-'
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label="실행 시각">
                    {item.executedAt || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="응답 시간">
                    {'responseTimeText' in row ? row.responseTimeText : (resultsRow?.speedText || '-')}
                  </Descriptions.Item>
                  {activeTab === 'results' && resultsRow ? (
                    <>
                      <Descriptions.Item label="응답 속도 타입">
                        <Select
                          size="small"
                          style={{ minWidth: 160 }}
                          value={resultsRow.latencyClass}
                          options={[
                            { label: '싱글', value: 'SINGLE' },
                            { label: '멀티', value: 'MULTI' },
                            { label: '미분류', value: 'UNCLASSIFIED' },
                          ]}
                          disabled={!onChangeResultsLatencyClass || resultsLatencyClassSaving}
                          loading={resultsLatencyClassSaving}
                          onChange={(value) =>
                            onChangeResultsLatencyClass?.(
                              value as 'SINGLE' | 'MULTI' | 'UNCLASSIFIED',
                            )
                          }
                        />
                      </Descriptions.Item>
                      <Descriptions.Item label="대표 점수">
                        {resultsRow.totalScoreText}
                      </Descriptions.Item>
                      <Descriptions.Item label="의도 충족">
                        {resultsRow.intentScoreText}
                      </Descriptions.Item>
                      <Descriptions.Item label="정확성">
                        {resultsRow.accuracyScoreText}
                      </Descriptions.Item>
                      <Descriptions.Item label="일관성">
                        {resultsRow.consistencyScoreText}
                      </Descriptions.Item>
                      <Descriptions.Item label="안정성">
                        {resultsRow.stabilityScoreText}
                      </Descriptions.Item>
                    </>
                  ) : null}
                  <Descriptions.Item label="오류">
                    {item.error || '-'}
                  </Descriptions.Item>
                </Descriptions>
              ),
            },
            {
              key: 'query',
              label: '질의',
              children: renderTextBlock(String(item.queryText || '')),
            },
            {
              key: 'meta',
              label: '메타 데이터',
              children: (
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label="카테고리">
                      {item.category || '-'}
                    </Descriptions.Item>
                    <Descriptions.Item label="대화 방 번호">
                      {item.conversationRoomIndex}
                    </Descriptions.Item>
                    <Descriptions.Item label="반복 실행 번호">
                      {item.repeatIndex}
                    </Descriptions.Item>
                    <Descriptions.Item label="대화 ID">
                      {item.conversationId || '-'}
                    </Descriptions.Item>
                  </Descriptions>
                </Space>
              ),
            },
            {
              key: 'raw',
              label: '로우 데이터',
              children: renderTextBlock(tryPrettyJson(item.rawJson, '')),
            },
            {
              key: 'expected-result',
              label: '기대결과(스냅샷)',
              children: renderTextBlock(String(item.expectedResult || '')),
            },
            {
              key: 'llm-evaluation',
              label: 'LLM 평가 결과',
              children: renderTextBlock(
                JSON.stringify(
                  {
                    status: item.llmEvaluation?.status,
                    evalModel: item.llmEvaluation?.evalModel,
                    metricScores: item.llmEvaluation?.metricScores,
                    totalScore: item.llmEvaluation?.totalScore,
                    comment: item.llmEvaluation?.comment,
                  },
                  null,
                  2,
                ),
              ),
            },
          ]}
        />
      ) : null}
    </Drawer>
  );
}
