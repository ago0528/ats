import { Button, Dropdown, Space, Tooltip, Typography } from 'antd';
import type { MenuProps } from 'antd';
import { EllipsisOutlined, ExportOutlined, LinkOutlined } from '@ant-design/icons';

import { buildValidationRunExportUrl } from '../../../api/validation';
import type { ValidationRun } from '../../../api/types/validation';
import { getRunDisplayName } from '../utils/runDisplay';

export function ValidationHistoryDetailHeaderBar({
  currentRun,
  summaryItems,
  onOpenInRunWorkspace,
  onCopyShareLink,
  onOpenUpdateRun,
  onOpenExpectedBulkUpdate,
  onDeleteRun,
  canEditCurrentRun,
  canDeleteCurrentRun,
  canOpenExpectedBulkUpdate,
  hasItems,
}: {
  currentRun: ValidationRun | null;
  summaryItems: Array<{ key: string; label: string; value: string; valueTooltip?: string }>;
  onOpenInRunWorkspace?: (payload: { runId: string; testSetId?: string | null }) => void;
  onCopyShareLink?: () => void;
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
        </div>
        <Space>
          <Tooltip title="검증 실행 화면으로 이동합니다.">
            <Button
              type="primary"
              icon={<ExportOutlined />}
              disabled={isDisabled}
              onClick={() => {
                if (!currentRun) return;
                onOpenInRunWorkspace?.({
                  runId: currentRun.id,
                  testSetId: currentRun.testSetId ?? undefined,
                });
              }}
            >
              검증하기
            </Button>
          </Tooltip>
          <Tooltip title="현재 탭/필터/페이지 상태 링크를 복사합니다.">
            <Button
              icon={<LinkOutlined />}
              disabled={isDisabled}
              onClick={() => onCopyShareLink?.()}
            >
              링크 복사
            </Button>
          </Tooltip>
          <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }} trigger={['click']}>
            <Button icon={<EllipsisOutlined />} />
          </Dropdown>
        </Space>
      </div>
      <div className="validation-history-detail-summary-line">
        {summaryItems.map((item) => (
          <Tooltip key={item.key} title={item.valueTooltip || item.value}>
            <div className="validation-history-detail-summary-item">
              <Typography.Text type="secondary" className="validation-history-detail-summary-label">
                {item.label}
              </Typography.Text>
              <Typography.Text className="validation-history-detail-summary-value">
                {item.value}
              </Typography.Text>
            </div>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
