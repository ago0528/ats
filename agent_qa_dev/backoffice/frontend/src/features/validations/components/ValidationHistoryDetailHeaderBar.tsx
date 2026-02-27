import { Button, Dropdown, Space, Tag, Typography } from 'antd';
import type { MenuProps } from 'antd';
import { EllipsisOutlined } from '@ant-design/icons';

import { buildValidationRunExportUrl } from '../../../api/validation';
import type { ValidationRun } from '../../../api/types/validation';
import {
  getRunStatusColor,
  getRunStatusLabel,
} from '../utils/historyDetailDisplay';
import { getRunDisplayName } from '../utils/runDisplay';

export function ValidationHistoryDetailHeaderBar({
  currentRun,
  onOpenInRunWorkspace,
  onOpenUpdateRun,
  onOpenExpectedBulkUpdate,
  onDeleteRun,
  canEditCurrentRun,
  canDeleteCurrentRun,
  canOpenExpectedBulkUpdate,
  hasItems,
}: {
  currentRun: ValidationRun | null;
  onOpenInRunWorkspace?: (payload: { runId: string; testSetId?: string | null }) => void;
  onOpenUpdateRun?: () => void;
  onOpenExpectedBulkUpdate?: () => void;
  onDeleteRun?: () => void;
  canEditCurrentRun: boolean;
  canDeleteCurrentRun: boolean;
  canOpenExpectedBulkUpdate: boolean;
  hasItems: boolean;
}) {
  const isDisabled = !currentRun;
  const isDownloadDisabled = !currentRun || !hasItems;
  const runName = currentRun ? getRunDisplayName(currentRun) : '-';
  const runStatusLabel = getRunStatusLabel(currentRun?.status);
  const runStatusColor = getRunStatusColor(currentRun?.status);

  const menuItems: MenuProps['items'] = [
    {
      key: 'download-excel',
      label: '엑셀 다운로드',
      disabled: isDownloadDisabled,
    },
    {
      key: 'download-debug',
      label: '디버그 다운로드',
      disabled: isDownloadDisabled,
    },
    {
      key: 'expected-bulk-update',
      label: '기대결과 일괄 업데이트',
      disabled: isDisabled || !canOpenExpectedBulkUpdate,
    },
    {
      type: 'divider',
    },
    {
      key: 'update-run',
      label: 'Run 수정',
      disabled: isDisabled || !canEditCurrentRun,
    },
    {
      key: 'delete-run',
      label: 'Run 삭제',
      disabled: isDisabled || !canDeleteCurrentRun,
      danger: true,
    },
  ];

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (!currentRun) return;
    if (key === 'download-excel') {
      window.location.href = buildValidationRunExportUrl(currentRun.id);
      return;
    }
    if (key === 'download-debug') {
      window.location.href = buildValidationRunExportUrl(currentRun.id, {
        includeDebug: true,
      });
      return;
    }
    if (key === 'update-run') {
      onOpenUpdateRun?.();
      return;
    }
    if (key === 'expected-bulk-update') {
      onOpenExpectedBulkUpdate?.();
      return;
    }
    if (key === 'delete-run') {
      onDeleteRun?.();
    }
  };

  return (
    <div className="validation-history-detail-header-bar">
      <div className="validation-history-detail-header-row">
        <div className="validation-history-detail-run-meta">
          <Typography.Title level={5} style={{ margin: 0 }}>
            {runName}
          </Typography.Title>
          <Tag color={runStatusColor}>{runStatusLabel}</Tag>
        </div>
        <Space>
          <Button
            type="primary"
            disabled={isDisabled}
            onClick={() => {
              if (!currentRun) return;
              onOpenInRunWorkspace?.({
                runId: currentRun.id,
                testSetId: currentRun.testSetId ?? undefined,
              });
            }}
          >
            검증 실행에서 이 Run 열기
          </Button>
          <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }} trigger={['click']}>
            <Button icon={<EllipsisOutlined />} />
          </Dropdown>
        </Space>
      </div>
    </div>
  );
}
