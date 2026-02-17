import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Col, Input, Row, Tag, Typography } from 'antd';
function lengthDelta(before, after) {
    const delta = after.length - before.length;
    if (delta === 0)
        return '0';
    if (delta > 0)
        return `+${delta}`;
    return `${delta}`;
}
export function PromptDiffPanel({ before, after, onChangeAfter }) {
    return (_jsxs(Row, { gutter: 16, children: [_jsxs(Col, { span: 12, children: [_jsx(Typography.Title, { level: 5, children: "\uBCC0\uACBD \uC804" }), _jsx(Input.TextArea, { value: before, readOnly: true, autoSize: { minRows: 14 }, style: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' } })] }), _jsxs(Col, { span: 12, children: [_jsx(Typography.Title, { level: 5, children: "\uD604\uC7AC" }), _jsxs(Tag, { style: { marginBottom: 8 }, color: lengthDelta(before, after).startsWith('+') ? 'success' : 'default', children: ["\uAE38\uC774 \uCC28\uC774: ", lengthDelta(before, after)] }), onChangeAfter ? (_jsx(Input.TextArea, { value: after, onChange: (e) => onChangeAfter(e.target.value), autoSize: { minRows: 14 }, style: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' } })) : (_jsx(Input.TextArea, { value: after, readOnly: true, autoSize: { minRows: 14 }, style: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' } }))] })] }));
}
