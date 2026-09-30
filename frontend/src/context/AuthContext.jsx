import React, { useCallback, useEffect, useState } from 'react';
import api from '../api';
import { AuthContext } from './auth';

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    // The session is the httpOnly cookie: ask the server who we are.
    const refreshUser = useCallback(async () => {
        try {
            const response = await api.get('/auth/user/');
            setUser(response.data);
        } catch {
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refreshUser();
    }, [refreshUser]);

    const login = (userData) => setUser(userData);

    const logout = async () => {
        try {
            await api.post('/auth/logout/');
        } catch (error) {
            console.error('Logout failed', error);
        } finally {
            setUser(null);
            window.location.href = '/login';
        }
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
            {children}
        </AuthContext.Provider>
    );
};
