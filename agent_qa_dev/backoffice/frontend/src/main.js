import { jsx as _jsx } from "react/jsx-runtime";
import React from 'react';
import ReactDOM from 'react-dom/client';
import { App, ConfigProvider } from 'antd';
import { AppLayout } from './app/AppLayout.tsx';
import { appTheme } from './theme/theme.ts';
import './styles.css';
ReactDOM.createRoot(document.getElementById('root')).render(
  _jsx(React.StrictMode, {
    children: _jsx(
      ConfigProvider,
      {
        theme: appTheme,
        children: _jsx(
          App,
          {
            children: _jsx(AppLayout, {}),
          },
        ),
      },
    ),
  }),
);
