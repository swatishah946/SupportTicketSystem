import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import Dashboard from './components/Dashboard';
import AdminDashboard from './components/AdminDashboard';
import ControllerDashboard from './components/ControllerDashboard';
import CustomerDashboard from './components/CustomerDashboard';
import TicketList from './components/TicketList';
import TicketDetail from './components/TicketDetail';
import TicketForm from './components/TicketForm';
import NavBar from './components/NavBar';
import ProtectedRoute from './components/ProtectedRoute';
import RootRedirect from './components/RootRedirect';
import { AuthProvider } from './context/AuthContext';
import { RealtimeProvider } from './context/RealtimeProvider';

function App() {
  return (
      <AuthProvider>
        <Router>
         <RealtimeProvider>
          <NavBar />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Root Intelligent Redirect */}
            <Route path="/" element={<RootRedirect />} />

            {/* Protected Routes */}
            <Route
              path="/admin"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <AdminDashboard />
                </ProtectedRoute>
              }
            />

            <Route
              path="/agent"
              element={
                <ProtectedRoute allowedRoles={['support_agent']}>
                  <ControllerDashboard />
                </ProtectedRoute>
              }
            />

            <Route
              path="/dashboard"
              element={
                <ProtectedRoute allowedRoles={['customer']}>
                  <CustomerDashboard />
                </ProtectedRoute>
              }
            />

            <Route
              path="/tickets"
              element={
                <ProtectedRoute allowedRoles={['admin', 'support_agent', 'customer']}>
                  <div className="page">
                    <div className="page-head"><h1>Tickets</h1></div>
                    <TicketList />
                  </div>
                </ProtectedRoute>
              }
            />

            <Route
              path="/tickets/:id"
              element={
                <ProtectedRoute allowedRoles={['admin', 'support_agent', 'customer']}>
                  <TicketDetail />
                </ProtectedRoute>
              }
            />

            <Route
              path="/new"
              element={
                <ProtectedRoute allowedRoles={['admin', 'support_agent', 'customer']}>
                  <TicketForm />
                </ProtectedRoute>
              }
            />

            {/* Fallback route */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
         </RealtimeProvider>
        </Router>
      </AuthProvider>
  );
}

export default App;
