import React from 'react';
import ReactDOM from 'react-dom/client';
import { App, ConfigProvider } from 'antd';
import { BrowserRouter } from 'react-router-dom';

import { AppLayout } from './app/AppLayout';
import { appTheme } from './theme/theme';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider theme={appTheme}>
      <App>
        <BrowserRouter>
          <AppLayout />
        </BrowserRouter>
      </App>
    </ConfigProvider>
  </React.StrictMode>,
);
