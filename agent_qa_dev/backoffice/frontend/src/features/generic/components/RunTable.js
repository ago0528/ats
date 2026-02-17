import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { CloseCircleOutlined } from '@ant-design/icons';
import { Card, Tag, Tooltip, Typography } from 'antd';
import { Table } from 'antd';
const withOptional = (value, fallback = '-') => String(value ?? fallback);
function statusToTag(status) {
    const normalized = status.toLowerCase();
    if (normalized.includes('pass'))
        return _jsx(Tag, { color: "success", children: "PASS" });
    if (normalized.includes('fail'))
        return _jsx(Tag, { color: "error", children: "FAIL" });
    if (normalized.includes('skip'))
        return _jsx(Tag, { color: "warning", children: "SKIP" });
    return _jsx(Tag, { color: "default", children: status || '-' });
}
function responseTimeText(value) {
    if (value === null || value === undefined)
        return '-';
    return `${value.toFixed(3)}s`;
}
function detailLabel(label, value, fallback = '-') {
    return `${label}: ${withOptional(value, fallback)}`;
}
export const RUN_TABLE_COLUMNS = [
    {
        title: '질의 ID',
        dataIndex: 'queryId',
        sorter: (a, b) => String(a.queryId ?? '').localeCompare(String(b.queryId ?? '')),
    },
    {
        title: '질의',
        dataIndex: 'query',
        sorter: (a, b) => String(a.query ?? '').localeCompare(String(b.query ?? '')),
        ellipsis: true,
        render: (value) => (_jsx(Tooltip, { title: value, children: _jsx(Typography.Text, { ellipsis: { tooltip: value }, children: withOptional(value) }) })),
    },
    {
        title: '응답',
        dataIndex: 'responseText',
        width: 360,
        render: (value) => (_jsx(Typography.Text, { code: true, style: { whiteSpace: 'pre-wrap', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }, children: withOptional(value, '-') || '-' })),
    },
    {
        title: '응답시간',
        dataIndex: 'responseTimeSec',
        width: 110,
        sorter: (a, b) => Number(a.responseTimeSec ?? 0) - Number(b.responseTimeSec ?? 0),
        render: (value) => responseTimeText(value),
    },
    {
        title: '로직 검증결과',
        dataIndex: 'logicResult',
        sorter: (a, b) => String(a.logicResult ?? '').localeCompare(String(b.logicResult ?? '')),
        render: (value) => statusToTag(withOptional(value)),
    },
    {
        title: 'LLM 상태',
        dataIndex: 'llmEvalStatus',
        sorter: (a, b) => String(a.llmEvalStatus ?? '').localeCompare(String(b.llmEvalStatus ?? '')),
        render: (value) => statusToTag(withOptional(value, '')),
    },
    {
        title: '오류',
        dataIndex: 'error',
        width: 220,
        ellipsis: true,
        render: (value) => {
            if (!value) {
                return _jsx(Typography.Text, { type: "secondary", children: "-" });
            }
            return (_jsx(Tooltip, { title: value, children: _jsxs(Typography.Text, { type: "danger", style: { whiteSpace: 'pre-wrap' }, children: [_jsx(CloseCircleOutlined, {}), " ", withOptional(value)] }) }));
        },
    },
];
export function RunTable({ rows }) {
    const rowCount = rows.length;
    const hasRows = rows.length > 0;
    return (_jsx(Table, { rowKey: "id", className: "run-table", pagination: { pageSize: 20 }, columns: RUN_TABLE_COLUMNS, dataSource: rows, rowClassName: (row) => (String(row.error || '').trim() ? 'ant-table-row-error' : ''), scroll: { x: 1200, y: 420 }, locale: {
            emptyText: '현재 결과 데이터가 없습니다. 실행 생성 또는 결과 업데이트를 해주세요.',
        }, onRow: (row) => ({
            style: { cursor: 'default' },
            'data-row-index': row.id,
        }), title: () => (hasRows ? `총 ${rowCount}건` : '결과 데이터'), expandable: {
            expandedRowRender: (row) => (_jsxs(Card, { size: "small", className: "run-row-details", children: [_jsx(Typography.Paragraph, { className: "run-row-details-title", style: { marginBottom: 10 }, children: detailLabel('실행 프로세스', row.executionProcess, '없음') }), _jsx(Typography.Paragraph, { copyable: true, style: { whiteSpace: 'pre-wrap', marginBottom: 0 }, children: withOptional(row.rawJson, '').trim() || '-' }), _jsxs(Typography.Text, { type: "secondary", className: "run-row-meta", children: [detailLabel('LLM 평가기준', row.llmCriteria), ' / ', detailLabel('검증 필드', row.fieldPath), ' / ', detailLabel('기대값', row.expectedValue)] })] })),
            rowExpandable: () => true,
        } }));
}
