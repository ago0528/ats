import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { Alert, Divider, Button, Card, Col, Empty, Input, InputNumber, Select, Radio, Row, Switch, Space, Spin, Steps, Tag, Tooltip, Typography, Upload, message, } from 'antd';
import { CheckCircleOutlined, FileExcelOutlined, InfoCircleOutlined, LoadingOutlined, RocketOutlined, } from '@ant-design/icons';
import { api } from '../../api/client';
import { MetricsBar } from './components/MetricsBar';
import { RunTable } from './components/RunTable';
export const RUN_CREATION_LABEL = '검증 실행 생성';
export const RUN_CREATION_HELP_TOOLTIP = 'CSV 업로드 또는 단일 질의를 등록한 뒤 1단계(질의 실행) -> 2단계(LLM 평가) 순서로 진행하세요.';
const RUN_STATUS_TEXT = {
    PENDING: '준비',
    RUNNING: '진행중',
    DONE: '완료',
    FAILED: '실패',
};
function statusColor(status) {
    if (status === 'PENDING')
        return 'default';
    if (status === 'RUNNING')
        return 'processing';
    if (status === 'DONE')
        return 'success';
    return 'error';
}
function clampNumber(input, fallback) {
    const normalized = Number(input);
    if (!Number.isFinite(normalized))
        return fallback;
    if (normalized < 1)
        return 1;
    return Math.trunc(normalized);
}
export function GenericRunPage({ environment, tokens }) {
    const [mode, setMode] = useState('upload');
    const [files, setFiles] = useState([]);
    const [rows, setRows] = useState([]);
    const [run, setRun] = useState(null);
    const [singleQuery, setSingleQuery] = useState('');
    const [singleLlmCriteria, setSingleLlmCriteria] = useState('');
    const [singleField, setSingleField] = useState('');
    const [singleExpected, setSingleExpected] = useState('');
    const [openaiKey, setOpenaiKey] = useState('');
    const [openaiModel, setOpenaiModel] = useState('gpt-5.2');
    const [maxParallel, setMaxParallel] = useState(3);
    const [maxChars, setMaxChars] = useState(15000);
    const [contextJson, setContextJson] = useState('');
    const [targetAssistant, setTargetAssistant] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [creating, setCreating] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [logicStatusFilter, setLogicStatusFilter] = useState('all');
    const [errorOnly, setErrorOnly] = useState(false);
    const runId = run?.runId ?? '';
    const hasTokens = Boolean(tokens.bearer && tokens.cms && tokens.mrs);
    const running = run?.status === 'RUNNING';
    const canRunStep2 = Boolean(run?.doneRows || run?.llmDoneRows || run?.status === 'DONE' || run?.status === 'FAILED');
    const pollInterval = 2000;
    const statusLabel = run ? RUN_STATUS_TEXT[run.status] : '미생성';
    const workflowState = useMemo(() => {
        if (!run)
            return 0;
        if (run.status === 'PENDING')
            return 0;
        if (run.status === 'RUNNING')
            return 1;
        if (run.doneRows > 0)
            return 2;
        return 1;
    }, [run?.status, run?.doneRows]);
    const progressText = useMemo(() => {
        const total = run?.totalRows ?? rows.length;
        const doneCount = run?.doneRows ?? 0;
        const errorCount = run?.errorRows ?? 0;
        return total > 0 ? `${Math.min(total, doneCount + errorCount)} / ${total}` : '0 / 0';
    }, [run?.totalRows, run?.doneRows, run?.errorRows, rows.length]);
    const runProgress = useMemo(() => {
        const total = run?.totalRows ?? rows.length;
        if (total <= 0)
            return 0;
        const doneCount = run?.doneRows ?? 0;
        const errorCount = run?.errorRows ?? 0;
        return Math.min(100, Math.round(((doneCount + errorCount) / total) * 100));
    }, [rows.length, run?.totalRows, run?.doneRows, run?.errorRows]);
    const step1DisabledReason = useMemo(() => {
        if (creating || isLoading)
            return '요청 처리 중입니다.';
        if (!runId)
            return '실행 대상이 없습니다.';
        if (!hasTokens)
            return '1단계 실행 토큰이 필요합니다.';
        if (!run || run.status !== 'PENDING')
            return '1단계는 PENDING 상태에서만 가능합니다.';
        return '';
    }, [run, runId, hasTokens, creating, isLoading]);
    const step2DisabledReason = useMemo(() => {
        if (creating || isLoading)
            return '요청 처리 중입니다.';
        if (!runId)
            return '실행 대상이 없습니다.';
        if (!run || !canRunStep2)
            return '1단계 실행 완료 후 2단계 평가를 시작하세요.';
        return '';
    }, [run, canRunStep2, runId, creating, isLoading]);
    const buildRowsPayload = ({ q, logicStatus, hasError }) => {
        const params = {};
        const query = q.trim();
        if (query) {
            params.q = query;
        }
        if (logicStatus !== 'all') {
            params.logicStatus = logicStatus;
        }
        if (hasError) {
            params.hasError = true;
        }
        return params;
    };
    const loadRows = async (id, filters) => {
        const resp = await api.get(`/generic-runs/${id}/rows`, {
            params: buildRowsPayload(filters ?? {
                q: searchQuery,
                logicStatus: logicStatusFilter,
                hasError: errorOnly,
            }),
        });
        setRows((resp.data.rows || []));
    };
    const loadRun = async (id) => {
        const resp = await api.get(`/generic-runs/${id}`);
        setRun(resp.data);
    };
    useEffect(() => {
        if (!runId) {
            return;
        }
        void loadRun(runId);
        void loadRows(runId);
    }, [runId, searchQuery, logicStatusFilter, errorOnly]);
    useEffect(() => {
        if (run?.status !== 'RUNNING' || !runId) {
            return;
        }
        const timer = setInterval(async () => {
            await loadRun(runId);
            await loadRows(runId);
        }, pollInterval);
        return () => {
            clearInterval(timer);
        };
    }, [runId, run?.status, searchQuery, logicStatusFilter, errorOnly]);
    const downloadTemplate = () => {
        window.open(`${api.defaults.baseURL}/generic-runs/template`, '_blank');
    };
    const createRunFromCsv = async () => {
        if (!files[0]?.originFileObj) {
            message.error('CSV 파일을 선택하세요.');
            return;
        }
        setCreating(true);
        try {
            const fd = new FormData();
            fd.append('environment', environment);
            fd.append('maxParallel', String(maxParallel));
            fd.append('openaiModel', openaiModel);
            fd.append('maxChars', String(maxChars));
            if (contextJson.trim())
                fd.append('contextJson', contextJson);
            if (targetAssistant.trim())
                fd.append('targetAssistant', targetAssistant);
            fd.append('file', files[0].originFileObj);
            const resp = await api.post('/generic-runs', fd);
            const created = {
                ...resp.data,
                runId: resp.data.runId,
                status: 'PENDING',
                totalRows: resp.data.rows ?? 0,
                doneRows: 0,
                errorRows: 0,
                llmDoneRows: 0,
            };
            setRun(created);
            await loadRun(resp.data.runId);
            await loadRows(resp.data.runId);
            message.success('검증 실행이 생성되었습니다.');
            setFiles([]);
        }
        catch (e) {
            message.error('검증 실행 생성 실패');
            console.error(e);
        }
        finally {
            setCreating(false);
        }
    };
    const createAndRunSingle = async () => {
        if (!singleQuery.trim()) {
            message.error('질의를 입력하세요.');
            return;
        }
        if (!hasTokens) {
            message.warning('cURL 토큰이 없어 단일 질의 실행이 불가합니다.');
            return;
        }
        setCreating(true);
        try {
            const resp = await api.post('/generic-runs/direct', {
                environment,
                query: singleQuery,
                llmCriteria: singleLlmCriteria,
                fieldPath: singleField,
                expectedValue: singleExpected,
                maxParallel,
                maxChars,
                openaiModel,
                contextJson: contextJson || undefined,
                targetAssistant: targetAssistant || undefined,
                bearer: tokens.bearer,
                cms: tokens.cms,
                mrs: tokens.mrs,
                openaiKey: openaiKey || undefined,
            });
            setRun({
                runId: resp.data.runId,
                status: 'RUNNING',
                totalRows: 1,
                doneRows: 0,
                errorRows: 0,
                llmDoneRows: 0,
            });
            await loadRun(resp.data.runId);
            await loadRows(resp.data.runId);
            message.success('단일 질의 실행을 즉시 시작했습니다.');
            setSingleQuery('');
            setSingleLlmCriteria('');
            setSingleField('');
            setSingleExpected('');
            setMode('upload');
        }
        catch (e) {
            message.error('단일 질의 실행 요청에 실패했습니다.');
            console.error(e);
        }
        finally {
            setCreating(false);
        }
    };
    const executeStep1 = async () => {
        if (!runId || !run || running)
            return;
        setIsLoading(true);
        try {
            await api.post(`/generic-runs/${runId}/execute`, {
                bearer: tokens.bearer,
                cms: tokens.cms,
                mrs: tokens.mrs,
            });
            message.success('1단계 질의 실행 요청 완료');
        }
        catch (e) {
            message.error('질의 실행에 실패했습니다.');
            console.error(e);
        }
        finally {
            setIsLoading(false);
        }
    };
    const evaluateStep2 = async () => {
        if (!runId)
            return;
        setIsLoading(true);
        try {
            await api.post(`/generic-runs/${runId}/evaluate`, {
                openaiKey: openaiKey || undefined,
                openaiModel,
                maxChars,
                maxParallel,
            });
            message.success('2단계 LLM 평가 요청 완료');
        }
        catch (e) {
            message.error('LLM 평가 요청에 실패했습니다.');
            console.error(e);
        }
        finally {
            setIsLoading(false);
        }
    };
    const passFail = useMemo(() => {
        const pass = rows.filter((x) => String(x.logicResult ?? '').startsWith('PASS')).length;
        const fail = rows.filter((x) => String(x.logicResult ?? '').startsWith('FAIL')).length;
        return `${pass} / ${fail}`;
    }, [rows]);
    const llmDoneCount = run?.llmDoneRows ?? rows.filter((x) => String(x.llmEvalStatus || '').trim() !== '').length;
    const errorCount = run?.errorRows ?? rows.filter((x) => String(x.error || '').trim() !== '').length;
    const hasFilter = searchQuery.trim() !== '' || logicStatusFilter !== 'all' || errorOnly;
    const tableToolbarLabel = hasFilter ? `필터 적용: ${rows.length}건` : `총 ${rows.length}건`;
    const logicFilterOptions = useMemo(() => [
        { value: 'all', label: '로직 상태: 전체' },
        { value: 'PASS', label: 'PASS' },
        { value: 'FAIL', label: 'FAIL' },
        { value: 'SKIP', label: 'SKIP' },
    ], []);
    return (_jsxs(Space, { direction: "vertical", size: 16, style: { width: '100%' }, className: "run-page-stack", children: [_jsxs(Card, { title: "\uC5D0\uC774\uC804\uD2B8 \uAC80\uC99D", className: "backoffice-content-card", children: [_jsxs("div", { className: "run-page-toolbar status-row", children: [_jsxs(Space, { size: 8, align: "center", children: [_jsx(Typography.Text, { strong: true, children: "\uC2E4\uD589 \uC0C1\uD0DC" }), _jsx(Tag, { color: statusColor(run?.status ?? 'PENDING'), children: statusLabel }), _jsxs(Typography.Text, { className: "run-meta", children: ["RUN_ID: ", runId || '-'] }), _jsxs(Typography.Text, { className: "run-meta", children: ["\uC9C4\uD589\uB960 ", progressText] })] }), _jsx(Tooltip, { title: `진행률 ${runProgress}%`, children: _jsxs(Typography.Text, { className: "run-meta", children: [runProgress, "%"] }) })] }), _jsxs(Space, { direction: "vertical", size: 8, style: { width: '100%', marginTop: 12 }, children: [_jsxs("div", { className: "run-page-toolbar", children: [_jsx(Space, { children: _jsx(Steps, { size: "small", current: workflowState, items: [
                                                { title: '생성', description: 'CSV/단일 질의 등록' },
                                                { title: '1단계 실행', description: '질의 실행' },
                                                { title: '2단계 평가', description: 'LLM 평가' },
                                            ] }) }), _jsx(Tooltip, { title: RUN_CREATION_HELP_TOOLTIP, children: _jsx(InfoCircleOutlined, { style: { color: '#7B5CF2', fontSize: 16 } }) })] }), _jsx(Typography.Text, { className: "run-meta", children: "cURL \uD1A0\uD070\uC740 \uC0C1\uB2E8\uC758 [cURL \uD1A0\uD070 \uD30C\uC2F1]\uC5D0\uC11C \uC785\uB825\uD558\uACE0, OpenAI key\uB294 2\uB2E8\uACC4\uC5D0\uC11C\uB9CC \uC785\uB825\uD558\uC138\uC694." })] }), _jsx(Alert, { type: hasTokens ? 'info' : 'warning', showIcon: true, style: { marginTop: 16 }, message: hasTokens ? '토큰이 적용된 상태입니다.' : '1단계 실행 토큰 미적용', description: hasTokens ? '실행 상태에서 1단계가 가능해집니다.' : '1단계 실행은 cURL 토큰이 필요합니다.' }), _jsx("div", { className: "run-filters", children: _jsxs(Row, { gutter: [8, 8], align: "middle", children: [_jsx(Col, { span: 10, md: 8, xs: 24, children: _jsx(Input.Search, { value: searchQuery, onChange: (e) => setSearchQuery(e.target.value), onSearch: (value) => setSearchQuery(value), allowClear: true, placeholder: "\uC751\uB2F5/\uC9C8\uC758 \uAC80\uC0C9", enterButton: "\uAC80\uC0C9" }) }), _jsx(Col, { span: 8, md: 6, xs: 24, children: _jsx(Select, { value: logicStatusFilter, onChange: (value) => setLogicStatusFilter(value), options: logicFilterOptions, style: { width: '100%' } }) }), _jsx(Col, { span: 6, md: 4, xs: 24, children: _jsxs(Space, { children: [_jsx(Switch, { checked: errorOnly, onChange: setErrorOnly, checkedChildren: "ON", unCheckedChildren: "OFF" }), _jsx(Typography.Text, { className: "run-meta", children: "\uC624\uB958\uB9CC \uBCF4\uAE30" })] }) }), _jsx(Col, { span: 24, md: 6, xs: 24, children: hasFilter ? _jsx(Tag, { color: "blue", children: "\uD544\uD130 \uC801\uC6A9\uB428" }) : null })] }) }), _jsx("div", { className: "section-title", style: { marginTop: 16 }, children: "\uC2E4\uD589 \uC785\uB825" }), _jsx(Space, { style: { marginBottom: 12 }, children: _jsxs(Radio.Group, { value: mode, onChange: (e) => setMode(e.target.value), optionType: "button", buttonStyle: "solid", children: [_jsx(Radio.Button, { value: "upload", children: "CSV \uC5C5\uB85C\uB4DC" }), _jsx(Radio.Button, { value: "single", children: "\uB2E8\uC77C \uC9C8\uC758" })] }) }), mode === 'upload' ? (_jsx(Upload, { beforeUpload: () => false, fileList: files, onChange: (e) => setFiles(e.fileList), maxCount: 1, children: _jsx(Button, { icon: _jsx(FileExcelOutlined, {}), type: "dashed", children: "CSV \uC120\uD0DD" }) })) : (_jsx(Card, { size: "small", title: "\uB2E8\uC77C \uC9C8\uC758 \uC785\uB825", className: "backoffice-content-card", children: _jsxs(Space, { direction: "vertical", style: { width: '100%' }, size: 12, children: [_jsx(Input.TextArea, { rows: 4, value: singleQuery, onChange: (e) => setSingleQuery(e.target.value), placeholder: "\uC5D0\uC774\uC804\uD2B8\uC5D0 \uC9C8\uC758\uD560 \uBB38\uC7A5\uC744 \uC785\uB825\uD558\uC138\uC694", showCount: true, maxLength: 1200 }), _jsx(Input, { value: singleLlmCriteria, onChange: (e) => setSingleLlmCriteria(e.target.value), placeholder: "LLM \uD3C9\uAC00 \uAE30\uC900(\uC120\uD0DD)" }), _jsxs(Row, { gutter: 12, children: [_jsx(Col, { span: 12, children: _jsx(Input, { value: singleField, onChange: (e) => setSingleField(e.target.value), placeholder: "\uAC80\uC99D \uD544\uB4DC \uD0A4(\uC608: assistantMessage, \uC120\uD0DD \uAC00\uB2A5)" }) }), _jsx(Col, { span: 12, children: _jsx(Input, { value: singleExpected, onChange: (e) => setSingleExpected(e.target.value), placeholder: "\uAE30\uB300\uAC12(\uC120\uD0DD)" }) })] })] }) })), _jsxs(Card, { size: "small", title: "\uC2E4\uD589 \uC635\uC158 / LLM \uC124\uC815", className: "backoffice-content-card", style: { marginTop: 16 }, children: [_jsxs(Row, { gutter: 12, children: [_jsx(Col, { span: 6, children: _jsx(Input, { size: "middle", value: openaiModel, onChange: (e) => setOpenaiModel(e.target.value), addonBefore: "LLM \uBAA8\uB378", placeholder: "gpt-5.2" }) }), _jsx(Col, { span: 6, children: _jsx(Input.Password, { size: "middle", value: openaiKey, onChange: (e) => setOpenaiKey(e.target.value), addonBefore: "OpenAI \uD0A4", placeholder: "LLM \uD3C9\uAC00 \uC2DC \uC785\uB825" }) }), _jsx(Col, { span: 6, children: _jsx(InputNumber, { size: "middle", min: 1, value: maxParallel, onChange: (next) => setMaxParallel(clampNumber(next, 3)), addonBefore: "\uB3D9\uC2DC \uC2E4\uD589 \uC218", style: { width: '100%' } }) }), _jsx(Col, { span: 6, children: _jsx(InputNumber, { size: "middle", min: 1000, step: 500, value: maxChars, onChange: (next) => setMaxChars(clampNumber(next, 15000)), addonBefore: "\uCD5C\uB300 \uC751\uB2F5 \uAE38\uC774", style: { width: '100%' } }) })] }), _jsx("div", { style: { marginTop: 12 }, children: _jsx(Input.TextArea, { rows: 2, value: contextJson, onChange: (e) => setContextJson(e.target.value), placeholder: '\uCEE8\uD14D\uC2A4\uD2B8 JSON (\uC120\uD0DD): {"recruitPlanId": 123}' }) }), _jsx("div", { style: { marginTop: 12 }, children: _jsx(Input, { value: targetAssistant, onChange: (e) => setTargetAssistant(e.target.value), placeholder: "\uB300\uC0C1 \uC5D0\uC774\uC804\uD2B8(\uC120\uD0DD)" }) })] }), _jsx("div", { style: { marginTop: 16 }, children: _jsxs(Space, { wrap: true, size: [8, 8], children: [_jsx(Button, { type: "primary", loading: creating, icon: mode === 'upload' ? _jsx(RocketOutlined, {}) : _jsx(CheckCircleOutlined, {}), onClick: mode === 'upload' ? createRunFromCsv : createAndRunSingle, children: RUN_CREATION_LABEL }), _jsx(Tooltip, { title: step1DisabledReason || undefined, children: _jsx("span", { children: _jsx(Button, { onClick: executeStep1, disabled: Boolean(step1DisabledReason), loading: isLoading, icon: running ? _jsx(LoadingOutlined, {}) : undefined, children: "1\uB2E8\uACC4 \uC9C8\uC758 \uC2E4\uD589" }) }) }), _jsx(Tooltip, { title: step2DisabledReason || undefined, children: _jsx("span", { children: _jsx(Button, { onClick: evaluateStep2, disabled: Boolean(step2DisabledReason), loading: isLoading, children: "2\uB2E8\uACC4 LLM \uD3C9\uAC00" }) }) }), _jsx(Button, { href: runId ? `${api.defaults.baseURL}/generic-runs/${runId}/export.xlsx` : undefined, disabled: !runId, icon: _jsx(FileExcelOutlined, {}), children: "Excel \uB2E4\uC6B4\uB85C\uB4DC" }), _jsx(Button, { onClick: () => runId && void loadRows(runId), children: "\uACB0\uACFC \uC0C8\uB85C\uACE0\uCE68" }), _jsx(Button, { onClick: downloadTemplate, type: "default", children: "\uD15C\uD50C\uB9BF \uB2E4\uC6B4\uB85C\uB4DC" })] }) }), isLoading && (_jsxs("div", { className: "run-meta", style: { marginTop: 12 }, children: [_jsx(Spin, { size: "small", indicator: _jsx(LoadingOutlined, {}) }), _jsx("span", { style: { marginLeft: 6 }, children: "\uC694\uCCAD \uCC98\uB9AC \uC911" })] }))] }), _jsxs("div", { children: [_jsx("div", { className: "section-title", children: "\uACB0\uACFC \uB300\uC2DC\uBCF4\uB4DC" }), _jsx(MetricsBar, { total: run?.totalRows ?? rows.length, passFail: passFail, llmDone: llmDoneCount, errors: errorCount })] }), rows.length === 0 ? (_jsx(Card, { className: "backoffice-content-card backoffice-empty-state", children: _jsx(Empty, { description: _jsxs(Space, { direction: "vertical", children: [_jsx("span", { children: "\uC870\uD68C\uB41C \uC9C8\uC758 \uACB0\uACFC\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4." }), _jsx("span", { className: "run-runner-hint", children: "CSV \uC5C5\uB85C\uB4DC \uB610\uB294 \uB2E8\uC77C \uC9C8\uC758\uB97C \uD1B5\uD574 \uC2E4\uD589\uC744 \uBA3C\uC800 \uB9CC\uB4E4\uC5B4 \uC8FC\uC138\uC694." })] }) }) })) : (_jsxs(_Fragment, { children: [_jsx(Divider, { style: { marginTop: 0 } }), _jsx(Typography.Text, { className: "run-meta", style: { marginBottom: 8, display: 'inline-block' }, children: tableToolbarLabel }), _jsx(RunTable, { rows: rows })] }))] }));
}
