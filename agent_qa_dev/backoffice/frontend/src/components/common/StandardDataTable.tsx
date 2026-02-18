import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  type ThHTMLAttributes,
} from 'react';

import { Table } from 'antd';
import type { ColumnGroupType, ColumnsType, ColumnType, TablePaginationConfig, TableProps } from 'antd/es/table';
import { useStandardPaginationConfig } from './standardPaginationConfig';

const STANDARD_DEFAULT_PAGE_SIZE = 50;
const STANDARD_PAGE_SIZE_OPTIONS = [20, 50, 100];
const DEFAULT_RESIZABLE_COLUMN_WIDTH = 180;
const DEFAULT_MIN_COLUMN_WIDTH = 120;

type StandardDataTableProps<RecordType extends object> = Omit<TableProps<RecordType>, 'columns' | 'pagination'> & {
  columns?: ColumnsType<RecordType>;
  pagination?: TableProps<RecordType>['pagination'];
  wrapperClassName?: string;
  wrapperStyle?: CSSProperties;
  tableId?: string;
  resizable?: boolean;
  defaultResizableColumnWidth?: number;
  minColumnWidth?: number;
  minColumnWidths?: Record<string, number>;
  initialColumnWidths?: Record<string, number>;
  scrollXPadding?: number;
  useStandardPagination?: boolean;
};

type ResizableHeaderCellProps = ThHTMLAttributes<HTMLTableCellElement> & {
  children?: ReactNode;
  onResizeStart?: (event: ReactMouseEvent<HTMLSpanElement>) => void;
};

type ResizeState = {
  columnKey: string;
  startX: number;
  startWidth: number;
} | null;

type LeafColumnMeta = {
  key: string;
  width: number;
  minWidth: number;
};

function joinClassNames(...classNames: Array<string | undefined>) {
  return classNames.filter(Boolean).join(' ');
}

function normalizeColumnKey(dataIndex: ColumnType<unknown>['dataIndex']) {
  if (Array.isArray(dataIndex)) return dataIndex.map((item) => String(item)).join('.');
  if (typeof dataIndex === 'string' || typeof dataIndex === 'number') return String(dataIndex);
  return '';
}

function resolveColumnKey<RecordType extends object>(column: ColumnType<RecordType>, index: number, path: string) {
  if (column.key !== undefined && column.key !== null) return String(column.key);
  const fromDataIndex = normalizeColumnKey(column.dataIndex);
  if (fromDataIndex) return fromDataIndex;
  return `${path || 'col'}-${index}`;
}

function hasChildren<RecordType extends object>(
  column: ColumnType<RecordType> | ColumnGroupType<RecordType>,
): column is ColumnGroupType<RecordType> {
  return 'children' in column && Array.isArray(column.children) && column.children.length > 0;
}

function collectLeafColumnMeta<RecordType extends object>({
  columns,
  defaultWidth,
  minColumnWidth,
  minColumnWidths,
  initialColumnWidths,
}: {
  columns?: ColumnsType<RecordType>;
  defaultWidth: number;
  minColumnWidth: number;
  minColumnWidths: Record<string, number>;
  initialColumnWidths: Record<string, number>;
}) {
  const result: LeafColumnMeta[] = [];
  if (!columns?.length) return result;

  const traverse = (input: ColumnsType<RecordType>, path: string) => {
    input.forEach((column, index) => {
      const key = resolveColumnKey(column, index, path);
      if (hasChildren(column)) {
        traverse(column.children, key);
        return;
      }

      const rawWidth = initialColumnWidths[key] ?? (typeof column.width === 'number' ? column.width : defaultWidth);
      const minWidth = minColumnWidths[key] ?? minColumnWidth;
      result.push({
        key,
        width: Math.max(minWidth, rawWidth),
        minWidth,
      });
    });
  };

  traverse(columns, '');
  return result;
}

