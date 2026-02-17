import { Input, Select, Space } from 'antd';

import type { QueryGroup } from '../../../api/types/validation';
import { CATEGORY_OPTIONS } from '../constants';

export function QueryFilters({
  category,
  groupId,
  groups,
  onSearch,
  onCategoryChange,
  onGroupChange,
}: {
  category: string[];
  groupId: string[];
  groups: QueryGroup[];
  onSearch: (value: string) => void;
  onCategoryChange: (value: string[] | undefined) => void;
  onGroupChange: (value: string[] | undefined) => void;
}) {
  return (
    <Space wrap>
      <Input.Search placeholder="질의 검색" allowClear style={{ width: 240 }} onSearch={onSearch} enterButton />
      <Select
        mode="multiple"
        allowClear
        placeholder="카테고리"
        options={CATEGORY_OPTIONS}
        value={Array.isArray(category) ? category : []}
        onChange={(value) => onCategoryChange(value)}
        showSearch={false}
        maxTagCount="responsive"
        style={{ width: 240 }}
      />
      <Select
        mode="multiple"
        allowClear
        placeholder="그룹"
        options={groups.map((group) => ({ label: group.groupName, value: group.id }))}
        value={Array.isArray(groupId) ? groupId : []}
        onChange={(value) => onGroupChange(value)}
        showSearch
        optionFilterProp="label"
        listHeight={32 * 5}
        maxTagCount="responsive"
        style={{ width: 280 }}
      />
    </Space>
  );
}
