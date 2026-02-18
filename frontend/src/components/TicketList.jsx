import React, { useState, useEffect } from 'react';
import api from '../api';

const TicketList = () => {
    const [tickets, setTickets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filterStatus, setFilterStatus] = useState('');
    const [filterPriority, setFilterPriority] = useState('');
    const [search, setSearch] = useState('');

    const fetchTickets = async () => {
        setLoading(true);
        try {
            let query = '/tickets/?';
            if (filterStatus) query += `status=${filterStatus}&`;
            if (filterPriority) query += `priority=${filterPriority}&`;
            if (search) query += `search=${search}&`;

            const response = await api.get(query);
            setTickets(response.data);
        } catch (error) {
            console.error("Failed to fetch tickets", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTickets();
    }, [filterStatus, filterPriority, search]);

    // Expose refresh method to parent if needed, or just auto-refresh on props change
    // For now, simple internal state.

    return (
        <div>
            <div className="card">
                <h3>Filters</h3>
                <div className="grid">
                    <input
                        placeholder="Search..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                    <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                        <option value="">All Statuses</option>
                        <option value="open">Open</option>
                        <option value="in_progress">In Progress</option>
                        <option value="resolved">Resolved</option>
                        <option value="closed">Closed</option>
                    </select>
                    <select value={filterPriority} onChange={(e) => setFilterPriority(e.target.value)}>
                        <option value="">All Priorities</option>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                    </select>
                </div>
            </div>

            <div className="grid">
                {loading ? (
                    <p>Loading tickets...</p>
                ) : tickets.length === 0 ? (
                    <p>No tickets found.</p>
                ) : (
                    tickets.map(ticket => (
                        <div key={ticket.id} className="card">
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <h4>#{ticket.id} {ticket.title}</h4>
                                <span className="status-badge">{ticket.status}</span>
                            </div>
                            <p>{ticket.description}</p>
                            <div style={{ borderTop: '2px solid #2a2a2a', paddingTop: '10px', marginTop: '10px', fontSize: '0.9rem' }}>
                                <p><strong>Category:</strong> {ticket.category} | <strong>Priority:</strong> {ticket.priority}</p>
                                <p><strong>Created:</strong> {new Date(ticket.created_at).toLocaleString()}</p>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default TicketList;
