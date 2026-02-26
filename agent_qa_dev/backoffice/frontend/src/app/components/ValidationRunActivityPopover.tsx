import { BellOutlined, FilterOutlined } from '@ant-design/icons';
import { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  Dropdown,
  Empty,
  List,
  Popover,
  Progress,
  Space,
  Tag,
  Typography,
} from 'antd';
import type { MenuProps } from 'antd';

import type { ValidationRunActivityItem } from '../../api/types/validation';
import type { Environment } from '../EnvironmentScope';
import { useValidationRunActivity } from '../hooks/useValidationRunActivity';
import type { RuntimeSecrets } from '../types';

type ActivityFilter = 'ALL' | 'UNREAD';

const ACTIVITY_FILTER_STORAGE_KEY = 'validationRunActivityFilter:v1';

type ValidationRunActivityPopoverProps = {
  environment: Environment;
  runtimeSecrets: RuntimeSecrets;
  onOpenRunWorkspace: (payload: {
    runId: string;
    testSetId?: string | null;
  }) => void;
  onOpenHistoryRunDetail: (runId: string) => void;
};

function toExecutionPercent(item: ValidationRunActivityItem) {
  const total = Math.max(0, Number(item.totalItems || 0));
  if (total <= 0) return 0;
  const done = Math.max(
    0,
    Number(item.doneItems || 0) + Number(item.errorItems || 0),
  );
  return Math.min(100, Math.round((done / total) * 100));
}

function toEvaluationPercent(item: ValidationRunActivityItem) {
  const total = Math.max(0, Number(item.totalItems || 0));
  if (total <= 0) return 0;
  const done = Math.max(0, Number(item.llmDoneItems || 0));
  return Math.min(100, Math.round((done / total) * 100));
}

function getStatusTag(item: ValidationRunActivityItem) {
  const status = String(item.status || '').toUpperCase();
  const evalStatus = String(item.evalStatus || '').toUpperCase();
  if (status === 'RUNNING') {
    return <Tag color="processing">실행 중</Tag>;
  }
  if (status === 'DONE' && evalStatus === 'RUNNING') {
    return <Tag color="blue">평가 중</Tag>;
  }
  if (status === 'FAILED' || evalStatus === 'FAILED') {
    return <Tag color="error">실패</Tag>;
  }
  if (status === 'DONE') {
    return <Tag color="success">완료</Tag>;
  }
  return <Tag>대기</Tag>;
}

function isInProgressActivity(item: ValidationRunActivityItem) {
  const status = String(item.status || '').toUpperCase();
  const evalStatus = String(item.evalStatus || '').toUpperCase();
  return status === 'RUNNING' || (status === 'DONE' && evalStatus === 'RUNNING');
}

function loadPersistedFilter(): ActivityFilter {
  if (typeof window === 'undefined') return 'ALL';
  const value = String(window.localStorage.getItem(ACTIVITY_FILTER_STORAGE_KEY) || '').toUpperCase();
  if (value === 'UNREAD') return 'UNREAD';
  return 'ALL';
}

function getProgressMeta(item: ValidationRunActivityItem): {
  label: string;
  done: number;
  total: number;
  percent: number;
  strokeColor?: string;
} {
  const total = Math.max(0, Number(item.totalItems || 0));
  const executionDone = Math.max(0, Number(item.doneItems || 0) + Number(item.errorItems || 0));
  const evaluationDone = Math.max(0, Number(item.llmDoneItems || 0));
  const status = String(item.status || '').toUpperCase();
  const evalStatus = String(item.evalStatus || '').toUpperCase();

  if (status === 'RUNNING') {
    return {
      label: '실행',
      done: executionDone,
      total,
      percent: toExecutionPercent(item),
    };
  }
  if (status === 'DONE' && evalStatus === 'RUNNING') {
    return {
      label: '평가',
      done: evaluationDone,
      total,
      percent: toEvaluationPercent(item),
      strokeColor: '#8a7cff',
    };
  }
  if (status === 'FAILED' || evalStatus === 'FAILED') {
    const failedPercent = total > 0 ? Math.min(100, Math.round((executionDone / total) * 100)) : 0;
    return {
      label: '실패',
      done: executionDone,
      total,
      percent: failedPercent,
      strokeColor: '#ff4d4f',
    };
  }
  const done = total > 0 ? total : executionDone;
  return {
    label: '완료',
    done,
    total: total > 0 ? total : done,
    percent: 100,
    strokeColor: '#52c41a',
  };
}

