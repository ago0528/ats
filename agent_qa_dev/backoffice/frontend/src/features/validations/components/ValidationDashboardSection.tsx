import { Button, Card, Empty, Select, Space, Typography } from 'antd';

import type { ValidationTestSet } from '../../../api/types/validation';

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
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space>
        <Select
          placeholder="테스트 세트 선택"
          value={dashboardTestSetId}
          options={testSets.map((testSet) => ({ label: `${testSet.name} (${testSet.itemCount})`, value: testSet.id }))}
          onChange={(value) => setDashboardTestSetId(value)}
          style={{ width: 260 }}
        />
        <Button onClick={handleLoadDashboard}>조회</Button>
      </Space>
      {dashboardData ? (
        <Card size="small">
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
            {JSON.stringify(dashboardData, null, 2)}
          </Typography.Paragraph>
        </Card>
      ) : (
        <Empty description="조회할 테스트 세트를 선택해 주세요." />
      )}
    </Space>
  );
}
