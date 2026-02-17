import { Progress, Space, Typography } from 'antd';

export function RunProgressBar({
  total,
  done,
  errors,
}: {
  total: number;
  done: number;
  errors: number;
}) {
  const count = Math.max(0, Number(total || 0));
  const finished = Math.max(0, Number(done || 0));
  const percent = count > 0 ? Math.round((finished / count) * 100) : 0;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={4}>
      <Progress percent={percent} status={errors > 0 ? 'exception' : 'active'} />
      <Typography.Text type="secondary">
        총 {count}건 / 완료 {finished}건 / 오류 {errors}건
      </Typography.Text>
    </Space>
  );
}
