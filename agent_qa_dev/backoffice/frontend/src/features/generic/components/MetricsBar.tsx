import { Card, Col, Row, Statistic } from 'antd';

type Props = {
  total: number;
  passFail: string;
  llmDone: number;
  errors: number;
};

export function MetricsBar({ total, passFail, llmDone, errors }: Props) {
  return (
    <Row gutter={[12, 12]} className="metric-grid">
      <Col xs={24} sm={12} lg={6}>
        <Card>
          <Statistic title="총 질의 수" value={total} />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card>
          <Statistic title="로직 PASS / FAIL" value={passFail} />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card>
          <Statistic title="LLM 평가 완료" value={llmDone} />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card>
          <Statistic title="오류 건수" value={errors} />
        </Card>
      </Col>
    </Row>
  );
}
