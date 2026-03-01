const VERSION_LABEL_REGEX = /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/;

export function isValidEvalPromptVersionLabel(value: string): boolean {
  return VERSION_LABEL_REGEX.test(String(value || '').trim());
}

export function getEvalPromptVersionValidationMessage(value: string): string {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '버전 라벨을 입력해 주세요.';
  }
  if (!isValidEvalPromptVersionLabel(normalized)) {
    return '버전 라벨 형식이 올바르지 않습니다. (영문/숫자/._- , 최대 80자)';
  }
  return '';
}
