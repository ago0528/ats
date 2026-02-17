import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Card, Col, Row, Statistic } from 'antd';
export function MetricsBar({ total, passFail, llmDone, errors }) {
    return (_jsxs(Row, { gutter: [12, 12], className: "metric-grid", children: [_jsx(Col, { xs: 24, sm: 12, lg: 6, children: _jsx(Card, { children: _jsx(Statistic, { title: "\uCD1D \uC9C8\uC758 \uC218", value: total }) }) }), _jsx(Col, { xs: 24, sm: 12, lg: 6, children: _jsx(Card, { children: _jsx(Statistic, { title: "\uB85C\uC9C1 PASS / FAIL", value: passFail }) }) }), _jsx(Col, { xs: 24, sm: 12, lg: 6, children: _jsx(Card, { children: _jsx(Statistic, { title: "LLM \uD3C9\uAC00 \uC644\uB8CC", value: llmDone }) }) }), _jsx(Col, { xs: 24, sm: 12, lg: 6, children: _jsx(Card, { children: _jsx(Statistic, { title: "\uC624\uB958 \uAC74\uC218", value: errors }) }) })] }));
}
