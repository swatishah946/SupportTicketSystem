import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';
import { notificationFor } from '../lib/notify';
import { AuthContext } from './auth';
import { RealtimeContext } from './realtime';

const UNAUTHORIZED = 4401; // server: token missing or expired
const MAX_BACKOFF_MS = 30000;

/**
 * Keeps one WebSocket open while the user is logged in.
 * - Reconnects with exponential backoff (1s, 2s, 4s ... 30s) if the connection drops.
 * - On code 4401 it refreshes the login cookie first, then reconnects.
 * - Sends a ping every 25s so proxies don't close an idle connection.
 */
export const RealtimeProvider = ({ children }) => {
    const { user } = useContext(AuthContext);
    const [status, setStatus] = useState('offline');
    const [toasts, setToasts] = useState([]);
    const listeners = useRef(new Set());
    const userRef = useRef(user);
    const userId = user?.id;

    useEffect(() => {
        userRef.current = user;
    });

    const subscribe = useCallback((fn) => {
        listeners.current.add(fn);
        return () => listeners.current.delete(fn);
    }, []);

    const dismiss = useCallback((id) => setToasts((all) => all.filter((t) => t.id !== id)), []);

    useEffect(() => {
        if (!userId) return undefined;
        let socket;
        let retryTimer;
        let pingTimer;
        let attempt = 0;
        let stopped = false;

        const connect = () => {
            const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
            socket = new WebSocket(`${scheme}://${window.location.host}/ws/`);
            setStatus('connecting');

            socket.onopen = () => {
                attempt = 0;
                setStatus('live');
                pingTimer = setInterval(() => socket.send(JSON.stringify({ type: 'ping' })), 25000);
            };

            socket.onmessage = (message) => {
                const event = JSON.parse(message.data);
                if (event.event !== 'ticket') return;
                listeners.current.forEach((fn) => fn(event));
                const text = notificationFor(event, userRef.current);
                if (text) {
                    const id = `${Date.now()}-${Math.random()}`;
                    setToasts((all) => [...all.slice(-3), { id, text, ticket: event.ticket }]);
                    setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), 7000);
                }
            };

            socket.onclose = async (closeEvent) => {
                clearInterval(pingTimer);
                setStatus('offline');
                if (stopped) return;
                if (closeEvent.code === UNAUTHORIZED) {
                    try {
                        await api.post('/auth/token/refresh/', {});
                    } catch {
                        return; // logged out: stay disconnected
                    }
                }
                const delay = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempt);
                attempt += 1;
                retryTimer = setTimeout(connect, delay);
            };
        };

        connect();
        return () => {
            stopped = true;
            clearTimeout(retryTimer);
            clearInterval(pingTimer);
            if (socket) socket.close();
        };
    }, [userId]);

    return (
        <RealtimeContext.Provider value={{ status: userId ? status : 'offline', subscribe }}>
            {children}
            <div className="toasts" aria-live="polite">
                {toasts.map((toast) => (
                    <div key={toast.id} className="toast">
                        <Link to={`/tickets/${toast.ticket}`} onClick={() => dismiss(toast.id)}>{toast.text}</Link>
                        <button type="button" aria-label="Dismiss" onClick={() => dismiss(toast.id)}>×</button>
                    </div>
                ))}
            </div>
        </RealtimeContext.Provider>
    );
};
