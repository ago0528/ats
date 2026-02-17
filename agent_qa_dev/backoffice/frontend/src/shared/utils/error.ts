export function getRequestErrorMessage(error: unknown, fallback = '요청 처리 중 오류가 발생했습니다.') {
  if (
    typeof error === 'object'
    && error !== null
    && 'response' in error
    && typeof (error as { response?: unknown }).response === 'object'
    && (error as { response?: { data?: unknown } }).response !== null
  ) {
    const response = (error as { response?: { data?: unknown } }).response;

    if (typeof response?.data === 'string' && response.data.trim()) {
      return response.data;
    }

    if (
      typeof response?.data === 'object'
      && response.data !== null
      && 'detail' in response.data
      && typeof (response.data as { detail?: unknown }).detail === 'string'
      && (response.data as { detail?: string }).detail?.trim()
    ) {
      return (response.data as { detail: string }).detail;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}
