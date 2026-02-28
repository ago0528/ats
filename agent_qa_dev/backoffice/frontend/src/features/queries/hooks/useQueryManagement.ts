import { useEffect, useMemo, useRef, useState } from 'react';
import { Form } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';
import type { UploadFile } from 'antd/es/upload/interface';
import { AxiosError } from 'axios';

import {
  appendQueriesToValidationTestSet,
  createQuery,
  createValidationTestSet,
  deleteQuery,
  listQueries,
  listQueryGroups,
  listValidationTestSets,
  previewQueriesBulkUpdate,
  previewQueriesBulkUpload,
  updateQueriesBulk,
  updateQuery,
  uploadQueriesBulk,
} from '../../../api/validation';
import type {
  QueryCategory,
  QueryBulkUpdatePreviewResult,
  QueryGroup,
  QuerySelectionFilter,
  QuerySelectionPayload,
  ValidationQuery,
  ValidationTestSet,
} from '../../../api/types/validation';
import type { Environment } from '../../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../../app/types';
import { toTimestamp } from '../../../shared/utils/dateTime';
import { parseContextJson } from '../../../shared/utils/validationConfig';
import { BULK_UPDATE_EMPTY_TEXT, BULK_UPLOAD_EMPTY_TEXT } from '../constants';
import type { BulkUpdatePreviewRow, UploadPreviewRow } from '../types';
import { buildBulkUpdateCsvContent, mapBulkUpdatePreviewRows } from '../utils/bulkUpdate';
import { parseUploadPreviewFile } from '../utils/uploadPreview';

type QueryFormValues = {
  queryText: string;
  expectedResult: string;
  category: QueryCategory;
  groupId?: string;
};

type CreateTestSetFromSelectionValues = {
  name: string;
  description: string;
  contextJson?: string;
};

type AppendToTestSetValues = {
  testSetId: string;
};

type QuerySelectionSnapshot = {
  filter: QuerySelectionFilter;
  signature: string;
  totalMatched: number;
};

type BulkUpdateAttemptOptions = {
  allowCreateGroups: boolean;
  skipUnmappedQueryIds: boolean;
};

function normalizeMultiSelectValue(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item).trim()).filter(Boolean);
}

function normalizeStringArray(values?: string[]) {
  return Array.from(new Set((values || []).map((value) => String(value).trim()).filter(Boolean)));
}

function buildSelectionFilter({
  search,
  category,
  groupId,
}: {
  search: string;
  category: string[];
  groupId: string[];
}): QuerySelectionFilter {
  return {
    q: String(search || '').trim(),
    category: normalizeStringArray(category),
    groupId: normalizeStringArray(groupId),
  };
}

function buildSelectionSignature(filter: QuerySelectionFilter): string {
  const normalized = {
    q: String(filter.q || '').trim(),
    category: normalizeStringArray(filter.category).sort(),
    groupId: normalizeStringArray(filter.groupId).sort(),
  };
  return JSON.stringify(normalized);
}

