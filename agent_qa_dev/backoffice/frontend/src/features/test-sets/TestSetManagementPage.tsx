import { useEffect, useState } from 'react';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Typography,
} from 'antd';
import { useLocation } from 'react-router-dom';

import {
  cloneValidationTestSet,
  createValidationTestSet,
  deleteValidationTestSet,
  getValidationTestSet,
  listQueryGroups,
  listQueries,
  listValidationTestSets,
  updateValidationTestSet,
} from '../../api/validation';
import type {
  QueryGroup,
  ValidationQuery,
  ValidationTestSet,
} from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import {
  AGENT_MODE_OPTIONS,
  DEFAULT_AGENT_MODE_VALUE,
  DEFAULT_EVAL_MODEL_VALUE,
  EVAL_MODEL_OPTIONS,
} from '../validations/constants';
import { QueryPickerModal } from '../validations/components/QueryPickerModal';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { StandardModal } from '../../components/common/StandardModal';
import { formatDateTime } from '../../shared/utils/dateTime';

type TestSetFormValues = {
  name: string;
  description: string;
  agentId?: string;
  contextJson?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
};

const QUERY_PICKER_PAGE_SIZE_DEFAULT = 50;
const CONTEXT_SAMPLE =
  '{\n  "recruitPlanId": 1234,\n  "채용명": "2026년 상반기 채용"\n}';

const normalizeAgentModeValue = (value?: string) => {
  const trimmed = (value || '').trim();
  if (!trimmed || trimmed === 'ORCHESTRATOR_WORKER_V3') {
    return DEFAULT_AGENT_MODE_VALUE;
  }
  return trimmed;
};

const parseContextJson = (raw?: string) => {
  const text = (raw || '').trim();
  if (!text) {
    return { parsedContext: undefined as Record<string, unknown> | undefined };
  }
  try {
    const parsed = JSON.parse(text);
    if (
      parsed === null ||
      typeof parsed !== 'object' ||
      Array.isArray(parsed)
    ) {
      return {
        parsedContext: undefined,
        parseError: 'context는 JSON 객체 형태여야 합니다.',
      };
    }
    return { parsedContext: parsed as Record<string, unknown> };
  } catch (error) {
    return {
      parsedContext: undefined,
      parseError:
        `context JSON 형식이 올바르지 않습니다. ${error instanceof Error ? error.message : ''}`.trim(),
    };
  }
};

