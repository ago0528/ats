import { Button, Card, Empty, Select, Space, Typography } from 'antd';

import type { QueryGroup } from '../../../api/types/validation';

export function ValidationDashboardSection({
  groups,
  dashboardGroupId,
  setDashboardGroupId,
  handleLoadDashboard,
  dashboardData,
}: {
  groups: QueryGroup[];
  dashboardGroupId: string;
  setDashboardGroupId: (value: string) => void;
  handleLoadDashboard: () => void;
  dashboardData: Record<string, unknown> | null;
}) {
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space>
        <Select
          placeholder="그룹 선택"
          value={dashboardGroupId}
          options={groups.map((group) => ({ label: group.groupName, value: group.id }))}
          onChange={(value) => setDashboardGroupId(value)}
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
        <Empty description="조회할 그룹을 선택해 주세요." />
      )}
    </Space>
  );
}
