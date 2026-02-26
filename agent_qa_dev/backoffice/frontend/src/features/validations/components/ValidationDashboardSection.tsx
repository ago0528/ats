import { Button, Card, Col, Empty, Row, Select, Space, Statistic, Table, Tag, Typography } from 'antd';

import type {
  ValidationDashboardDistributions,
  ValidationDashboardScoring,
  ValidationTestSet,
} from '../../../api/types/validation';

type DashboardResponse = {
  scoring?: ValidationDashboardScoring;
  distributions?: ValidationDashboardDistributions;
  failurePatterns?: Array<{ category: string; count: number }>;
};

const formatScore = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toFixed(2);
};

const formatSec = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Number(value).toFixed(3)}초`;
};

const formatPercent = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${(Number(value) * 100).toFixed(2)}%`;
};

const toBucketRows = (buckets?: Record<string, number>) => {
  const source = buckets || {};
  return ['5', '4', '3', '2', '1', '0'].map((score) => ({
    key: score,
    score,
    count: Number(source[score] || 0),
  }));
};

const BUCKET_COLUMNS = [
  { key: 'score', title: '점수', dataIndex: 'score', width: 90 },
  { key: 'count', title: '건수', dataIndex: 'count', width: 120 },
];

export function ValidationDashboardSection({
  testSets,
  dashboardTestSetId,
  setDashboardTestSetId,
  handleLoadDashboard,
  dashboardData,
}: {
  testSets: ValidationTestSet[];
  dashboardTestSetId: string;
  setDashboardTestSetId: (value: string) => void;
  handleLoadDashboard: () => void;
  dashboardData: Record<string, unknown> | null;
}) {
  const payload = (dashboardData || {}) as DashboardResponse;
  const scoring = payload.scoring;
  const distributions = payload.distributions;
  const accuracyFallbackCount = Number(scoring?.accuracy?.accuracyFallbackCount || 0);
  const accuracySampleCount = Number(scoring?.accuracy?.sampleCount || 0);
  const accuracyFallbackRate = (
    scoring?.accuracy?.accuracyFallbackRate !== undefined
      ? Number(scoring?.accuracy?.accuracyFallbackRate || 0)
      : (accuracySampleCount > 0 ? accuracyFallbackCount / accuracySampleCount : 0)
  );
  const latencyUnclassifiedCount = Number(scoring?.latencyUnclassifiedCount || 0);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Space>
        <Select
          placeholder="테스트 세트 선택"
          value={dashboardTestSetId}
          options={testSets.map((testSet) => ({ label: `${testSet.name} (${testSet.itemCount})`, value: testSet.id }))}
          onChange={(value) => setDashboardTestSetId(value)}
          style={{ width: 280 }}
        />
        <Button onClick={handleLoadDashboard}>조회</Button>
      </Space>

      {!dashboardData ? (
        <Empty description="조회할 테스트 세트를 선택해 주세요." />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Card size="small" title="핵심 지표">
            <Row gutter={[12, 12]}>
              <Col xs={24} sm={12} md={8} lg={4}>
                <Statistic title="의도 충족" value={formatScore(scoring?.intent?.score)} />
                <Typography.Text type="secondary">표본 {scoring?.intent?.sampleCount || 0}건</Typography.Text>
              </Col>
              <Col xs={24} sm={12} md={8} lg={4}>
                <Statistic title="정확성" value={formatScore(scoring?.accuracy?.score)} />
                <Typography.Text type="secondary">표본 {scoring?.accuracy?.sampleCount || 0}건</Typography.Text>
                {(scoring?.accuracy?.legacyFallbackCount || 0) > 0 ? (
                  <div>
                    <Tag color="warning">legacy 폴백 {scoring?.accuracy?.legacyFallbackCount}건</Tag>
                  </div>
                ) : null}
                {accuracyFallbackCount > 0 ? (
                  <div>
                    <Tag color="gold">fallback {accuracyFallbackCount}건 ({formatPercent(accuracyFallbackRate)})</Tag>
                  </div>
                ) : null}
              </Col>
              <Col xs={24} sm={12} md={8} lg={4}>
                <Statistic
                  title="일관성"
                  value={
                    scoring?.consistency?.status === 'PENDING'
                      ? '보류'
                      : formatScore(scoring?.consistency?.score)
                  }
                />
                <Typography.Text type="secondary">
                  대상 질의 {scoring?.consistency?.eligibleQueryCount || 0}개
                </Typography.Text>
              </Col>
              <Col xs={24} sm={12} md={8} lg={4}>
                <Statistic title="응답 속도 SINGLE(참고)" value={formatSec(scoring?.latencySingle?.avgSec)} />
                <Typography.Text type="secondary">
                  avg {formatSec(scoring?.latencySingle?.avgSec)} / p50 {formatSec(scoring?.latencySingle?.p50Sec)} / p90 {formatSec(scoring?.latencySingle?.p90Sec)}
                </Typography.Text>
                <Typography.Text type="secondary">표본 {scoring?.latencySingle?.count || 0}건</Typography.Text>
                <div><Tag color="default">점수화 제외</Tag></div>
              </Col>
              <Col xs={24} sm={12} md={8} lg={4}>
                <Statistic title="응답 속도 MULTI(참고)" value={formatSec(scoring?.latencyMulti?.avgSec)} />
                <Typography.Text type="secondary">
                  avg {formatSec(scoring?.latencyMulti?.avgSec)} / p50 {formatSec(scoring?.latencyMulti?.p50Sec)} / p90 {formatSec(scoring?.latencyMulti?.p90Sec)}
                </Typography.Text>
                <Typography.Text type="secondary">표본 {scoring?.latencyMulti?.count || 0}건</Typography.Text>
                <div><Tag color="default">점수화 제외</Tag></div>
              </Col>
              <Col xs={24} sm={12} md={8} lg={4}>
                <Statistic title="안정성" value={formatScore(scoring?.stability?.score)} />
                <Typography.Text type="secondary">
                  에러율 {formatPercent(scoring?.stability?.errorRate)} / 빈응답율 {formatPercent(scoring?.stability?.emptyRate)}
                </Typography.Text>
              </Col>
            </Row>
            {latencyUnclassifiedCount > 0 ? (
              <div style={{ marginTop: 8 }}>
                <Tag color="warning">latencyClass 미분류 {latencyUnclassifiedCount}건</Tag>
              </div>
            ) : null}
          </Card>

          <Card size="small" title="점수 분포">
            <Table
              size="small"
              pagination={false}
              columns={BUCKET_COLUMNS}
              dataSource={toBucketRows(distributions?.scoreBuckets)}
              rowKey="key"
            />
          </Card>

          <Card size="small" title="실패 패턴 Top">
            <Table
              size="small"
              pagination={false}
              rowKey={(row) => `${row.category}-${row.count}`}
              columns={[
                { key: 'category', title: '카테고리', dataIndex: 'category', width: 220 },
                { key: 'count', title: '건수', dataIndex: 'count', width: 120 },
              ]}
              dataSource={Array.isArray(payload.failurePatterns) ? payload.failurePatterns : []}
            />
          </Card>
        </Space>
      )}
    </Space>
  );
}
