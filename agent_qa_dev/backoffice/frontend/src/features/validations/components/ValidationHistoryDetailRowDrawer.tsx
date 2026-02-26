import {
  Card,
  Collapse,
  Descriptions,
  Drawer,
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
  onClose,
}: {
  open: boolean;
  activeTab: HistoryDetailTab;
  historyRow: HistoryRowView | null;
  resultsRow: ResultsRowView | null;
  onClose: () => void;
}) {
  const row = activeTab === 'results' ? resultsRow : historyRow;
  const item = row?.item;

  return (
    <Drawer
      open={open}
      placement="right"
      width={680}
      title={activeTab === 'results' ? '평가 결과 상세' : '검증 이력 상세'}
      onClose={onClose}
    >
      {item ? (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Card size="small" title="요약">
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="상태">
                {'status' in row ? (
                  <Tag color={getRunItemStatusColor(row.status)}>
                    {row.statusLabel}
                  </Tag>
                ) : (
                  '-'
                )}
              </Descriptions.Item>
              <Descriptions.Item label="실행시각">
                {item.executedAt || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="총 응답시간">
                {'responseTimeText' in row ? row.responseTimeText : '-'}
              </Descriptions.Item>
              {activeTab === 'results' && resultsRow ? (
                <>
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
            </Descriptions>
          </Card>

          <Card size="small" title="요청(Request) 전문">
            {renderTextBlock(String(item.queryText || ''))}
          </Card>

          <Card size="small" title="응답(Response) 전문">
            {renderTextBlock(String(item.rawResponse || ''))}
          </Card>

          <Card size="small" title="메타 데이터">
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="Room/Repeat">
                {item.conversationRoomIndex}/{item.repeatIndex}
              </Descriptions.Item>
              <Descriptions.Item label="Conversation ID">
                {item.conversationId || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="기대결과">
                {item.expectedResult || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="카테고리">
                {item.category || '-'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card size="small" title="오류 상세">
            {renderTextBlock(String(item.error || ''))}
          </Card>

          <Collapse
            items={[
              {
                key: 'internal-code',
                label: '로우 데이터',
                children: (
                  <Space
                    direction="vertical"
                    size={8}
                    style={{ width: '100%' }}
                  >
                    <Card size="small" title="JSON">
                      {renderTextBlock(tryPrettyJson(item.rawJson, ''))}
                    </Card>
                    <Card size="small" title="기대 결과">
                      {renderTextBlock(
                        typeof item.appliedCriteria === 'string'
                          ? tryPrettyJson(item.appliedCriteria, '')
                          : JSON.stringify(item.appliedCriteria || {}, null, 2),
                      )}
                    </Card>
                    <Card size="small" title="LLM 평가 결과">
                      {renderTextBlock(
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
                      )}
                    </Card>
                  </Space>
                ),
              },
            ]}
          />
        </Space>
      ) : null}
    </Drawer>
  );
}
