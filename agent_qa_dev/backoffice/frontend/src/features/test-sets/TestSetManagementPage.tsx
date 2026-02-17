import { useEffect, useMemo, useState } from 'react';
import { App, Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Typography } from 'antd';
import { useLocation } from 'react-router-dom';

import {
  cloneValidationTestSet,
  createValidationTestSet,
  deleteValidationTestSet,
  getValidationTestSet,
  listQueries,
  listValidationTestSets,
  updateValidationTestSet,
} from '../../api/validation';
import type { ValidationQuery, ValidationTestSet } from '../../api/types/validation';
import type { Environment } from '../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../app/types';
import { StandardDataTable } from '../../components/common/StandardDataTable';
import { formatDateTime } from '../../shared/utils/dateTime';

type TestSetFormValues = {
  name: string;
  description: string;
  queryIds: string[];
  agentId?: string;
  testModel?: string;
  evalModel?: string;
  repeatInConversation?: number;
  conversationRoomCount?: number;
  agentParallelCalls?: number;
  timeoutMs?: number;
};

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

  const [queries, setQueries] = useState<ValidationQuery[]>([]);
  const [queriesLoading, setQueriesLoading] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ValidationTestSet | null>(null);
  const [saving, setSaving] = useState(false);
  const [handledCreateParam, setHandledCreateParam] = useState('');
  const [form] = Form.useForm<TestSetFormValues>();

  const loadTestSets = async () => {
    setLoading(true);
    try {
      const data = await listValidationTestSets({ q: search || undefined, limit: 300 });
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

  const loadQueries = async () => {
    setQueriesLoading(true);
    try {
      const data = await listQueries({ limit: 2000 });
      setQueries(data.items);
    } catch (error) {
      console.error(error);
      message.error('질의 목록 조회에 실패했습니다.');
    } finally {
      setQueriesLoading(false);
    }
  };

  useEffect(() => {
    void loadTestSets();
  }, [search, environment, tokens.bearer, tokens.cms, tokens.mrs]);

  useEffect(() => {
    void loadQueries();
  }, [environment]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const mode = params.get('mode');
    const queryIdsText = params.get('queryIds') || '';
    const queryIds = queryIdsText
      .split(',')
      .map((queryId) => queryId.trim())
      .filter(Boolean);
    const signature = `${mode || ''}:${queryIds.join(',')}`;
    if (mode !== 'create' || queryIds.length === 0 || handledCreateParam === signature) return;
    setHandledCreateParam(signature);
    setEditing(null);
    form.setFieldsValue({
      name: '',
      description: '',
      queryIds,
      agentId: '',
      testModel: '',
      evalModel: '',
      repeatInConversation: 1,
      conversationRoomCount: 1,
      agentParallelCalls: 3,
      timeoutMs: 120000,
    });
    setModalOpen(true);
  }, [form, handledCreateParam, location.search, queries.length]);

  const queryOptions = useMemo(
    () => queries.map((query) => ({ label: `${query.queryText} (${query.id})`, value: query.id })),
    [queries],
  );

  const openCreate = () => {
    setEditing(null);
    form.setFieldsValue({
      name: '',
      description: '',
      queryIds: [],
      agentId: '',
      testModel: '',
      evalModel: '',
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
      form.setFieldsValue({
        name: detail.name,
        description: detail.description,
        queryIds: detail.queryIds || [],
        agentId: detail.config.agentId || '',
        testModel: detail.config.testModel || '',
        evalModel: detail.config.evalModel || '',
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
      setSaving(true);
      const config = {
        agentId: values.agentId || undefined,
        testModel: values.testModel || undefined,
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
          queryIds: values.queryIds,
          config,
        });
        message.success('테스트 세트를 수정했습니다.');
      } else {
        await createValidationTestSet({
          name: values.name,
          description: values.description,
          queryIds: values.queryIds,
          config,
        });
        message.success('테스트 세트를 생성했습니다.');
      }
      setModalOpen(false);
      await loadTestSets();
    } catch (error) {
      console.error(error);
      message.error('테스트 세트 저장에 실패했습니다.');
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
    <Card className="backoffice-content-card" title="테스트 세트">
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Typography.Text type="secondary">
          테스트 세트는 환경 비귀속 설계 자산입니다. 실행 시 현재 선택된 환경({environment})이 적용됩니다.
        </Typography.Text>

        <Space wrap>
          <Input.Search
            allowClear
            placeholder="테스트 세트 이름 검색"
            onSearch={setSearch}
            style={{ width: 320 }}
            enterButton
          />
          <Button type="primary" onClick={openCreate}>테스트 세트 생성</Button>
          <Button type="primary" disabled={!selectedTestSetId} onClick={() => onOpenValidationRun?.(selectedTestSetId)}>
            검증 실행으로 이동
          </Button>
          <Button onClick={onOpenValidationHistory}>검증 이력으로 이동</Button>
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
              sorter: (a, b) => String(a.updatedAt || '').localeCompare(String(b.updatedAt || '')),
            },
            {
              key: 'actions',
              title: '작업',
              width: TEST_SET_COLUMN_WIDTHS.actions,
              render: (_, row: ValidationTestSet) => (
                <Space size="small">
                  <Button onClick={() => { void openEdit(row); }}>수정</Button>
                  <Button onClick={() => { void handleClone(row.id); }}>복제</Button>
                  <Popconfirm title="테스트 세트를 삭제할까요?" onConfirm={() => { void handleDelete(row.id); }}>
                    <Button danger>삭제</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Space>

      <Modal
        open={modalOpen}
        title={editing ? '테스트 세트 수정' : '테스트 세트 생성'}
        onCancel={() => setModalOpen(false)}
        onOk={() => { void handleSave(); }}
        okText={editing ? '수정' : '생성'}
        confirmLoading={saving}
        width={860}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item label="이름" name="name" rules={[{ required: true, message: '이름을 입력해 주세요.' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="설명" name="description">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
          <Form.Item
            label="질의 선택"
            name="queryIds"
            rules={[{ required: true, type: 'array', min: 1, message: '최소 1개 질의를 선택해 주세요.' }]}
          >
            <Select
              mode="multiple"
              allowClear
              loading={queriesLoading}
              placeholder="테스트 세트에 포함할 질의를 선택하세요."
              options={queryOptions}
              optionFilterProp="label"
            />
          </Form.Item>
          <Typography.Text strong>기본 실행 파라미터</Typography.Text>
          <Space style={{ width: '100%' }} wrap>
            <Form.Item label="Agent ID" name="agentId" style={{ minWidth: 220 }}>
              <Input placeholder="ORCHESTRATOR_WORKER_V3" />
            </Form.Item>
            <Form.Item label="Test Model" name="testModel" style={{ minWidth: 180 }}>
              <Input placeholder="gpt-5.2" />
            </Form.Item>
            <Form.Item label="Eval Model" name="evalModel" style={{ minWidth: 180 }}>
              <Input placeholder="gpt-5.2" />
            </Form.Item>
            <Form.Item label="반복 수" name="repeatInConversation" style={{ minWidth: 120 }}>
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item label="대화 방 수" name="conversationRoomCount" style={{ minWidth: 120 }}>
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item label="병렬 호출 수" name="agentParallelCalls" style={{ minWidth: 120 }}>
              <InputNumber min={1} />
            </Form.Item>
            <Form.Item label="타임아웃(ms)" name="timeoutMs" style={{ minWidth: 140 }}>
              <InputNumber min={1000} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Card>
  );
}
