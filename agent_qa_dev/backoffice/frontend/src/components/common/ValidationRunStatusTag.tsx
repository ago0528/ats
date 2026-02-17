import { Tag } from 'antd';

export function ValidationRunStatusTag({ status }: { status?: string | null }) {
  const normalized = String(status || '').toUpperCase();
  if (normalized === 'DONE') return <Tag color="success">DONE</Tag>;
  if (normalized === 'RUNNING') return <Tag color="processing">RUNNING</Tag>;
  if (normalized === 'FAILED') return <Tag color="error">FAILED</Tag>;
  if (normalized === 'PENDING') return <Tag>PENDING</Tag>;
  return <Tag>{status || '-'}</Tag>;
}