function sumLeafColumnWidth<RecordType extends object>(columns?: ColumnsType<RecordType>): number {
  if (!columns?.length) return 0;
  return columns.reduce((acc, column) => {
    if (hasChildren(column)) {
      return acc + sumLeafColumnWidth(column.children);
    }
    if (typeof column.width === 'number' && Number.isFinite(column.width)) {
      return acc + column.width;
    }
    return acc;
  }, 0);
}

function ResizableHeaderCell({
  onResizeStart,
  children,
  ...restProps
}: ResizableHeaderCellProps) {
  if (!onResizeStart) {
    return <th {...restProps}>{children}</th>;
  }
  return (
    <th {...restProps}>
      <div className="query-table-header-cell">
        <span className="query-table-header-title">{children}</span>
        <span
          className="query-table-resize-handle"
          role="separator"
          aria-label="컬럼 너비 조절"
          onClick={(event) => event.stopPropagation()}
          onMouseDown={onResizeStart}
        />
      </div>
    </th>
  );
}

function buildStandardPagination(
  pagination: TableProps<unknown>['pagination'],
  useStandardPagination: boolean,
  pageSizeLimit: number,
): TableProps<unknown>['pagination'] {
  if (!useStandardPagination) return pagination;
  if (pagination === false) return false;

  const normalizePositiveInt = (value: unknown) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) return null;
    return Math.trunc(parsed);
  };

  const normalizePageSizeOptions = (rawOptions: TablePaginationConfig['pageSizeOptions'], limit: number) => {
    const source = rawOptions ?? STANDARD_PAGE_SIZE_OPTIONS;
    const normalized = new Set<number>();
    source.forEach((option) => {
      const parsed = normalizePositiveInt(option);
      if (!parsed || parsed > limit) return;
      normalized.add(parsed);
    });
    normalized.add(limit);
    return Array.from(normalized).sort((left, right) => left - right);
  };

  const normalizePageSize = (value: unknown, limit: number) => {
    const parsed = normalizePositiveInt(value);
    if (!parsed) return undefined;
    return Math.min(parsed, limit);
  };

  const resolveAllViewPageSize = (total: unknown, limit: number) => {
    const parsedTotal = normalizePositiveInt(total);
    if (!parsedTotal) return limit;
    return Math.min(parsedTotal, limit);
  };

  const raw: TablePaginationConfig = pagination ?? {};
  const normalizedPageSizeLimit = Math.max(1, Math.trunc(pageSizeLimit));
  const normalizedPageSizeOptions = normalizePageSizeOptions(raw.pageSizeOptions, normalizedPageSizeLimit);
  const allViewPageSize = resolveAllViewPageSize(raw.total, normalizedPageSizeLimit);
  const selectOptions = [
    ...normalizedPageSizeOptions
      .filter((option) => option !== allViewPageSize)
      .map((option) => ({ label: `${option}개 보기`, value: option })),
    { label: '전체 보기', value: allViewPageSize },
  ];
  const showSizeChanger = raw.showSizeChanger ?? true;
  const mergedShowSizeChanger =
    showSizeChanger === false
      ? false
      : ({
        ...(typeof showSizeChanger === 'object' ? showSizeChanger : {}),
        options: selectOptions,
      } as NonNullable<TablePaginationConfig['showSizeChanger']>);

  const merged: TablePaginationConfig = {
    ...raw,
    position: raw.position ?? ['bottomCenter'],
    showSizeChanger: mergedShowSizeChanger,
    pageSizeOptions: selectOptions.map((option) => String(option.value)),
    showTotal:
      raw.showTotal ??
      ((total, range) => {
        if (!range?.length || total === 0) return `0 / ${total}개`;
        return `${range[0]}-${range[1]} / ${total}개`;
      }),
  };

  const normalizedPageSize = normalizePageSize(raw.pageSize, normalizedPageSizeLimit);
  if (normalizedPageSize !== undefined) {
    merged.pageSize = normalizedPageSize;
  }

  const normalizedDefaultPageSize = normalizePageSize(raw.defaultPageSize, normalizedPageSizeLimit);
  if (normalizedDefaultPageSize !== undefined) {
    merged.defaultPageSize = normalizedDefaultPageSize;
  }

  if (raw.pageSize === undefined && raw.defaultPageSize === undefined) {
    merged.defaultPageSize = Math.min(STANDARD_DEFAULT_PAGE_SIZE, normalizedPageSizeLimit);
  }

  return merged;
}

