import { useEffect, useRef, useState } from 'react';
import { Form } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';
import type { UploadFile } from 'antd/es/upload/interface';
import { AxiosError } from 'axios';

import {
  createQuery,
  deleteQuery,
  listQueries,
  listQueryGroups,
  previewQueriesBulkUpload,
  updateQuery,
  uploadQueriesBulk,
} from '../../../api/validation';
import type { QueryCategory, QueryGroup, ValidationQuery } from '../../../api/types/validation';
import type { Environment } from '../../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../../app/types';
import { formatDateTime, formatShortDate, toTimestamp } from '../../../shared/utils/dateTime';
import { parseJsonOrOriginal, stringifyPretty } from '../../../shared/utils/json';
import { BULK_UPLOAD_EMPTY_TEXT } from '../constants';
import type { UploadPreviewRow } from '../types';
import { parseUploadPreviewFile } from '../utils/uploadPreview';

type QueryFormValues = {
  queryText: string;
  expectedResult: string;
  category: QueryCategory;
  groupId?: string;
  llmEvalCriteria: string;
  logicFieldPath: string;
  logicExpectedValue: string;
  contextJson: string;
  targetAssistant: string;
};

function normalizeMultiSelectValue(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
}

export function useQueryManagement({
  environment,
  tokens,
  message,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  message: MessageInstance;
}) {
  const [groups, setGroups] = useState<QueryGroup[]>([]);
  const [items, setItems] = useState<ValidationQuery[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string[]>([]);
  const [groupId, setGroupId] = useState<string[]>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ValidationQuery | null>(null);
  const [saving, setSaving] = useState(false);
  const [bulkUploadModalOpen, setBulkUploadModalOpen] = useState(false);
  const [bulkUploadFiles, setBulkUploadFiles] = useState<UploadFile[]>([]);
  const [bulkUploadPreviewRows, setBulkUploadPreviewRows] = useState<UploadPreviewRow[]>([]);
  const [bulkUploadPreviewTotal, setBulkUploadPreviewTotal] = useState(0);
  const [bulkUploadPreviewEmptyText, setBulkUploadPreviewEmptyText] = useState(BULK_UPLOAD_EMPTY_TEXT);
  const [bulkUploadGroupConfirmOpen, setBulkUploadGroupConfirmOpen] = useState(false);
  const [bulkUploadPendingGroupNames, setBulkUploadPendingGroupNames] = useState<string[]>([]);
  const [bulkUploadPendingGroupRows, setBulkUploadPendingGroupRows] = useState<number[]>([]);
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const previewRequestSeq = useRef(0);
  const [form] = Form.useForm<QueryFormValues>();

  const loadGroups = async () => {
    try {
      const data = await listQueryGroups({ limit: 500 });
      setGroups(data.items);
    } catch (error) {
      console.error(error);
      message.error('그룹 목록 조회에 실패했습니다.');
    }
  };

  const loadQueries = async () => {
    setLoading(true);
    try {
      const selectedCategories = normalizeMultiSelectValue(category);
      const selectedGroupIds = normalizeMultiSelectValue(groupId);
      const data = await listQueries({
        q: search || undefined,
        category: selectedCategories.length > 0 ? selectedCategories : undefined,
        groupId: selectedGroupIds.length > 0 ? selectedGroupIds : undefined,
        offset: (currentPage - 1) * pageSize,
        limit: pageSize,
        sortBy: 'createdAt',
        sortOrder: 'desc',
      });
      const sortedItems = [...data.items].sort((a, b) => {
        const diff = toTimestamp(b.createdAt) - toTimestamp(a.createdAt);
        if (diff !== 0) return diff;
        return String(b.id).localeCompare(String(a.id));
      });
      setItems(sortedItems);
      setTotal(data.total);
      if (data.items.length === 0 && data.total > 0 && currentPage > 1) {
        setCurrentPage((prev) => Math.max(1, prev - 1));
      }
    } catch (error) {
      console.error(error);
      message.error('질의 목록 조회에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadGroups();
  }, [environment]);

  useEffect(() => {
    void loadQueries();
  }, [search, category, groupId, currentPage, pageSize, environment, tokens.bearer, tokens.cms, tokens.mrs]);

  const openCreate = () => {
    setEditing(null);
    form.setFieldsValue({
      queryText: '',
      expectedResult: '',
      category: 'Happy path',
      groupId: undefined,
      llmEvalCriteria: '',
      logicFieldPath: '',
      logicExpectedValue: '',
      contextJson: '',
      targetAssistant: '',
    });
    setModalOpen(true);
  };

  const openEdit = (row: ValidationQuery) => {
    setEditing(row);
    form.setFieldsValue({
      queryText: row.queryText,
      expectedResult: row.expectedResult,
      category: row.category as QueryCategory,
      groupId: row.groupId || undefined,
      llmEvalCriteria: stringifyPretty(row.llmEvalCriteria),
      logicFieldPath: row.logicFieldPath,
      logicExpectedValue: row.logicExpectedValue,
      contextJson: row.contextJson || '',
      targetAssistant: row.targetAssistant || '',
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const criteria = parseJsonOrOriginal<Record<string, unknown>>(values.llmEvalCriteria);

      if (editing) {
        await updateQuery(editing.id, {
          queryText: values.queryText,
          expectedResult: values.expectedResult,
          category: values.category,
          groupId: values.groupId ?? null,
          llmEvalCriteria: criteria,
          logicFieldPath: values.logicFieldPath,
          logicExpectedValue: values.logicExpectedValue,
          contextJson: values.contextJson,
          targetAssistant: values.targetAssistant,
        });
        message.success('질의를 수정했습니다.');
      } else {
        await createQuery({
          queryText: values.queryText,
          expectedResult: values.expectedResult,
          category: values.category,
          groupId: values.groupId,
          llmEvalCriteria: criteria,
          logicFieldPath: values.logicFieldPath,
          logicExpectedValue: values.logicExpectedValue,
          contextJson: values.contextJson,
          targetAssistant: values.targetAssistant,
          createdBy: 'unknown',
        });
        message.success('질의를 등록했습니다.');
      }
      setModalOpen(false);
      await loadQueries();
    } catch (error) {
      console.error(error);
      message.error('질의 저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (queryId: string) => {
    try {
      await deleteQuery(queryId);
      setSelectedRowKeys((prev) => prev.filter((key) => key !== queryId));
      message.success('질의가 삭제됐어요.');
      await loadQueries();
    } catch (error) {
      console.error(error);
      message.error('질의 삭제에 실패했습니다.');
    }
  };

  const resetBulkUploadState = () => {
    previewRequestSeq.current += 1;
    setBulkUploadFiles([]);
    setBulkUploadPreviewRows([]);
    setBulkUploadPreviewTotal(0);
    setBulkUploadPreviewEmptyText(BULK_UPLOAD_EMPTY_TEXT);
    setBulkUploadGroupConfirmOpen(false);
    setBulkUploadPendingGroupNames([]);
    setBulkUploadPendingGroupRows([]);
  };

  const openBulkUploadModal = () => {
    resetBulkUploadState();
    setBulkUploadModalOpen(true);
  };

  const closeBulkUploadModal = () => {
    if (bulkUploading) return;
    setBulkUploadModalOpen(false);
    resetBulkUploadState();
  };

  const closeBulkUploadGroupConfirmModal = () => {
    if (bulkUploading) return;
    setBulkUploadGroupConfirmOpen(false);
  };

  const handleBulkUploadFileChange = async (nextFiles: UploadFile[]) => {
    const latestFiles = nextFiles.slice(-1);
    const requestId = previewRequestSeq.current + 1;
    previewRequestSeq.current = requestId;
    setBulkUploadFiles(latestFiles);
    setBulkUploadGroupConfirmOpen(false);
    setBulkUploadPendingGroupNames([]);
    setBulkUploadPendingGroupRows([]);
    const selectedFile = latestFiles[0]?.originFileObj;
    if (!selectedFile) {
      setBulkUploadPreviewRows([]);
      setBulkUploadPreviewTotal(0);
      setBulkUploadPreviewEmptyText(BULK_UPLOAD_EMPTY_TEXT);
      return;
    }
    try {
      const preview = await parseUploadPreviewFile(selectedFile);
      if (requestId !== previewRequestSeq.current) return;
      setBulkUploadPreviewRows(preview.rows);
      setBulkUploadPreviewTotal(preview.totalRows);
      setBulkUploadPreviewEmptyText(preview.emptyText);
      if (preview.warningText) {
        message.warning(preview.warningText);
      }
    } catch (error) {
      console.error(error);
      if (requestId !== previewRequestSeq.current) return;
      setBulkUploadPreviewRows([]);
      setBulkUploadPreviewTotal(0);
      setBulkUploadPreviewEmptyText('미리보기를 불러오지 못했어요.');
      message.error('CSV 미리보기에 실패했습니다.');
    }
  };

  const showBulkUploadError = (error: unknown) => {
    console.error(error);
    const detail = error instanceof AxiosError
      ? String(error.response?.data?.detail || '').trim()
      : '';
    if (detail) {
      message.error(`벌크 업로드에 실패했습니다. (${detail})`);
    } else {
      message.error('벌크 업로드에 실패했습니다.');
    }
  };

  const runBulkUpload = async (file: File) => {
    const result = await uploadQueriesBulk(file, undefined, 'unknown');
    message.success('업로드가 완료됐어요.');
    if ((result.createdGroupNames?.length || 0) > 0) {
      message.info(`그룹이 자동 생성됐어요. (${result.createdGroupNames?.join(', ')})`);
    }
    setBulkUploadGroupConfirmOpen(false);
    setBulkUploadModalOpen(false);
    resetBulkUploadState();
    await Promise.all([loadGroups(), loadQueries()]);
  };

  const handleBulkUpload = async () => {
    const file = bulkUploadFiles[0]?.originFileObj;
    if (!file) {
      message.warning('업로드할 파일을 선택해 주세요.');
      return;
    }
    try {
      setBulkUploading(true);
      const preview = await previewQueriesBulkUpload(file);
      if ((preview.groupsToCreate?.length || 0) > 0) {
        setBulkUploadPendingGroupNames(preview.groupsToCreate);
        setBulkUploadPendingGroupRows(preview.groupsToCreateRows || []);
        setBulkUploadGroupConfirmOpen(true);
        return;
      }
      await runBulkUpload(file);
    } catch (error) {
      showBulkUploadError(error);
    } finally {
      setBulkUploading(false);
    }
  };

  const confirmBulkUploadWithGroupCreation = async () => {
    const file = bulkUploadFiles[0]?.originFileObj;
    if (!file) {
      message.warning('업로드할 파일을 선택해 주세요.');
      return;
    }
    try {
      setBulkUploading(true);
      await runBulkUpload(file);
    } catch (error) {
      showBulkUploadError(error);
    } finally {
      setBulkUploading(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    const targetIds = [...selectedRowKeys];
    try {
      setBulkDeleting(true);
      const results = await Promise.allSettled(targetIds.map((queryId) => deleteQuery(queryId)));
      const failedIds = targetIds.filter((_, index) => results[index]?.status === 'rejected');
      const successCount = targetIds.length - failedIds.length;
      if (successCount === 0) {
        message.error('질의 삭제에 실패했습니다.');
        return;
      }
      if (failedIds.length === 0) {
        message.success('질의가 삭제됐어요.');
      } else {
        message.warning(`일부 질의만 삭제됐어요. (${successCount}/${targetIds.length})`);
      }
      setSelectedRowKeys(failedIds);
      setBulkDeleteModalOpen(false);
      await loadQueries();
    } catch (error) {
      console.error(error);
      message.error('질의 삭제에 실패했습니다.');
    } finally {
      setBulkDeleting(false);
    }
  };

  const handleSearch = (value: string) => {
    setSearch(value);
    setCurrentPage(1);
  };

  const handleCategoryChange = (value: string[] | undefined) => {
    setCategory(normalizeMultiSelectValue(value));
    setCurrentPage(1);
  };

  const handleGroupChange = (value: string[] | undefined) => {
    setGroupId(normalizeMultiSelectValue(value));
    setCurrentPage(1);
  };

  return {
    groups,
    items,
    total,
    loading,
    category,
    groupId,
    selectedRowKeys,
    setSelectedRowKeys,
    modalOpen,
    setModalOpen,
    editing,
    saving,
    form,
    bulkUploadModalOpen,
    bulkUploadFiles,
    bulkUploadPreviewRows,
    bulkUploadPreviewTotal,
    bulkUploadPreviewEmptyText,
    bulkUploadGroupConfirmOpen,
    bulkUploadPendingGroupNames,
    bulkUploadPendingGroupRows,
    bulkUploading,
    bulkDeleteModalOpen,
    setBulkDeleteModalOpen,
    bulkDeleting,
    currentPage,
    pageSize,
    setCurrentPage,
    setPageSize,
    openCreate,
    openEdit,
    handleSave,
    handleDelete,
    openBulkUploadModal,
    closeBulkUploadModal,
    closeBulkUploadGroupConfirmModal,
    handleBulkUploadFileChange,
    handleBulkUpload,
    confirmBulkUploadWithGroupCreation,
    handleBulkDelete,
    handleSearch,
    handleCategoryChange,
    handleGroupChange,
    loadQueries,
    formatDateTime,
    formatShortDate,
  };
}

export type { QueryFormValues };