const stringifyContext = (value?: unknown) => {
  if (value === undefined || value === null) {
    return '';
  }
  if (typeof value === 'string') {
    return value.trim();
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
};

const normalizeQueryIds = (queryIds: string[]) =>
  Array.from(
    new Set(queryIds.map((queryId) => String(queryId).trim()).filter(Boolean)),
  );

const TEST_SET_COLUMN_WIDTHS = {
  name: 260,
  description: 360,
  itemCount: 100,
  updatedAt: 180,
  actions: 220,
};

export function TestSetManagementPage({
  environment,
  tokens,
  onOpenValidationRun,
  onOpenValidationHistory,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  onOpenValidationRun?: (testSetId?: string) => void;
  onOpenValidationHistory?: () => void;
}) {
  const { message } = App.useApp();
  const location = useLocation();
  const [search, setSearch] = useState('');
  const [items, setItems] = useState<ValidationTestSet[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedTestSetId, setSelectedTestSetId] = useState<string>('');

  const [queryPickerOpen, setQueryPickerOpen] = useState(false);
  const [queryPickerLoading, setQueryPickerLoading] = useState(false);
  const [queryPickerSearchInput, setQueryPickerSearchInput] = useState('');
  const [queryPickerSearchKeyword, setQueryPickerSearchKeyword] = useState('');
  const [queryPickerCategory, setQueryPickerCategory] = useState<
    string | undefined
  >(undefined);
  const [queryPickerGroupId, setQueryPickerGroupId] = useState<
    string | undefined
  >(undefined);
  const [queryPickerSelectedIds, setQueryPickerSelectedIds] = useState<
    string[]
  >([]);
  const [queryPickerItems, setQueryPickerItems] = useState<ValidationQuery[]>(
    [],
  );
  const [queryPickerPage, setQueryPickerPage] = useState(1);
  const [queryPickerPageSize, setQueryPickerPageSize] = useState(
    QUERY_PICKER_PAGE_SIZE_DEFAULT,
  );
  const [queryPickerTotal, setQueryPickerTotal] = useState(0);
  const [queryGroups, setQueryGroups] = useState<QueryGroup[]>([]);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ValidationTestSet | null>(null);
  const [saving, setSaving] = useState(false);
  const [handledCreateParam, setHandledCreateParam] = useState('');
  const [form] = Form.useForm<TestSetFormValues>();

  const loadTestSets = async () => {
    setLoading(true);
    try {
      const data = await listValidationTestSets({
        q: search || undefined,
        limit: 300,
      });
      setItems(data.items);
      setTotal(data.total);
      setSelectedTestSetId((prev) => {
        if (prev && data.items.some((item) => item.id === prev)) return prev;
        return data.items[0]?.id || '';
      });
    } catch (error) {
      console.error(error);
      message.error('테스트 세트 목록 조회에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const setQuerySelection = (queryIds: string[]) => {
    const normalized = normalizeQueryIds(queryIds);
    setQueryPickerSelectedIds(normalized);
    return normalized;
  };

  const loadQueryGroups = async () => {
    try {
      const data = await listQueryGroups();
      setQueryGroups(data.items);
    } catch (error) {
      console.error(error);
      message.error('질의 그룹 조회에 실패했습니다.');
    }
  };

  const loadQueryPickerItems = async () => {
    setQueryPickerLoading(true);
    try {
      const offset = Math.max(0, (queryPickerPage - 1) * queryPickerPageSize);
      const data = await listQueries({
        q: queryPickerSearchKeyword || undefined,
        category: queryPickerCategory || undefined,
        groupId: queryPickerGroupId || undefined,
        limit: queryPickerPageSize,
        offset,
      });
      setQueryPickerItems(data.items);
      setQueryPickerTotal(data.total);
    } catch (error) {
      console.error(error);
      message.error('질의 조회에 실패했습니다.');
      setQueryPickerItems([]);
      setQueryPickerTotal(0);
    } finally {
      setQueryPickerLoading(false);
    }
  };

  useEffect(() => {
    void loadTestSets();
  }, [search, environment, tokens.bearer, tokens.cms, tokens.mrs]);

  useEffect(() => {
    void loadQueryGroups();
  }, []);

  useEffect(() => {
    if (!queryPickerOpen) return;
    void loadQueryPickerItems();
  }, [
    queryPickerOpen,
    queryPickerPage,
    queryPickerPageSize,
    queryPickerSearchKeyword,
    queryPickerCategory,
    queryPickerGroupId,
  ]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const mode = params.get('mode');
    const queryIdsText = params.get('queryIds') || '';
    const queryIds = queryIdsText
      .split(',')
      .map((queryId) => queryId.trim())
      .filter(Boolean);
    const signature = `${mode || ''}:${queryIds.join(',')}`;
    if (
      mode !== 'create' ||
      queryIds.length === 0 ||
      handledCreateParam === signature
    )
      return;
    setHandledCreateParam(signature);
    setEditing(null);
    setQuerySelection(queryIds);
    form.setFieldsValue({
      name: '',
      description: '',
      agentId: DEFAULT_AGENT_MODE_VALUE,
      contextJson: '',
      evalModel: DEFAULT_EVAL_MODEL_VALUE,
      repeatInConversation: 1,
      conversationRoomCount: 1,
      agentParallelCalls: 3,
      timeoutMs: 120000,
    });
    setModalOpen(true);
  }, [form, handledCreateParam, location.search]);

  const openCreate = () => {
    setEditing(null);
    setQuerySelection([]);
    setQueryPickerOpen(false);
    setQueryPickerSearchInput('');
    setQueryPickerSearchKeyword('');
    setQueryPickerCategory(undefined);
    setQueryPickerGroupId(undefined);
    setQueryPickerPage(1);
    setQueryPickerPageSize(QUERY_PICKER_PAGE_SIZE_DEFAULT);
    setQueryPickerItems([]);
    setQueryPickerTotal(0);
    form.setFieldsValue({
      name: '',
      description: '',
      agentId: DEFAULT_AGENT_MODE_VALUE,
      contextJson: '',
      evalModel: DEFAULT_EVAL_MODEL_VALUE,
      repeatInConversation: 1,
      conversationRoomCount: 1,
      agentParallelCalls: 3,
      timeoutMs: 120000,
    });
    setModalOpen(true);
  };

  const openEdit = async (testSet: ValidationTestSet) => {
    try {
      const detail = await getValidationTestSet(testSet.id);
      setEditing(detail);
      setQuerySelection(detail.queryIds || []);
      setQueryPickerOpen(false);
      setQueryPickerSearchInput('');
      setQueryPickerSearchKeyword('');
      setQueryPickerCategory(undefined);
      setQueryPickerGroupId(undefined);
      setQueryPickerPage(1);
      setQueryPickerPageSize(QUERY_PICKER_PAGE_SIZE_DEFAULT);
      form.setFieldsValue({
        name: detail.name,
        description: detail.description,
        agentId: normalizeAgentModeValue(detail.config.agentId),
        contextJson: stringifyContext(detail.config.context),
        evalModel: detail.config.evalModel || DEFAULT_EVAL_MODEL_VALUE,
        repeatInConversation: detail.config.repeatInConversation ?? 1,
        conversationRoomCount: detail.config.conversationRoomCount ?? 1,
        agentParallelCalls: detail.config.agentParallelCalls ?? 3,
        timeoutMs: detail.config.timeoutMs ?? 120000,
      });
      setModalOpen(true);
    } catch (error) {
      console.error(error);
      message.error('테스트 세트 상세 조회에 실패했습니다.');
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const queryIds = queryPickerSelectedIds;
      if (queryIds.length === 0) {
        message.error('최소 1개 질의를 선택해 주세요.');
        return;
      }
      const parsedContext = parseContextJson(values.contextJson || '');
      if (parsedContext.parseError) {
        message.error(parsedContext.parseError);
        return;
      }
      setSaving(true);
      const config = {
        agentId: normalizeAgentModeValue(values.agentId),
        context: parsedContext.parsedContext,
        evalModel: values.evalModel || undefined,
        repeatInConversation: values.repeatInConversation,
        conversationRoomCount: values.conversationRoomCount,
        agentParallelCalls: values.agentParallelCalls,
        timeoutMs: values.timeoutMs,
      };
      if (editing) {
        await updateValidationTestSet(editing.id, {
          name: values.name,
          description: values.description,
          queryIds,
          config,
        });
        message.success('테스트 세트를 수정했습니다.');
      } else {
        await createValidationTestSet({
          name: values.name,
          description: values.description,
          queryIds,
          config,
        });
        message.success('테스트 세트를 생성했습니다.');
      }
      setModalOpen(false);
      await loadTestSets();
    } catch (error) {
      console.error(error);
      message.error('테스트 세트 저장을 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (testSetId: string) => {
    try {
      await deleteValidationTestSet(testSetId);
      message.success('테스트 세트를 삭제했습니다.');
      await loadTestSets();
    } catch (error) {
      console.error(error);
      message.error('테스트 세트 삭제에 실패했습니다.');
    }
  };

  const handleClone = async (testSetId: string) => {
    try {
      await cloneValidationTestSet(testSetId);
      message.success('테스트 세트를 복제했습니다.');
      await loadTestSets();
    } catch (error) {
      console.error(error);
      message.error('테스트 세트 복제에 실패했습니다.');
    }
  };

  return (
    <Card className="backoffice-content-card">
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Space wrap>
          <Input.Search
            allowClear
            placeholder="테스트 세트 이름 검색"
            onSearch={setSearch}
            style={{ width: 320 }}
            enterButton
          />
          <Button onClick={openCreate}>테스트 세트 생성</Button>
          <Button onClick={onOpenValidationHistory}>검증 결과로 이동</Button>
          <Button
            type="primary"
            disabled={!selectedTestSetId}
            onClick={() => onOpenValidationRun?.(selectedTestSetId)}
          >
            검증 실행으로 이동
          </Button>
        </Space>

        <StandardDataTable
          tableId="validation-test-sets-main"
          initialColumnWidths={TEST_SET_COLUMN_WIDTHS}
          minColumnWidth={100}
          className="query-management-table"
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={items}
          rowSelection={{
            type: 'radio',
            selectedRowKeys: selectedTestSetId ? [selectedTestSetId] : [],
            onChange: (keys) => setSelectedTestSetId(String(keys[0] || '')),
          }}
          pagination={{ total }}
          columns={[
            {
              key: 'name',
              title: '이름',
              dataIndex: 'name',
              width: TEST_SET_COLUMN_WIDTHS.name,
              sorter: (a, b) => String(a.name).localeCompare(String(b.name)),
            },
            {
              key: 'description',
              title: '설명',
              dataIndex: 'description',
              width: TEST_SET_COLUMN_WIDTHS.description,
              ellipsis: true,
              render: (value?: string) => value || '-',
            },
            {
              key: 'itemCount',
              title: '질의 수',
              dataIndex: 'itemCount',
              width: TEST_SET_COLUMN_WIDTHS.itemCount,
              sorter: (a, b) => a.itemCount - b.itemCount,
            },
            {
              key: 'updatedAt',
              title: '수정시각',
              dataIndex: 'updatedAt',
              width: TEST_SET_COLUMN_WIDTHS.updatedAt,
              render: (value?: string) => formatDateTime(value),
              sorter: (a, b) =>
                String(a.updatedAt || '').localeCompare(
                  String(b.updatedAt || ''),
                ),
            },
            {
              key: 'actions',
              title: '작업',
              width: TEST_SET_COLUMN_WIDTHS.actions,
              render: (_, row: ValidationTestSet) => (
                <Space size="small">
                  <Button
                    onClick={() => {
                      void openEdit(row);
                    }}
                  >
                    수정
                  </Button>
                  <Button
                    onClick={() => {
                      void handleClone(row.id);
                    }}
                  >
                    복제
                  </Button>
                  <Popconfirm
                    title="테스트 세트를 삭제할까요?"
                    onConfirm={() => {
                      void handleDelete(row.id);
                    }}
                  >
                    <Button danger>삭제</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Space>

      <StandardModal
        open={modalOpen}
        title={editing ? '테스트 세트 수정' : '테스트 세트 생성'}
        cancelText="취소"
        onCancel={() => setModalOpen(false)}
        onOk={() => {
          void handleSave();
        }}
        okText={editing ? '수정' : '생성'}
        confirmLoading={saving}
        width={760}
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          className="standard-modal-field-stack"
        >
          <Form.Item
            label="이름"
            name="name"
            rules={[{ required: true, message: '이름을 입력해 주세요.' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="설명" name="description">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
          <Form.Item
            label="질의 선택"
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <Space
              wrap
              style={{ width: '100%', justifyContent: 'space-between' }}
            >
              <Typography.Text type="secondary">
                선택 질의 {queryPickerSelectedIds.length}개
              </Typography.Text>
              <Space>
                <Button
                  onClick={() => {
                    setQueryPickerOpen(true);
                  }}
                >
                  질의 목록에서 선택
                </Button>
                <Button
                  onClick={() => {
                    setQuerySelection([]);
                  }}
                >
                  초기화
                </Button>
              </Space>
            </Space>
          </Form.Item>
          <Form.Item
            label="에이전트 모드"
            name="agentId"
            style={{ flex: 1 }}
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <Select options={[...AGENT_MODE_OPTIONS]} />
          </Form.Item>
          <Form.Item
            label="평가 모델"
            name="evalModel"
            style={{ flex: 1 }}
            rules={[{ required: true, message: '필수 항목입니다.' }]}
          >
            <Select options={[...EVAL_MODEL_OPTIONS]} />
          </Form.Item>
          <Space style={{ width: '100%' }} wrap>
            <Form.Item
              label="반복 수"
              name="repeatInConversation"
              style={{ flex: 1 }}
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item
              label="채팅방 수"
              name="conversationRoomCount"
              style={{ flex: 1 }}
              extra="채팅방 단위로 순차 실행됩니다. A 방 완료 후 B 방이 시작됩니다."
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item
              label="동시 실행 수"
              name="agentParallelCalls"
              style={{ flex: 1 }}
              extra="각 채팅방 내 질의를 N개씩 병렬 처리합니다."
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item
              label="타임아웃(ms)"
              name="timeoutMs"
              style={{ flex: 1 }}
              rules={[{ required: true, message: '필수 항목입니다.' }]}
            >
              <InputNumber min={1000} />
            </Form.Item>
          </Space>
          <Form.Item
            label="Context"
            name="contextJson"
            extra="API 호출 context에 전달할 JSON"
          >
            <Input.TextArea
              autoSize={{ minRows: 4, maxRows: 6 }}
              placeholder={CONTEXT_SAMPLE}
            />
          </Form.Item>
        </Form>
      </StandardModal>

      <QueryPickerModal
        queryPickerOpen={queryPickerOpen}
        setQueryPickerOpen={setQueryPickerOpen}
        queryPickerSaving={saving}
        handleImportQueries={() => {
          setQueryPickerOpen(false);
        }}
        queryPickerSearchInput={queryPickerSearchInput}
        setQueryPickerSearchInput={setQueryPickerSearchInput}
        setQueryPickerSearchKeyword={setQueryPickerSearchKeyword}
        queryPickerSearchKeyword={queryPickerSearchKeyword}
        setQueryPickerPage={setQueryPickerPage}
        queryPickerCategory={queryPickerCategory}
        setQueryPickerCategory={setQueryPickerCategory}
        queryPickerGroupId={queryPickerGroupId}
        setQueryPickerGroupId={setQueryPickerGroupId}
        groups={queryGroups}
        queryPickerSelectedIds={queryPickerSelectedIds}
        queryPickerLoading={queryPickerLoading}
        queryPickerItems={queryPickerItems}
        setQueryPickerSelectedIds={setQueryPickerSelectedIds}
        queryPickerPage={queryPickerPage}
        queryPickerPageSize={queryPickerPageSize}
        setQueryPickerPageSize={setQueryPickerPageSize}
        queryPickerTotal={queryPickerTotal}
      />
    </Card>
  );
}
