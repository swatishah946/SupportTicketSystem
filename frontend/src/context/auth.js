import { createContext } from 'react';

export const AuthContext = createContext(null);

export const homeFor = (role) =>
    role === 'admin' ? '/admin' : role === 'support_agent' ? '/agent' : '/dashboard';
