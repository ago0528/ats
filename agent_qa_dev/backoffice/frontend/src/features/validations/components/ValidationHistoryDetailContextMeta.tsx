import { Tooltip, Typography } from 'antd';

type ContextMetaItem = {
  key: string;
  label: string;
  value: string;
  valueTooltip?: string;
};

function renderValue(value: string, tooltip?: string) {
  const tooltipText = tooltip || value;
  return (
    <Tooltip title={tooltipText}>
      <Typography.Text
        className="validation-history-detail-context-meta-value"
        ellipsis
      >
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
      {items.map((item) => (
        <div key={item.key} className="validation-history-detail-context-meta-slot">
          <div className="validation-history-detail-context-meta-item">
            <Typography.Text
              type="secondary"
              className="validation-history-detail-context-meta-label"
            >
              {item.label}
            </Typography.Text>
            {renderValue(item.value, item.valueTooltip)}
          </div>
        </div>
      ))}
    </div>
  );
}
