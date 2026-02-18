import React, { useState, useEffect } from 'react';
import api from '../api';

const Dashboard = () => {
    const [stats, setStats] = useState(null);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await api.get('/tickets/stats/');
                setStats(response.data);
            } catch (error) {
                console.error("Failed to fetch stats", error);
            }
        };
        fetchStats();
    }, []);

    if (!stats) return <p>Loading stats...</p>;

    return (
        <div className="grid">
            <div className="card" style={{ textAlign: 'center' }}>
                <h3>Total Tickets</h3>
                <h1 style={{ fontSize: '3rem' }}>{stats.total_tickets}</h1>
            </div>
            <div className="card" style={{ textAlign: 'center' }}>
                <h3>Open Tickets</h3>
                <h1 style={{ fontSize: '3rem' }}>{stats.open_tickets}</h1>
            </div>
            <div className="card" style={{ textAlign: 'center' }}>
                <h3>Avg / Day</h3>
                <h1 style={{ fontSize: '3rem' }}>{stats.avg_tickets_per_day}</h1>
            </div>

            <div className="card">
                <h3>Priority Breakdown</h3>
                <ul>
                    {Object.entries(stats.priority_breakdown).map(([key, value]) => (
                        <li key={key}><strong>{key.toUpperCase()}:</strong> {value}</li>
                    ))}
                </ul>
            </div>
            <div className="card">
                <h3>Category Breakdown</h3>
                <ul>
                    {Object.entries(stats.category_breakdown).map(([key, value]) => (
                        <li key={key}><strong>{key.toUpperCase()}:</strong> {value}</li>
                    ))}
                </ul>
            </div>
        </div>
    );
};

export default Dashboard;
