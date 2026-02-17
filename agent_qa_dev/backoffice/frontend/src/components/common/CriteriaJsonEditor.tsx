import { Input } from 'antd';

export function CriteriaJsonEditor({
  value,
  onChange,
  placeholder,
}: {
  value?: string;
  onChange?: (next: string) => void;
  placeholder?: string;
}) {
  return (
    <Input.TextArea
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
      autoSize={{ minRows: 4, maxRows: 10 }}
      placeholder={placeholder || '{"version":1,"metrics":[{"key":"accuracy","weight":0.4}]}'}
    />
  );
}
