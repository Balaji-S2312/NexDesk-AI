import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { AuthProvider } from './contexts/AuthContext';
import { ToastProvider } from './contexts/ToastContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppLayout } from './layouts/AppLayout';
import { useAuth } from './hooks/useAuth';

// Auth pages
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { VerifyEmail } from './pages/VerifyEmail';

// Employee & Shared pages
import { EmployeeOverview } from './pages/EmployeeOverview';
import { AISupport } from './pages/AISupport';
import { MyTickets } from './pages/MyTickets';
import { TicketDetails } from './pages/TicketDetails';
import { KnowledgeBase } from './pages/KnowledgeBase';
import { Notifications } from './pages/Notifications';
import { Profile } from './pages/Profile';

// Admin pages
import { AdminDashboard } from './pages/AdminDashboard';
import { AdminIncidents } from './pages/AdminIncidents';
import { AdminAssignmentGroups } from './pages/AdminAssignmentGroups';
import { AdminSLAManagement } from './pages/AdminSLAManagement';
import { AdminAuditLogs } from './pages/AdminAuditLogs';
import { AdminSettings } from './pages/AdminSettings';

// Dynamic root redirect based on user role
const RootRedirect = () => {
  const { user, isAdmin } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return isAdmin ? <AdminDashboard /> : <EmployeeOverview />;
};

export default function App() {
  return (
    <Router>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              {/* Public Auth Routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/verify-email" element={<VerifyEmail />} />

              {/* Authenticated Workspace wrapped in AppLayout */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  {/* Dynamic Root */}
                  <Route path="/" element={<RootRedirect />} />

                  {/* Employee / Shared Routes */}
                  <Route path="/ai-support" element={<AISupport />} />
                  <Route path="/my-tickets" element={<MyTickets />} />
                  <Route path="/tickets/:id" element={<TicketDetails />} />
                  <Route path="/notifications" element={<Notifications />} />
                  <Route path="/knowledge-base" element={<KnowledgeBase />} />
                  <Route path="/profile" element={<Profile />} />

                  {/* Admin Only Routes */}
                  <Route element={<ProtectedRoute requiredRole="admin" />}>
                    <Route path="/incidents" element={<AdminIncidents />} />
                    <Route path="/ai-assistant" element={<AISupport />} />
                    <Route path="/assignment-groups" element={<AdminAssignmentGroups />} />
                    <Route path="/sla-management" element={<AdminSLAManagement />} />
                    <Route path="/audit-logs" element={<AdminAuditLogs />} />
                    <Route path="/settings" element={<AdminSettings />} />
                  </Route>
                </Route>
              </Route>

              {/* Catch-all redirect */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </Router>
  );
}
