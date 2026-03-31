import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { WorkspaceProvider } from './contexts/WorkspaceContext';

import PermissionGuard from './components/PermissionGuard';

import LandingPage from './pages/LandingPage';
import SignIn from './pages/auth/SignIn';
import SignUp from './pages/auth/SignUp';
import AuthCallback from './pages/auth/AuthCallback';
import ForgotPassword from './pages/auth/ForgotPassword';
import ResetPassword from './pages/auth/ResetPassword';
import VerifyEmail from './pages/auth/VerifyEmail';
import ResendVerification from './pages/auth/ResendVerification';

import SelectWorkspace from './pages/workspace/SelectWorkspace';
import CreateWorkspace from './pages/workspace/CreateWorkspace';

import OrganizerDashboard from './pages/dashboard/OrganizerDashboard';
import AgendaPage from './pages/agenda/AgendaPage';
import ParticipantDashboard from './pages/dashboard/ParticipantDashboard';

import AppointmentWizard from './pages/appointments/AppointmentWizard';
import AppointmentDetail from './pages/appointments/AppointmentDetail';
import ParticipantManagement from './pages/appointments/ParticipantManagement';

import InvitationPage from './pages/invitations/InvitationPage';
import CheckinPage from './pages/proof/CheckinPage';

import DisputesListPage from './pages/disputes/DisputesListPage';
import DisputeDetailPage from './pages/disputes/DisputeDetailPage';
import DecisionDetailPage from './pages/decisions/DecisionDetailPage';
import DecisionsListPage from './pages/decisions/DecisionsListPage';
import AttendanceSheetPage from './pages/declarations/AttendanceSheetPage';
import PresencesPage from './pages/declarations/PresencesPage';

import AdminDashboard from './pages/admin/AdminDashboard';
import AdminArbitrationList from './pages/admin/AdminArbitrationList';
import AdminArbitrationDetail from './pages/admin/AdminArbitrationDetail';
import AdminAssociations from './pages/admin/AdminAssociations';
import AdminUsers from './pages/admin/AdminUsers';
import AdminPayouts from './pages/admin/AdminPayouts';
import AdminStalePayouts from './pages/admin/AdminStalePayouts';

import Settings from './pages/settings/Settings';
import Profile from './pages/settings/Profile';
import WorkspaceSettings from './pages/settings/WorkspaceSettings';
import Integrations from './pages/settings/Integrations';
import PaymentSettings from './pages/settings/PaymentSettings';
import WalletPage from './pages/settings/WalletPage';
import StatisticsPage from './pages/settings/StatisticsPage';
import ImpactPage from './pages/ImpactPage';
import FinancialResultsPage from './pages/FinancialResultsPage';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900"></div>
    </div>;
  }
  
  return user ? children : <Navigate to="/signin" />;
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <WorkspaceProvider>
          <div className="App">
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/signin" element={<SignIn />} />
              <Route path="/signup" element={<SignUp />} />
              <Route path="/auth/callback" element={<AuthCallback />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/resend-verification" element={<ResendVerification />} />
              
              <Route path="/invitation/:token" element={<InvitationPage />} />
              <Route path="/proof/:appointmentId" element={<CheckinPage />} />
              <Route path="/impact" element={<ImpactPage />} />
              
              <Route path="/workspace/select" element={<PrivateRoute><SelectWorkspace /></PrivateRoute>} />
              <Route path="/workspace/create" element={<PrivateRoute><CreateWorkspace /></PrivateRoute>} />
              
              <Route path="/dashboard" element={<PrivateRoute><OrganizerDashboard /></PrivateRoute>} />
              <Route path="/agenda" element={<PrivateRoute><AgendaPage /></PrivateRoute>} />
              <Route path="/dashboard/participant" element={<PrivateRoute><ParticipantDashboard /></PrivateRoute>} />
              
              <Route path="/appointments/create" element={<PrivateRoute><AppointmentWizard /></PrivateRoute>} />
              <Route path="/appointments/:id" element={<PrivateRoute><AppointmentDetail /></PrivateRoute>} />
              <Route path="/appointments/:id/participants" element={<PrivateRoute><ParticipantManagement /></PrivateRoute>} />
              
              <Route path="/presences" element={<PrivateRoute><PresencesPage /></PrivateRoute>} />
              <Route path="/litiges" element={<PrivateRoute><DisputesListPage /></PrivateRoute>} />
              <Route path="/litiges/:id" element={<PrivateRoute><DisputeDetailPage /></PrivateRoute>} />
              <Route path="/decisions" element={<PrivateRoute><DecisionsListPage /></PrivateRoute>} />
              <Route path="/decisions/:disputeId" element={<PrivateRoute><DecisionDetailPage /></PrivateRoute>} />
              <Route path="/appointments/:id/attendance-sheet" element={<PrivateRoute><AttendanceSheetPage /></PrivateRoute>} />
              
              <Route path="/admin" element={<PrivateRoute><AdminDashboard /></PrivateRoute>} />
              <Route path="/admin/review" element={<Navigate to="/admin" replace />} />
              <Route path="/admin/arbitration" element={<PrivateRoute><PermissionGuard permission="admin:arbitration"><AdminArbitrationList /></PermissionGuard></PrivateRoute>} />
              <Route path="/admin/arbitration/:disputeId" element={<PrivateRoute><PermissionGuard permission="admin:arbitration"><AdminArbitrationDetail /></PermissionGuard></PrivateRoute>} />
              <Route path="/admin/associations" element={<PrivateRoute><PermissionGuard permission="admin:associations"><AdminAssociations /></PermissionGuard></PrivateRoute>} />
              <Route path="/admin/payouts" element={<PrivateRoute><PermissionGuard permission="admin:payouts"><AdminPayouts /></PermissionGuard></PrivateRoute>} />
              <Route path="/admin/stale-payouts" element={<PrivateRoute><PermissionGuard permission="admin:stale-payouts"><AdminStalePayouts /></PermissionGuard></PrivateRoute>} />
              <Route path="/admin/users" element={<PrivateRoute><PermissionGuard permission="admin:users"><AdminUsers /></PermissionGuard></PrivateRoute>} />
              
              <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
              <Route path="/settings/profile" element={<PrivateRoute><Profile /></PrivateRoute>} />
              <Route path="/settings/workspace" element={<PrivateRoute><WorkspaceSettings /></PrivateRoute>} />
              <Route path="/settings/integrations" element={<PrivateRoute><Integrations /></PrivateRoute>} />
              <Route path="/settings/payment" element={<PrivateRoute><PaymentSettings /></PrivateRoute>} />
              <Route path="/settings/statistics" element={<PrivateRoute><StatisticsPage /></PrivateRoute>} />
              <Route path="/wallet" element={<PrivateRoute><WalletPage /></PrivateRoute>} />
              <Route path="/settings/wallet" element={<Navigate to="/wallet" replace />} />
              <Route path="/mes-resultats" element={<PrivateRoute><FinancialResultsPage /></PrivateRoute>} />
            </Routes>
            <Toaster />
          </div>
        </WorkspaceProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
