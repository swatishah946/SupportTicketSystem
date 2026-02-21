import React, { useState } from 'react';
import api from '../api';
import Dashboard from './Dashboard';
import TicketList from './TicketList';

const AdminDashboard = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const mockAgents = [
        { name: 'Agent Smith', open_tickets: 4, resolved_today: 12 },
        { name: 'Agent Neo', open_tickets: 2, resolved_today: 5 },
        { name: 'Agent Trinity', open_tickets: 6, resolved_today: 15 },
    ];

    const handleCreateAgent = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await api.post('/auth/create-agent/', { email, password });
            alert('Agent successfully created!');
            setEmail('');
            setPassword('');
        } catch (error) {
            console.error('Agent creation failed', error);
            alert('Failed to create agent. See console for details.');
        } finally {
            setLoading(false);
        }
    };

    const inputStyle = {
        padding: '10px',
        marginRight: '10px',
        border: '2px solid black',
        fontFamily: 'monospace',
        borderRadius: '0',
    };

    const btnStyle = {
        padding: '10px 20px',
        backgroundColor: 'black',
        color: 'white',
        border: 'none',
        boxShadow: '4px 4px 0px #888',
        cursor: 'pointer',
        fontWeight: 'bold',
        fontFamily: 'monospace',
        textTransform: 'uppercase',
    };

    return (
        <div style={{ padding: '20px', fontFamily: 'monospace' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h1 style={{ textTransform: 'uppercase', margin: 0 }}>Admin Dashboard</h1>
                <a href="http://localhost:8000/admin/" target="_blank" rel="noopener noreferrer">
                    <button style={btnStyle}>
                        OPEN DJANGO ADMIN (USER MANAGEMENT)
                    </button>
                </a>
            </div>

            <section style={{
                marginBottom: '40px',
                padding: '20px',
                border: '2px solid black',
                boxShadow: '4px 4px 0px black',
                backgroundColor: 'white'
            }}>
                <h2 style={{ textTransform: 'uppercase', marginTop: 0 }}>Onboard New Support Agent</h2>
                <form onSubmit={handleCreateAgent} style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                    <input
                        type="email"
                        placeholder="Agent Email"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        style={inputStyle}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Secure Password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        style={inputStyle}
                        required
                    />
                    <button type="submit" style={btnStyle} disabled={loading}>
                        {loading ? 'Creating...' : 'Create Agent'}
                    </button>
                </form>
            </section>

            <section style={{ marginBottom: '40px' }}>
                <h2 style={{ textTransform: 'uppercase', borderBottom: '2px solid black', paddingBottom: '10px' }}>System Overview</h2>
                <Dashboard />
            </section>

            <section style={{ marginBottom: '40px' }}>
                <h2 style={{ textTransform: 'uppercase', borderBottom: '2px solid black', paddingBottom: '10px' }}>Agent Performance Overview</h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '20px' }}>
                    {mockAgents.map((agent, index) => (
                        <div key={index} style={{ padding: '15px', border: '2px solid black', boxShadow: '4px 4px 0px black', backgroundColor: 'white' }}>
                            <h3 style={{ textTransform: 'uppercase', marginTop: 0 }}>{agent.name}</h3>
                            <p style={{ margin: '5px 0' }}><strong>Open Tickets:</strong> {agent.open_tickets}</p>
                            <p style={{ margin: '5px 0' }}><strong>Resolved Today:</strong> {agent.resolved_today}</p>
                        </div>
                    ))}
                </div>
            </section>

            <section>
                <h2 style={{ textTransform: 'uppercase', borderBottom: '2px solid black', paddingBottom: '10px' }}>All Tickets</h2>
                <TicketList />
            </section>
        </div>
    );
};

export default AdminDashboard;
