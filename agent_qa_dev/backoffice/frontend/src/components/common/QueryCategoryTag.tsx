import { Tag } from 'antd';

export function QueryCategoryTag({ category }: { category?: string | null }) {
  const value = String(category || 'Happy path');
  if (value === 'Happy path') return <Tag color="success">{value}</Tag>;
  if (value === 'Edge case') return <Tag color="warning">{value}</Tag>;
  if (value === 'Adversarial input') return <Tag color="error">{value}</Tag>;
  return <Tag>{value}</Tag>;
}
