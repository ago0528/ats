import { Select } from 'antd';

export type Environment = 'dev' | 'st2' | 'st' | 'pr';

export const ENV_OPTIONS = [
  { label: 'DV 환경', value: 'dev' },
  { label: 'QA 환경', value: 'st2' },
  { label: 'STG 환경', value: 'st' },
  { label: 'PR 환경', value: 'pr' },
];

type Props = {
  value: Environment;
  onChange: (next: Environment) => void;
  controlHeight?: number;
};

export function EnvironmentScope({ value, onChange, controlHeight }: Props) {
  return (
    <Select
      options={ENV_OPTIONS}
      value={value}
      size="middle"
      style={{ width: 160, height: controlHeight, minHeight: controlHeight }}
      onChange={(v) => onChange(v as Environment)}
    />
  );
}
