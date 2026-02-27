import { describe, expect, it } from 'vitest';
import { renderToString } from 'react-dom/server';

import { LoginPage } from '../LoginPage';

describe('login page', () => {
  it('renders official login copy', () => {
    const html = renderToString(
      <LoginPage
        environment="dev"
        loading={false}
        onEnvironmentChange={() => {}}
        onLogin={async () => {}}
      />,
    );

    expect(html).toContain('Agent QA Backoffice');
    expect(html).toContain('에이전트 검증 백오피스');
    expect(html).toContain('로그인');
  });

  it('renders local dev backdoor section when enabled', () => {
    const html = renderToString(
      <LoginPage
        environment="dev"
        loading={false}
        localDevBypassEnabled
        localDevBypassKey="local-key"
        onEnvironmentChange={() => {}}
        onLocalDevBypassKeyChange={() => {}}
        onLocalDevBypass={async () => {}}
        onLogin={async () => {}}
      />,
    );

    expect(html).toContain('로컬 개발 전용');
    expect(html).toContain('백도어키로 입장');
  });
});
