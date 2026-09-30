import React, { useState } from 'react';
import api, { errorMessage } from '../api';
import Dashboard from './Dashboard';
import TicketList from './TicketList';

const AdminDashboard = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState(null);

    const handleCreateAgent = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);
        try {
            const res = await api.post('/auth/create-agent/', { email, password });
            setMessage({ ok: true, text: `Agent ${res.data.email} created.` });
            setEmail('');
            setPassword('');
        } catch (err) {
            setMessage({ ok: false, text: errorMessage(err, 'Failed to create agent.') });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="page">
            <div className="page-head">
                <h1>Admin dashboard</h1>
                <div className="row">
                    <a href="/api/docs/" target="_blank" rel="noopener noreferrer"><button>API docs</button></a>
                    <a href="/admin/" target="_blank" rel="noopener noreferrer"><button>Django admin</button></a>
                </div>
            </div>

            <Dashboard />

            <h2 className="section-title">Onboard a support agent</h2>
            <form onSubmit={handleCreateAgent} className="row card">
                <input type="email" placeholder="agent@company.com" value={email}
                       onChange={(e) => setEmail(e.target.value)} required style={{ flex: '1 1 220px' }} />
                <input type="password" placeholder="Password (min 8 chars)" value={password}
                       onChange={(e) => setPassword(e.target.value)} required minLength={8} style={{ flex: '1 1 220px' }} />
                <button type="submit" className="btn-primary" disabled={loading}>
                    {loading ? 'Creating…' : 'Create agent'}
                </button>
                {message && <span className={message.ok ? '' : 'error'}>{message.text}</span>}
            </form>

            <h2 className="section-title">SLA breaches</h2>
            <TicketList preset={{ sla_breached: true, ordering: 'resolution_due' }} showFilters={false}
                        emptyText="No active ticket is past its SLA." />

            <h2 className="section-title">All tickets</h2>
            <TicketList />
        </div>
    );
};

export default AdminDashboard;
