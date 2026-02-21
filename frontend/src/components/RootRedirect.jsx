import React, { useContext } from 'react';
import { Navigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

const RootRedirect = () => {
    const { user, loading } = useContext(AuthContext);

    if (loading) return <div style={{ padding: '20px', fontFamily: 'monospace' }}>Loading...</div>;
    if (!user) return <Navigate to="/login" replace />;

    if (user.role === 'admin') return <Navigate to="/admin" replace />;
    if (user.role === 'support_agent') return <Navigate to="/agent" replace />;

    // Default to customer dashboard
    return <Navigate to="/dashboard" replace />;
};

export default RootRedirect;