export function StandardDataTable<RecordType extends object = Record<string, unknown>>({
  columns,
  pagination,
  wrapperClassName,
  wrapperStyle,
  className,
  tableId,
  resizable = true,
  defaultResizableColumnWidth = DEFAULT_RESIZABLE_COLUMN_WIDTH,
  minColumnWidth = DEFAULT_MIN_COLUMN_WIDTH,
  minColumnWidths,
  initialColumnWidths,
  scrollXPadding = 0,
  useStandardPagination = true,
  components,
  scroll,
  ...tableProps
}: StandardDataTableProps<RecordType>) {
  const { pageSizeLimit } = useStandardPaginationConfig();
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const [resizeState, setResizeState] = useState<ResizeState>(null);
  const loadedStorageKeyRef = useRef<string | null>(null);

  const storageKey = tableId ? `aqb.standard.table.column.widths.${tableId}` : undefined;
  const minWidthMap = minColumnWidths ?? {};
  const initialWidthMap = initialColumnWidths ?? {};
  const hasCustomHeaderCell = Boolean(components?.header && 'cell' in components.header && components.header.cell);
  const enableResizable = resizable && !hasCustomHeaderCell && Boolean(columns?.length);

  const leafColumnMeta = useMemo(
    () =>
      collectLeafColumnMeta<RecordType>({
        columns,
        defaultWidth: defaultResizableColumnWidth,
        minColumnWidth,
        minColumnWidths: minWidthMap,
        initialColumnWidths: initialWidthMap,
      }),
    [columns, defaultResizableColumnWidth, minColumnWidth, minWidthMap, initialWidthMap],
  );

  useEffect(() => {
    if (!enableResizable) return;
    setColumnWidths((prev) => {
      const next = { ...prev };
      let changed = false;
      const validKeys = new Set<string>();

      leafColumnMeta.forEach((meta) => {
        validKeys.add(meta.key);
        const current = next[meta.key];
        if (typeof current !== 'number' || !Number.isFinite(current)) {
          next[meta.key] = meta.width;
          changed = true;
          return;
        }
        const clamped = Math.max(meta.minWidth, current);
        if (clamped !== current) {
          next[meta.key] = clamped;
          changed = true;
        }
      });

      Object.keys(next).forEach((key) => {
        if (validKeys.has(key)) return;
        delete next[key];
        changed = true;
      });

      return changed ? next : prev;
    });
  }, [enableResizable, leafColumnMeta]);

  useEffect(() => {
    if (!enableResizable || !storageKey || typeof window === 'undefined') return;
    if (loadedStorageKeyRef.current === storageKey) return;

    loadedStorageKeyRef.current = storageKey;
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Record<string, number>;
      setColumnWidths((prev) => {
        const next = { ...prev };
        let changed = false;
        leafColumnMeta.forEach((meta) => {
          const saved = parsed[meta.key];
          if (typeof saved !== 'number' || !Number.isFinite(saved)) return;
          const clamped = Math.max(meta.minWidth, saved);
          if (next[meta.key] !== clamped) {
            next[meta.key] = clamped;
            changed = true;
          }
        });
        return changed ? next : prev;
      });
    } catch (error) {
      console.error(error);
    }
  }, [enableResizable, storageKey, leafColumnMeta]);

  useEffect(() => {
    if (!enableResizable || !storageKey || typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(columnWidths));
    } catch (error) {
      console.error(error);
    }
  }, [enableResizable, storageKey, columnWidths]);

  useEffect(() => {
    if (!resizeState) return;
    const minWidth = minWidthMap[resizeState.columnKey] ?? minColumnWidth;
    const handleMouseMove = (event: MouseEvent) => {
      const delta = event.clientX - resizeState.startX;
      const nextWidth = Math.max(minWidth, resizeState.startWidth + delta);
      setColumnWidths((prev) => ({
        ...prev,
        [resizeState.columnKey]: nextWidth,
      }));
    };
    const stopResize = () => setResizeState(null);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', stopResize);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', stopResize);
    };
  }, [resizeState, minWidthMap, minColumnWidth]);

  useEffect(() => {
    if (!resizeState) return;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
    };
  }, [resizeState]);

  const handleResizeStart = useCallback(
    (columnKey: string) => (event: ReactMouseEvent<HTMLSpanElement>) => {
      event.preventDefault();
      event.stopPropagation();
      const startWidth = columnWidths[columnKey] ?? minWidthMap[columnKey] ?? minColumnWidth;
      setResizeState({
        columnKey,
        startX: event.clientX,
        startWidth,
      });
    },
    [columnWidths, minWidthMap, minColumnWidth],
  );

  const enhancedColumns = useMemo<ColumnsType<RecordType>>(() => {
    if (!columns?.length || !enableResizable) return columns ?? [];
    const widthMap = new Map(leafColumnMeta.map((meta) => [meta.key, meta]));

    const traverse = (input: ColumnsType<RecordType>, path: string): ColumnsType<RecordType> =>
      input.map((column, index) => {
        const key = resolveColumnKey(column, index, path);
        if (hasChildren(column)) {
          return {
            ...column,
            children: traverse(column.children, key),
          };
        }

        const meta = widthMap.get(key);
        const fallbackWidth = meta?.width ?? defaultResizableColumnWidth;
        const minWidth = meta?.minWidth ?? minColumnWidth;
        const nextWidth = Math.max(minWidth, columnWidths[key] ?? fallbackWidth);
        const baseOnHeaderCell = column.onHeaderCell;

        return {
          ...column,
          width: nextWidth,
          onHeaderCell: (record) => {
            const baseCellProps = typeof baseOnHeaderCell === 'function' ? baseOnHeaderCell(record) : {};
            return {
              ...(baseCellProps || {}),
              onResizeStart: handleResizeStart(key),
            };
          },
        };
      });

    return traverse(columns, '');
  }, [
    columns,
    enableResizable,
    leafColumnMeta,
    defaultResizableColumnWidth,
    minColumnWidth,
    columnWidths,
    handleResizeStart,
  ]);

  const mergedComponents = useMemo(() => {
    if (!enableResizable) return components;
    return {
      ...components,
      header: {
        ...(components?.header || {}),
        cell: ResizableHeaderCell,
      },
    };
  }, [components, enableResizable]);

  const tableWidth = useMemo(() => sumLeafColumnWidth(enhancedColumns), [enhancedColumns]);
  const mergedScroll = useMemo(() => {
    if (!enableResizable) return scroll;
    const computedX = tableWidth > 0 ? tableWidth + scrollXPadding : undefined;
    if (!computedX) return scroll;

    if (!scroll) {
      return { x: computedX };
    }

    if (typeof scroll === 'object') {
      if (typeof scroll.x === 'number') {
        return { ...scroll, x: Math.max(scroll.x, computedX) };
      }
      if (scroll.x === undefined) {
        return { ...scroll, x: computedX };
      }
    }

    return scroll;
  }, [enableResizable, scroll, tableWidth, scrollXPadding]);

  const mergedPagination = useMemo(
    () => buildStandardPagination(pagination as TableProps<unknown>['pagination'], useStandardPagination, pageSizeLimit),
    [pagination, useStandardPagination, pageSizeLimit],
  );

  return (
    <div className={joinClassNames('standard-data-table-wrap', wrapperClassName)} style={wrapperStyle}>
      <Table<RecordType>
        {...tableProps}
        className={joinClassNames('standard-data-table', className)}
        columns={enhancedColumns}
        components={mergedComponents}
        pagination={mergedPagination as TableProps<RecordType>['pagination']}
        scroll={mergedScroll}
      />
    </div>
  );
}
