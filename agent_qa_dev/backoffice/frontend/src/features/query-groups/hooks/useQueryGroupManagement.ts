import { useEffect, useState } from 'react';
import { Form } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';
import { AxiosError } from 'axios';

import { createQueryGroup, deleteQueryGroup, listQueryGroups, updateQueryGroup } from '../../../api/validation';
import type { QueryGroup } from '../../../api/types/validation';
import type { Environment } from '../../../app/EnvironmentScope';
import type { RuntimeSecrets } from '../../../app/types';
import { getRequestErrorMessage } from '../../../shared/utils/error';

type QueryGroupFormValues = {
  groupName: string;
  description: string;
};

export function useQueryGroupManagement({
  environment,
  tokens,
  message,
}: {
  environment: Environment;
  tokens: RuntimeSecrets;
  message: MessageInstance;
}) {
  const [items, setItems] = useState<QueryGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<QueryGroup | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<QueryGroupFormValues>();

  const load = async () => {
    setLoading(true);
    try {
      const data = await listQueryGroups({ q: search || undefined, limit: 200 });
      setItems(data.items);
      setTotal(data.total);
    } catch (error) {
      message.error('그룹 목록 조회에 실패했습니다.');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [search, environment, tokens.bearer, tokens.cms, tokens.mrs]);

  const openCreate = () => {
    setEditing(null);
    form.setFieldsValue({ groupName: '', description: '' });
    setModalOpen(true);
  };

  const openEdit = (group: QueryGroup) => {
    setEditing(group);
    form.setFieldsValue({ groupName: group.groupName, description: group.description });
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      if (editing) {
        await updateQueryGroup(editing.id, {
          groupName: values.groupName,
          description: values.description,
        });
        message.success('그룹을 수정했습니다.');
      } else {
        await createQueryGroup({
          groupName: values.groupName,
          description: values.description,
        });
        message.success('그룹을 생성했습니다.');
      }
      setModalOpen(false);
      await load();
    } catch (error) {
      if (error instanceof Error) {
        console.error(error);
      }
      message.error('그룹 저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (groupId: string) => {
    try {
      await deleteQueryGroup(groupId);
      message.success('그룹을 삭제했습니다.');
      await load();
    } catch (error) {
      if (error instanceof AxiosError && error.response?.status === 409) {
        message.error('질의가 연결된 그룹은 삭제할 수 없습니다. 질의를 이동/삭제한 뒤 다시 시도하세요.');
        return;
      }
      const reason = getRequestErrorMessage(error, '');
      if (reason.trim()) {
        message.error(`그룹 삭제에 실패했습니다. (${reason})`);
      } else {
        message.error('그룹 삭제에 실패했습니다.');
      }
      console.error(error);
    }
  };

  return {
    items,
    total,
    loading,
    search,
    setSearch,
    modalOpen,
    setModalOpen,
    editing,
    saving,
    form,
    openCreate,
    openEdit,
    handleSave,
    handleDelete,
  };
}

export type { QueryGroupFormValues };
