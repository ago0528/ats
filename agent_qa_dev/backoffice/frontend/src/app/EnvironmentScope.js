import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Select, Space, Typography } from 'antd';
export const ENV_OPTIONS = [
    { label: 'DV 환경', value: 'dev' },
    { label: 'QA 환경', value: 'st2' },
    { label: 'STG 환경', value: 'st' },
    { label: 'PR 환경', value: 'pr' },
];
export function EnvironmentScope({ value, onChange }) {
    return (_jsxs(Space, { children: [_jsx(Typography.Text, { strong: true, children: "\uD658\uACBD" }), _jsx(Select, { options: ENV_OPTIONS, value: value, style: { width: 160 }, onChange: (v) => onChange(v) })] }));
}
