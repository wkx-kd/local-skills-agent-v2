import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import LoginPage from './pages/LoginPage';
import ChatPage from './pages/ChatPage';
import SkillsPage from './pages/SkillsPage';
import { useAuthStore } from './stores/authStore';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <ConfigProvider 
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#8ab4f8',
          colorBgBase: '#131314',
          colorBgContainer: '#1e1f20',
          colorBgElevated: '#1e1f20',
          colorBorder: '#444746',
          borderRadius: 24,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <PrivateRoute>
                <ChatPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/skills"
            element={
              <PrivateRoute>
                <SkillsPage />
              </PrivateRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
