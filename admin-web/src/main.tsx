import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#5c72f2', borderRadius: 10, fontFamily: 'Inter, PingFang SC, Microsoft YaHei, sans-serif' } }}>
      <App />
    </ConfigProvider>
  </React.StrictMode>
)
