import React, { useContext } from 'react';
import { Navigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

const ProtectedRoute = ({ children, allowedRoles }) => {
    const { user, loading } = useContext(AuthContext);

    if (loading) {
        return <div>Loading...</div>; // Could replace with a spinner component
    }

    if (!user) {
        return <Navigate to="/login" replace />;
    }

    if (allowedRoles && !allowedRoles.includes(user.role)) {
        // Redirect unauthorized users to the home page or a specific unauthorized page
        // For now, redirecting to home which usually has the dashboard or list
        // But if they are not allowed on dashboard, this might loop.
        // If customer tries to access admin dashboard, redirect to their ticket list?
        // Let's redirect to a safe default or show unauthorized message.
        return <div style={{ padding: '20px', color: 'red', fontFamily: 'monospace' }}>Unauthorized Access</div>;
    }

    return children;
};

export default ProtectedRoute;
