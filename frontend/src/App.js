import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { WorkspaceProvider } from './contexts/WorkspaceContext';

import LandingPage from './pages/LandingPage';
import SignIn from './pages/auth/SignIn';
import SignUp from './pages/auth/SignUp';
import ForgotPassword from './pages/auth/ForgotPassword';
import ResetPassword from './pages/auth/ResetPassword';
import VerifyEmail from './pages/auth/VerifyEmail';
import ResendVerification from './pages/auth/ResendVerification';

import SelectWorkspace from './pages/workspace/SelectWorkspace';
import CreateWorkspace from './pages/workspace/CreateWorkspace';

import OrganizerDashboard from './pages/dashboard/OrganizerDashboard';
import ParticipantDashboard from './pages/dashboard/ParticipantDashboard';

import AppointmentWizard from './pages/appointments/AppointmentWizard';
import AppointmentDetail from './pages/appointments/AppointmentDetail';
import ParticipantManagement from './pages/appointments/ParticipantManagement';

import AcceptInvitation from './pages/invitations/AcceptInvitation';
import InvitationPage from './pages/invitations/InvitationPage';

import PolicyTemplates from './pages/policies/PolicyTemplates';

import DisputeCenter from './pages/disputes/DisputeCenter';
import DisputeDetail from './pages/disputes/DisputeDetail';

import ReviewerDashboard from './pages/admin/ReviewerDashboard';

import AnalyticsOverview from './pages/analytics/AnalyticsOverview';

import Settings from './pages/settings/Settings';
import Profile from './pages/settings/Profile';
import WorkspaceSettings from './pages/settings/WorkspaceSettings';
import Integrations from './pages/settings/Integrations';

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
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/resend-verification" element={<ResendVerification />} />
              
              <Route path="/accept-invitation/:token" element={<AcceptInvitation />} />
              <Route path="/invitation/:token" element={<InvitationPage />} />
              
              <Route path="/workspace/select" element={<PrivateRoute><SelectWorkspace /></PrivateRoute>} />
              <Route path="/workspace/create" element={<PrivateRoute><CreateWorkspace /></PrivateRoute>} />
              
              <Route path="/dashboard" element={<PrivateRoute><OrganizerDashboard /></PrivateRoute>} />
              <Route path="/dashboard/participant" element={<PrivateRoute><ParticipantDashboard /></PrivateRoute>} />
              
              <Route path="/appointments/create" element={<PrivateRoute><AppointmentWizard /></PrivateRoute>} />
              <Route path="/appointments/:id" element={<PrivateRoute><AppointmentDetail /></PrivateRoute>} />
              <Route path="/appointments/:id/participants" element={<PrivateRoute><ParticipantManagement /></PrivateRoute>} />
              
              <Route path="/policies" element={<PrivateRoute><PolicyTemplates /></PrivateRoute>} />
              
              <Route path="/disputes" element={<PrivateRoute><DisputeCenter /></PrivateRoute>} />
              <Route path="/disputes/:id" element={<PrivateRoute><DisputeDetail /></PrivateRoute>} />
              
              <Route path="/admin/review" element={<PrivateRoute><ReviewerDashboard /></PrivateRoute>} />
              
              <Route path="/analytics" element={<PrivateRoute><AnalyticsOverview /></PrivateRoute>} />
              
              <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
              <Route path="/settings/profile" element={<PrivateRoute><Profile /></PrivateRoute>} />
              <Route path="/settings/workspace" element={<PrivateRoute><WorkspaceSettings /></PrivateRoute>} />
              <Route path="/settings/integrations" element={<PrivateRoute><Integrations /></PrivateRoute>} />
            </Routes>
            <Toaster />
          </div>
        </WorkspaceProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
