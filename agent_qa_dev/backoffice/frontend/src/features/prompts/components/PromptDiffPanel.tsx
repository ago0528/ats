import { Col, Input, Row, Tag, Typography } from 'antd';

type Props = {
  before: string;
  after: string;
  onChangeAfter?: (value: string) => void;
};

function lengthDelta(before: string, after: string) {
  const delta = after.length - before.length;
  if (delta === 0) return '0';
  if (delta > 0) return `+${delta}`;
  return `${delta}`;
}

export function PromptDiffPanel({ before, after, onChangeAfter }: Props) {
  return (
    <Row gutter={16}>
      <Col span={12}>
        <Typography.Title level={5}>변경 전</Typography.Title>
        <Input.TextArea
          value={before}
          readOnly
          autoSize={{ minRows: 14 }}
          style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
        />
      </Col>
      <Col span={12}>
        <Typography.Title level={5}>현재</Typography.Title>
        <Tag style={{ marginBottom: 8 }} color={lengthDelta(before, after).startsWith('+') ? 'success' : 'default'}>
          길이 차이: {lengthDelta(before, after)}
        </Tag>
        {onChangeAfter ? (
          <Input.TextArea
            value={after}
            onChange={(e) => onChangeAfter(e.target.value)}
            autoSize={{ minRows: 14 }}
            style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
          />
        ) : (
          <Input.TextArea
            value={after}
            readOnly
            autoSize={{ minRows: 14 }}
            style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
          />
        )}
      </Col>
    </Row>
  );
}
