import { Button, Space, Typography, Upload } from 'antd';
import { DownloadOutlined, UploadOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';

import { StandardDataTable } from '../../../components/common/StandardDataTable';
import { StandardModal } from '../../../components/common/StandardModal';
import { api } from '../../../api/client';
import { BULK_UPLOAD_EMPTY_TEXT, BULK_UPLOAD_PREVIEW_COLUMNS, BULK_UPLOAD_PREVIEW_LIMIT } from '../constants';
import type { UploadPreviewRow } from '../types';

export function BulkUploadModal({
  open,
  files,
  previewRows,
  previewTotal,
  previewEmptyText,
  uploading,
  onClose,
  onFilesChange,
  onUpload,
}: {
  open: boolean;
  files: UploadFile[];
  previewRows: UploadPreviewRow[];
  previewTotal: number;
  previewEmptyText: string;
  uploading: boolean;
  onClose: () => void;
  onFilesChange: (fileList: UploadFile[]) => void;
  onUpload: () => void;
}) {
  const handleDownloadTemplate = () => {
    const downloadUrl = `${api.defaults.baseURL}/queries/template?ts=${Date.now()}`;
    window.open(downloadUrl, '_blank');
  };

  return (
    <StandardModal
      title="대규모 업로드"
      open={open}
      width={860}
      onCancel={onClose}
      footer={
        <Space>
          <Button onClick={onClose} disabled={uploading}>
            취소
          </Button>
          <Button type="primary" loading={uploading} disabled={!files[0]?.originFileObj} onClick={onUpload}>
            업로드
          </Button>
        </Space>
      }
    >
      <div style={{ width: '100%', padding: 0, display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto' }}>
        <Typography.Text type="secondary">CSV 템플릿을 다운받아 사용해 주세요.</Typography.Text>

        <div>
          <Typography.Text>질의 템플릿</Typography.Text>
          <div style={{ marginTop: 8 }}>
            <Button icon={<DownloadOutlined />} onClick={handleDownloadTemplate}>
              템플릿 다운로드
            </Button>
          </div>
        </div>

        <div>
          <Typography.Text>CSV 업로드</Typography.Text>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Upload
              fileList={files}
              beforeUpload={() => false}
              onChange={({ fileList }) => {
                onFilesChange(fileList);
              }}
              maxCount={1}
              accept=".csv,.xlsx,.xls"
              showUploadList={false}
            >
              <Button icon={<UploadOutlined />}>질의 업로드</Button>
            </Upload>
            {files[0]?.name ? <Typography.Text type="secondary">{files[0].name}</Typography.Text> : null}
          </div>
        </div>

        <div>
          <Typography.Text>업로드한 질의 미리보기</Typography.Text>
          <div style={{ marginTop: 8 }}>
            {files.length === 0 ? (
              <Typography.Text type="secondary">{BULK_UPLOAD_EMPTY_TEXT}</Typography.Text>
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size={8}>
                <StandardDataTable
                  tableId="query-management-upload-preview"
                  className="query-management-table"
                  rowKey="key"
                  size="small"
                  columns={BULK_UPLOAD_PREVIEW_COLUMNS}
                  dataSource={previewRows}
                  tableLayout="fixed"
                  pagination={false}
                  scroll={{ x: 780, y: 280 }}
                  locale={{ emptyText: previewEmptyText }}
                />
                {previewTotal > BULK_UPLOAD_PREVIEW_LIMIT ? (
                  <Typography.Text type="secondary">
                    총 {previewTotal}건 중 {BULK_UPLOAD_PREVIEW_LIMIT}건만 표시됩니다.
                  </Typography.Text>
                ) : null}
                <Typography.Text type="secondary">CSV의 그룹 값이 비어 있으면 그룹 미지정으로 등록됩니다.</Typography.Text>
              </Space>
            )}
          </div>
        </div>
      </div>
    </StandardModal>
  );
}
