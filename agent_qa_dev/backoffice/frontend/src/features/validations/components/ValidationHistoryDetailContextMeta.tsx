import { Descriptions, Tooltip, Typography } from 'antd';

type ContextMetaItem = {
  key: string;
  label: string;
  value: string;
};

function renderValue(value: string) {
  return (
    <Tooltip title={value}>
      <Typography.Text ellipsis style={{ display: 'block', maxWidth: '100%' }}>
        {value}
      </Typography.Text>
    </Tooltip>
  );
}

export function ValidationHistoryDetailContextMeta({
  items,
}: {
  items: ContextMetaItem[];
}) {
  return (
    <div className="validation-history-detail-context-meta">
      <Descriptions size="small" column={{ xs: 1, sm: 2, md: 4 }}>
        {items.map((item) => (
          <Descriptions.Item key={item.key} label={item.label}>
            {renderValue(item.value)}
          </Descriptions.Item>
        ))}
      </Descriptions>
    </div>
  );
}