export function ValidationRunActivityPopover({
  environment,
  runtimeSecrets,
  onOpenRunWorkspace,
  onOpenHistoryRunDetail,
}: ValidationRunActivityPopoverProps) {
  const {
    open,
    setOpen,
    loading,
    items,
    unreadCount,
    markRunRead,
    markAllRead,
    hasActorKey,
  } = useValidationRunActivity({
    environment,
    runtimeSecrets,
    pollingMs: 5000,
  });
  const [filterMode, setFilterMode] = useState<ActivityFilter>(() => loadPersistedFilter());

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(ACTIVITY_FILTER_STORAGE_KEY, filterMode);
  }, [filterMode]);

  const filterItems = useMemo(
    () =>
      filterMode === 'UNREAD'
        ? items.filter((item) => !item.isRead)
        : items,
    [filterMode, items],
  );

  const filterMenu = useMemo<MenuProps>(
    () => ({
      selectable: true,
      selectedKeys: [filterMode],
      items: [
        { key: 'ALL', label: '모든 알림' },
        { key: 'UNREAD', label: '읽지 않음' },
      ],
      onClick: ({ key }) => {
        setFilterMode(key === 'UNREAD' ? 'UNREAD' : 'ALL');
      },
    }),
    [filterMode],
  );

  const handleOpenRun = async (item: ValidationRunActivityItem) => {
    try {
      await markRunRead(item.runId);
    } catch (error) {
      console.error(error);
    }
    if (!isInProgressActivity(item)) {
      onOpenHistoryRunDetail(item.runId);
    } else {
      onOpenRunWorkspace({
        runId: item.runId,
        testSetId: item.testSetId ?? undefined,
      });
    }
    setOpen(false);
  };

  const content = (
    <div className="validation-run-activity-popover">
      <div className="validation-run-activity-popover-header">
        <Typography.Text strong>알림</Typography.Text>
        <Space size={4}>
          <Button
            size="small"
            type="link"
            disabled={!hasActorKey || unreadCount <= 0}
            onClick={() => {
              void markAllRead();
            }}
          >
            모두 읽음
          </Button>
          <Dropdown menu={filterMenu} trigger={['click']}>
            <Button
              size="small"
              type="text"
              icon={<FilterOutlined />}
              aria-label="알림 필터"
            />
          </Dropdown>
        </Space>
      </div>

      {!hasActorKey ? (
        <Typography.Text type="secondary">
          로그인하면 모든 알림을 확인할 수 있어요.
        </Typography.Text>
      ) : null}

      {hasActorKey && filterItems.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={items.length === 0 ? '알림이 없습니다.' : '읽지 않은 알림이 없습니다.'}
        />
      ) : null}

      {hasActorKey && filterItems.length > 0 ? (
        <List
          loading={loading}
          size="small"
          dataSource={filterItems}
          className="validation-run-activity-list"
          renderItem={(item) => (
            <List.Item className={item.isRead ? '' : 'is-unread'}>
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space
                  size={8}
                  style={{ width: '100%', justifyContent: 'space-between' }}
                >
                  <Button
                    type="link"
                    className="validation-run-activity-run-link"
                    onClick={() => {
                      void handleOpenRun(item);
                    }}
                  >
                    {item.runName || item.runId}
                  </Button>
                  {getStatusTag(item)}
                </Space>
                {(() => {
                  const progress = getProgressMeta(item);
                  return (
                    <div>
                      <Typography.Text type="secondary">
                        {progress.label} {progress.done} / {progress.total}
                      </Typography.Text>
                      <Progress
                        percent={progress.percent}
                        size="small"
                        showInfo={false}
                        strokeColor={progress.strokeColor}
                      />
                    </div>
                  );
                })()}
              </Space>
            </List.Item>
          )}
        />
      ) : null}
    </div>
  );

  return (
    <Popover
      trigger="click"
      placement="bottomRight"
      open={open}
      onOpenChange={setOpen}
      content={content}
      overlayClassName="validation-run-activity-popover-overlay"
    >
      <Badge count={unreadCount} size="small">
        <Button
          type="default"
          size="middle"
          icon={<BellOutlined />}
          aria-label="검증 진행 알림"
        />
      </Badge>
    </Popover>
  );
}