function toQuerySelectionPayload(selection: {
  mode: 'manual' | 'filtered';
  manualSelectedRowKeys: string[];
  filteredSelectionSnapshot: QuerySelectionSnapshot | null;
  filteredDeselectedIds: string[];
}): QuerySelectionPayload | null {
  if (selection.mode === 'filtered') {
    if (!selection.filteredSelectionSnapshot) return null;
    return {
      mode: 'filtered',
      filter: selection.filteredSelectionSnapshot.filter,
      excludedQueryIds: selection.filteredDeselectedIds,
    };
  }
  if (selection.manualSelectedRowKeys.length === 0) return null;
  return {
    mode: 'ids',
    queryIds: selection.manualSelectedRowKeys,
  };
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
  const [manualSelectedRowKeys, setManualSelectedRowKeys] = useState<string[]>([]);
  const [selectionMode, setSelectionMode] = useState<'manual' | 'filtered'>('manual');
  const [filteredSelectionSnapshot, setFilteredSelectionSnapshot] = useState<QuerySelectionSnapshot | null>(null);
  const [filteredDeselectedIds, setFilteredDeselectedIds] = useState<string[]>([]);
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
  const [bulkUpdateModalOpen, setBulkUpdateModalOpen] = useState(false);
  const [bulkUpdateFiles, setBulkUpdateFiles] = useState<UploadFile[]>([]);
  const [bulkUpdatePreviewRows, setBulkUpdatePreviewRows] = useState<BulkUpdatePreviewRow[]>([]);
  const [bulkUpdatePreviewTotal, setBulkUpdatePreviewTotal] = useState(0);
  const [bulkUpdatePreviewEmptyText, setBulkUpdatePreviewEmptyText] = useState(BULK_UPDATE_EMPTY_TEXT);
  const [bulkUpdatePreviewSummary, setBulkUpdatePreviewSummary] = useState<QueryBulkUpdatePreviewResult | null>(null);
  const [bulkUpdateGroupConfirmOpen, setBulkUpdateGroupConfirmOpen] = useState(false);
  const [bulkUpdatePendingGroupNames, setBulkUpdatePendingGroupNames] = useState<string[]>([]);
  const [bulkUpdatePendingGroupRows, setBulkUpdatePendingGroupRows] = useState<number[]>([]);
  const [bulkUpdateUnmappedConfirmOpen, setBulkUpdateUnmappedConfirmOpen] = useState(false);
  const [bulkUpdatePendingUnmappedCount, setBulkUpdatePendingUnmappedCount] = useState(0);
  const [bulkUpdatePendingOptions, setBulkUpdatePendingOptions] = useState<BulkUpdateAttemptOptions | null>(null);
  const [bulkUpdating, setBulkUpdating] = useState(false);
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [createTestSetModalOpen, setCreateTestSetModalOpen] = useState(false);
  const [creatingTestSet, setCreatingTestSet] = useState(false);
  const [appendToTestSetModalOpen, setAppendToTestSetModalOpen] = useState(false);
  const [appendingToTestSet, setAppendingToTestSet] = useState(false);
  const [testSetOptionsLoading, setTestSetOptionsLoading] = useState(false);
  const [testSetOptions, setTestSetOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const bulkUploadPreviewRequestSeq = useRef(0);
  const bulkUpdatePreviewRequestSeq = useRef(0);
  const [form] = Form.useForm<QueryFormValues>();

  const currentSelectionFilter = useMemo(
    () => buildSelectionFilter({ search, category, groupId }),
    [search, category, groupId],
  );
  const currentSelectionSignature = useMemo(
    () => buildSelectionSignature(currentSelectionFilter),
    [currentSelectionFilter],
  );
  const isFilteredSelectionActive = selectionMode === 'filtered' && filteredSelectionSnapshot !== null;
  const isFilteredSelectionLocked = isFilteredSelectionActive
    ? filteredSelectionSnapshot.signature !== currentSelectionSignature
    : false;

  const selectedCount = isFilteredSelectionActive
    ? Math.max(0, filteredSelectionSnapshot.totalMatched - filteredDeselectedIds.length)
    : manualSelectedRowKeys.length;
  const filteredSelectionTotal = filteredSelectionSnapshot?.totalMatched || 0;
  const filteredDeselectedCount = filteredDeselectedIds.length;
  const canBulkDelete = selectionMode === 'manual' && manualSelectedRowKeys.length > 0;

  const tableSelectedRowKeys = useMemo(() => {
    if (!isFilteredSelectionActive) return manualSelectedRowKeys;
    if (isFilteredSelectionLocked) return [];
    const deselectedSet = new Set(filteredDeselectedIds);
    return items.map((item) => String(item.id)).filter((queryId) => !deselectedSet.has(queryId));
  }, [
    filteredDeselectedIds,
    isFilteredSelectionActive,
    isFilteredSelectionLocked,
    items,
    manualSelectedRowKeys,
  ]);

  const clearQuerySelection = () => {
    setSelectionMode('manual');
    setManualSelectedRowKeys([]);
    setFilteredSelectionSnapshot(null);
    setFilteredDeselectedIds([]);
    setBulkDeleteModalOpen(false);
  };

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

  const loadTestSetOptions = async () => {
    try {
      setTestSetOptionsLoading(true);
      const data = await listValidationTestSets({ limit: 300 });
      setTestSetOptions(
        data.items.map((item: ValidationTestSet) => ({
          label: `${item.name} (${item.itemCount}건)`,
          value: item.id,
        })),
      );
    } catch (error) {
      console.error(error);
      message.error('테스트 세트 목록 조회에 실패했습니다.');
    } finally {
      setTestSetOptionsLoading(false);
    }
  };

  const openCreate = () => {
    setEditing(null);
    form.setFieldsValue({
      queryText: '',
      expectedResult: '',
      category: 'Happy path',
      groupId: undefined,
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
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      if (editing) {
        await updateQuery(editing.id, {
          queryText: values.queryText,
          expectedResult: values.expectedResult,
          category: values.category,
          groupId: values.groupId ?? null,
        });
        message.success('질의를 수정했습니다.');
      } else {
        await createQuery({
          queryText: values.queryText,
          expectedResult: values.expectedResult,
          category: values.category,
          groupId: values.groupId,
          createdBy: 'unknown',
        });
        message.success('질의를 등록했습니다.');
      }
      setModalOpen(false);
      await loadQueries();
    } catch (error) {
      console.error(error);
      const detail = error instanceof AxiosError
        ? String(error.response?.data?.detail || '').trim()
        : '';
      if (detail.includes('Extra inputs are not permitted') || detail.includes('extra_forbidden')) {
        message.error('더 이상 지원하지 않는 구필드가 포함되어 저장에 실패했습니다. 최신 화면/템플릿으로 다시 시도해 주세요.');
      } else {
        message.error('질의 저장에 실패했습니다.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (queryId: string) => {
    try {
      await deleteQuery(queryId);
      setManualSelectedRowKeys((prev) => prev.filter((key) => key !== queryId));
      setFilteredDeselectedIds((prev) => prev.filter((key) => key !== queryId));
      message.success('질의가 삭제됐어요.');
      await loadQueries();
    } catch (error) {
      console.error(error);
      message.error('질의 삭제에 실패했습니다.');
    }
  };

  const resetBulkUploadState = () => {
    bulkUploadPreviewRequestSeq.current += 1;
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
    const requestId = bulkUploadPreviewRequestSeq.current + 1;
    bulkUploadPreviewRequestSeq.current = requestId;
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
      if (requestId !== bulkUploadPreviewRequestSeq.current) return;
      setBulkUploadPreviewRows(preview.rows);
      setBulkUploadPreviewTotal(preview.totalRows);
      setBulkUploadPreviewEmptyText(preview.emptyText);
      if (preview.warningText) {
        message.warning(preview.warningText);
      }
    } catch (error) {
      console.error(error);
      if (requestId !== bulkUploadPreviewRequestSeq.current) return;
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
    if ((result.invalidLatencyClassRows?.length || 0) > 0) {
      message.warning(`latencyClass 값이 유효하지 않은 행 ${result.invalidLatencyClassRows?.length}건은 업로드되지 않았어요. (허용값: SINGLE, MULTI)`);
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
      if ((preview.invalidLatencyClassRows?.length || 0) > 0) {
        message.warning(`latencyClass 값이 유효하지 않은 행 ${preview.invalidLatencyClassRows?.length}건이 있어요. (허용값: SINGLE, MULTI)`);
      }
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

  const applyBulkUpdatePreview = (preview: QueryBulkUpdatePreviewResult) => {
    setBulkUpdatePreviewSummary(preview);
    setBulkUpdatePreviewRows(mapBulkUpdatePreviewRows(preview.previewRows || []));
    setBulkUpdatePreviewTotal(preview.totalRows || 0);
    setBulkUpdatePreviewEmptyText('표시할 미리보기가 없어요.');
  };

  const resetBulkUpdateState = () => {
    bulkUpdatePreviewRequestSeq.current += 1;
    setBulkUpdateFiles([]);
    setBulkUpdatePreviewRows([]);
    setBulkUpdatePreviewTotal(0);
    setBulkUpdatePreviewEmptyText(BULK_UPDATE_EMPTY_TEXT);
    setBulkUpdatePreviewSummary(null);
    setBulkUpdateGroupConfirmOpen(false);
    setBulkUpdatePendingGroupNames([]);
    setBulkUpdatePendingGroupRows([]);
    setBulkUpdateUnmappedConfirmOpen(false);
    setBulkUpdatePendingUnmappedCount(0);
    setBulkUpdatePendingOptions(null);
  };

  const openBulkUpdateModal = () => {
    resetBulkUpdateState();
    setBulkUpdateModalOpen(true);
  };

  const closeBulkUpdateModal = () => {
    if (bulkUpdating) return;
    setBulkUpdateModalOpen(false);
    resetBulkUpdateState();
  };

  const closeBulkUpdateGroupConfirmModal = () => {
    if (bulkUpdating) return;
    setBulkUpdateGroupConfirmOpen(false);
  };

  const closeBulkUpdateUnmappedConfirmModal = () => {
    if (bulkUpdating) return;
    setBulkUpdateUnmappedConfirmOpen(false);
  };

  const handleBulkUpdateFileChange = async (nextFiles: UploadFile[]) => {
    const latestFiles = nextFiles.slice(-1);
    const requestId = bulkUpdatePreviewRequestSeq.current + 1;
    bulkUpdatePreviewRequestSeq.current = requestId;
    setBulkUpdateFiles(latestFiles);
    setBulkUpdateGroupConfirmOpen(false);
    setBulkUpdatePendingGroupNames([]);
    setBulkUpdatePendingGroupRows([]);
    setBulkUpdateUnmappedConfirmOpen(false);
    setBulkUpdatePendingUnmappedCount(0);
    setBulkUpdatePendingOptions(null);

    const selectedFile = latestFiles[0]?.originFileObj;
    if (!selectedFile) {
      setBulkUpdatePreviewRows([]);
      setBulkUpdatePreviewTotal(0);
      setBulkUpdatePreviewSummary(null);
      setBulkUpdatePreviewEmptyText(BULK_UPDATE_EMPTY_TEXT);
      return;
    }

    try {
      const preview = await previewQueriesBulkUpdate(selectedFile);
      if (requestId !== bulkUpdatePreviewRequestSeq.current) return;
      applyBulkUpdatePreview(preview);
    } catch (error) {
      console.error(error);
      if (requestId !== bulkUpdatePreviewRequestSeq.current) return;
      setBulkUpdatePreviewRows([]);
      setBulkUpdatePreviewTotal(0);
      setBulkUpdatePreviewSummary(null);
      setBulkUpdatePreviewEmptyText('미리보기를 불러오지 못했어요.');
      const detail = error instanceof AxiosError ? String(error.response?.data?.detail || '').trim() : '';
      if (detail) {
        message.error(`업데이트 미리보기에 실패했습니다. (${detail})`);
      } else {
        message.error('업데이트 미리보기에 실패했습니다.');
      }
    }
  };

  const loadAllFilteredQueries = async () => {
    const selectedCategories = normalizeMultiSelectValue(category);
    const selectedGroupIds = normalizeMultiSelectValue(groupId);
    const allItems: ValidationQuery[] = [];
    let offset = 0;
    const chunkSize = 500;

    while (true) {
      const data = await listQueries({
        q: search || undefined,
        category: selectedCategories.length > 0 ? selectedCategories : undefined,
        groupId: selectedGroupIds.length > 0 ? selectedGroupIds : undefined,
        offset,
        limit: chunkSize,
        sortBy: 'createdAt',
        sortOrder: 'desc',
      });
      allItems.push(...data.items);
      if (allItems.length >= data.total || data.items.length === 0) break;
      offset += chunkSize;
    }

    return allItems;
  };

  const handleDownloadBulkUpdateCsv = async () => {
    try {
      const allItems = await loadAllFilteredQueries();
      if (allItems.length === 0) {
        message.warning('다운로드할 질의가 없어요.');
        return;
      }
      const csvContent = buildBulkUpdateCsvContent(allItems);
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `queries-bulk-update-${Date.now()}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      message.error('CSV 다운로드에 실패했습니다.');
    }
  };

  const runBulkUpdateAttempt = async (options: BulkUpdateAttemptOptions) => {
    const file = bulkUpdateFiles[0]?.originFileObj;
    if (!file) {
      message.warning('업로드할 파일을 선택해 주세요.');
      return;
    }

    try {
      setBulkUpdating(true);
      const preview = await previewQueriesBulkUpdate(file);
      applyBulkUpdatePreview(preview);

      if ((preview.groupsToCreate?.length || 0) > 0 && !options.allowCreateGroups) {
        setBulkUpdatePendingOptions({ ...options, allowCreateGroups: true });
        setBulkUpdatePendingGroupNames(preview.groupsToCreate);
        setBulkUpdatePendingGroupRows(preview.groupsToCreateRows || []);
        setBulkUpdateGroupConfirmOpen(true);
        return;
      }

      if ((preview.unmappedQueryCount || 0) > 0 && !options.skipUnmappedQueryIds) {
        setBulkUpdatePendingOptions({ ...options, skipUnmappedQueryIds: true });
        setBulkUpdatePendingUnmappedCount(preview.unmappedQueryCount || 0);
        setBulkUpdateUnmappedConfirmOpen(true);
        return;
      }

      const result = await updateQueriesBulk(file, options);
      message.success(`업데이트가 완료됐어요. (${result.updatedCount}건)`);
      if ((result.createdGroupNames?.length || 0) > 0) {
        message.info(`그룹이 자동 생성됐어요. (${result.createdGroupNames?.join(', ')})`);
      }
      if ((result.skippedUnmappedCount || 0) > 0) {
        message.warning(`쿼리 ID 미매핑 항목 ${result.skippedUnmappedCount}건은 건너뛰었습니다.`);
      }
      setBulkUpdateGroupConfirmOpen(false);
      setBulkUpdateUnmappedConfirmOpen(false);
      setBulkUpdatePendingOptions(null);
      setBulkUpdateModalOpen(false);
      resetBulkUpdateState();
      await Promise.all([loadGroups(), loadQueries()]);
    } catch (error) {
      console.error(error);
      const detail = error instanceof AxiosError ? String(error.response?.data?.detail || '').trim() : '';
      if (detail) {
        message.error(`대규모 업데이트에 실패했습니다. (${detail})`);
      } else {
        message.error('대규모 업데이트에 실패했습니다.');
      }
    } finally {
      setBulkUpdating(false);
    }
  };

  const handleBulkUpdate = async () => {
    await runBulkUpdateAttempt({ allowCreateGroups: false, skipUnmappedQueryIds: false });
  };

  const confirmBulkUpdateWithGroupCreation = async () => {
    const nextOptions = bulkUpdatePendingOptions ?? { allowCreateGroups: true, skipUnmappedQueryIds: false };
    await runBulkUpdateAttempt({
      allowCreateGroups: true,
      skipUnmappedQueryIds: Boolean(nextOptions.skipUnmappedQueryIds),
    });
  };

  const confirmBulkUpdateWithUnmappedSkip = async () => {
    const nextOptions = bulkUpdatePendingOptions ?? { allowCreateGroups: false, skipUnmappedQueryIds: true };
    await runBulkUpdateAttempt({
      allowCreateGroups: Boolean(nextOptions.allowCreateGroups),
      skipUnmappedQueryIds: true,
    });
  };

  const handleBulkDelete = async () => {
    if (manualSelectedRowKeys.length === 0) return;
    const targetIds = [...manualSelectedRowKeys];
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
      setManualSelectedRowKeys(failedIds);
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

  const handleRowSelectionChange = (keys: Array<string | number | bigint>) => {
    if (!isFilteredSelectionActive) {
      setManualSelectedRowKeys(keys.map(String));
      return;
    }
    if (isFilteredSelectionLocked) return;
    const selectedKeySet = new Set(keys.map(String));
    const pageIds = items.map((item) => String(item.id));
    setFilteredDeselectedIds((prev) => {
      const next = new Set(prev);
      pageIds.forEach((pageId) => {
        if (selectedKeySet.has(pageId)) {
          next.delete(pageId);
        } else {
          next.add(pageId);
        }
      });
      return Array.from(next);
    });
  };

  const handleSelectAllFiltered = () => {
    if (total <= 0) {
      message.warning('선택할 질의가 없어요.');
      return;
    }
    setSelectionMode('filtered');
    setFilteredSelectionSnapshot({
      filter: currentSelectionFilter,
      signature: currentSelectionSignature,
      totalMatched: total,
    });
    setFilteredDeselectedIds([]);
    setManualSelectedRowKeys([]);
  };

  const handleOpenCreateTestSetModal = () => {
    if (selectedCount <= 0) {
      message.warning('테스트 세트로 만들 질의를 선택해 주세요.');
      return;
    }
    setCreateTestSetModalOpen(true);
  };

  const handleOpenAppendToTestSetModal = async () => {
    if (selectedCount <= 0) {
      message.warning('테스트 세트에 추가할 질의를 선택해 주세요.');
      return;
    }
    setAppendToTestSetModalOpen(true);
    if (testSetOptions.length === 0) {
      await loadTestSetOptions();
    }
  };

  const handleCreateTestSetFromSelection = async (values: CreateTestSetFromSelectionValues) => {
    const payload = toQuerySelectionPayload({
      mode: selectionMode,
      manualSelectedRowKeys,
      filteredSelectionSnapshot,
      filteredDeselectedIds,
    });
    if (!payload || selectedCount <= 0) {
      message.warning('선택된 질의가 없어요.');
      return;
    }

    try {
      setCreatingTestSet(true);
      const parsedContext = parseContextJson(values.contextJson || '');
      if (parsedContext.parseError) {
        message.error(parsedContext.parseError);
        return;
      }
      const data = await createValidationTestSet({
        name: String(values.name || '').trim(),
        description: String(values.description || '').trim(),
        querySelection: payload,
        ...(parsedContext.parsedContext === undefined
          ? {}
          : { config: { context: parsedContext.parsedContext } }),
      });
      message.success(`테스트 세트를 생성했습니다. (${data.itemCount}건)`);
      setCreateTestSetModalOpen(false);
      clearQuerySelection();
    } catch (error) {
      console.error(error);
      const detail = error instanceof AxiosError ? String(error.response?.data?.detail || '').trim() : '';
      if (detail) {
        message.error(`테스트 세트 생성에 실패했습니다. (${detail})`);
      } else {
        message.error('테스트 세트 생성에 실패했습니다.');
      }
    } finally {
      setCreatingTestSet(false);
    }
  };

  const handleAppendToTestSet = async (values: AppendToTestSetValues) => {
    const payload = toQuerySelectionPayload({
      mode: selectionMode,
      manualSelectedRowKeys,
      filteredSelectionSnapshot,
      filteredDeselectedIds,
    });
    if (!payload || selectedCount <= 0) {
      message.warning('선택된 질의가 없어요.');
      return;
    }

    const targetTestSetId = String(values.testSetId || '').trim();
    if (!targetTestSetId) {
      message.warning('추가할 테스트 세트를 선택해 주세요.');
      return;
    }

    try {
      setAppendingToTestSet(true);
      const result = await appendQueriesToValidationTestSet(targetTestSetId, {
        querySelection: payload,
      });
      message.success(`질의를 추가했습니다. (추가 ${result.addedCount}건, 중복 ${result.skippedCount}건)`);
      setAppendToTestSetModalOpen(false);
      clearQuerySelection();
    } catch (error) {
      console.error(error);
      const detail = error instanceof AxiosError ? String(error.response?.data?.detail || '').trim() : '';
      if (detail) {
        message.error(`테스트 세트 추가에 실패했습니다. (${detail})`);
      } else {
        message.error('테스트 세트 추가에 실패했습니다.');
      }
    } finally {
      setAppendingToTestSet(false);
    }
  };

  return {
    groups,
    items,
    total,
    loading,
    category,
    groupId,
    selectionMode,
    isFilteredSelectionLocked,
    selectedCount,
    filteredSelectionTotal,
    filteredDeselectedCount,
    tableSelectedRowKeys,
    canBulkDelete,
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
    bulkUpdateModalOpen,
    bulkUpdateFiles,
    bulkUpdatePreviewRows,
    bulkUpdatePreviewTotal,
    bulkUpdatePreviewEmptyText,
    bulkUpdatePreviewSummary,
    bulkUpdateGroupConfirmOpen,
    bulkUpdatePendingGroupNames,
    bulkUpdatePendingGroupRows,
    bulkUpdateUnmappedConfirmOpen,
    bulkUpdatePendingUnmappedCount,
    bulkUpdating,
    bulkDeleteModalOpen,
    setBulkDeleteModalOpen,
    bulkDeleting,
    createTestSetModalOpen,
    creatingTestSet,
    appendToTestSetModalOpen,
    appendingToTestSet,
    testSetOptionsLoading,
    testSetOptions,
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
    openBulkUpdateModal,
    closeBulkUpdateModal,
    closeBulkUpdateGroupConfirmModal,
    closeBulkUpdateUnmappedConfirmModal,
    handleBulkUpdateFileChange,
    handleBulkUpdate,
    confirmBulkUpdateWithGroupCreation,
    confirmBulkUpdateWithUnmappedSkip,
    handleDownloadBulkUpdateCsv,
    handleBulkDelete,
    handleSearch,
    handleCategoryChange,
    handleGroupChange,
    handleRowSelectionChange,
    handleSelectAllFiltered,
    clearQuerySelection,
    handleOpenCreateTestSetModal,
    handleOpenAppendToTestSetModal,
    handleCreateTestSetFromSelection,
    handleAppendToTestSet,
    closeCreateTestSetModal: () => setCreateTestSetModalOpen(false),
    closeAppendToTestSetModal: () => setAppendToTestSetModalOpen(false),
    loadQueries,
  };
}

export type { AppendToTestSetValues, CreateTestSetFromSelectionValues, QueryFormValues };
