import { useEffect, useState } from 'react';
import { Form } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';
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
} from '../../../api/validation';
import type {
  QueryGroup,
  ValidationQuery,
  ValidationTestSet,
} from '../../../api/types/validation';
import type { Environment } from '../../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../../app/types';
import {
  buildDefaultTestSetFormValues,
  buildTestSetConfig,
  normalizeQueryIds,
  QUERY_PICKER_PAGE_SIZE_DEFAULT,
  type TestSetFormValues,
  toTestSetFormValues,
} from '../utils/testSetForm';

export function useTestSetManagement({
  environment,
  tokens,
  message,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  message: MessageInstance;
}) {
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
  const [queryPickerCategory, setQueryPickerCategory] = useState<string | undefined>(undefined);
  const [queryPickerGroupId, setQueryPickerGroupId] = useState<string | undefined>(undefined);
  const [queryPickerSelectedIds, setQueryPickerSelectedIds] = useState<string[]>([]);
  const [queryPickerItems, setQueryPickerItems] = useState<ValidationQuery[]>([]);
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

  const resetQueryPickerState = () => {
    setQueryPickerOpen(false);
    setQueryPickerSearchInput('');
    setQueryPickerSearchKeyword('');
    setQueryPickerCategory(undefined);
    setQueryPickerGroupId(undefined);
    setQueryPickerPage(1);
    setQueryPickerPageSize(QUERY_PICKER_PAGE_SIZE_DEFAULT);
    setQueryPickerItems([]);
    setQueryPickerTotal(0);
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
      mode !== 'create'
      || queryIds.length === 0
      || handledCreateParam === signature
    ) {
      return;
    }

    setHandledCreateParam(signature);
    setEditing(null);
    setQuerySelection(queryIds);
    resetQueryPickerState();
    form.setFieldsValue(buildDefaultTestSetFormValues());
    setModalOpen(true);
  }, [form, handledCreateParam, location.search]);

  const openCreate = () => {
    setEditing(null);
    setQuerySelection([]);
    resetQueryPickerState();
    form.setFieldsValue(buildDefaultTestSetFormValues());
    setModalOpen(true);
  };

  const openEdit = async (testSet: ValidationTestSet) => {
    try {
      const detail = await getValidationTestSet(testSet.id);
      setEditing(detail);
      setQuerySelection(detail.queryIds || []);
      resetQueryPickerState();
      form.setFieldsValue(toTestSetFormValues(detail));
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

      const { config, parseError } = buildTestSetConfig(values);
      if (parseError) {
        message.error(parseError);
        return;
      }

      setSaving(true);
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

  return {
    items,
    total,
    loading,
    selectedTestSetId,
    setSelectedTestSetId,
    search,
    setSearch,
    queryPickerOpen,
    setQueryPickerOpen,
    queryPickerLoading,
    queryPickerSearchInput,
    setQueryPickerSearchInput,
    queryPickerSearchKeyword,
    setQueryPickerSearchKeyword,
    queryPickerCategory,
    setQueryPickerCategory,
    queryPickerGroupId,
    setQueryPickerGroupId,
    queryPickerSelectedIds,
    setQueryPickerSelectedIds,
    queryPickerItems,
    queryPickerPage,
    setQueryPickerPage,
    queryPickerPageSize,
    setQueryPickerPageSize,
    queryPickerTotal,
    queryGroups,
    modalOpen,
    setModalOpen,
    editing,
    saving,
    form,
    openCreate,
    openEdit,
    handleSave,
    handleDelete,
    handleClone,
    setQuerySelection,
  };
}
