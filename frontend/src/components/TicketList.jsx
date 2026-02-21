import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { AuthContext } from '../context/AuthContext';

const TicketList = ({ splitByAssignment = false }) => {
    const { user } = useContext(AuthContext);
    const navigate = useNavigate();
    const [tickets, setTickets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('All Statuses');
    const [priorityFilter, setPriorityFilter] = useState('All Priorities');

    const fetchTickets = async () => {
        setLoading(true);
        try {
            const response = await api.get('/tickets/');
            setTickets(response.data);
        } catch (error) {
            console.error("Failed to fetch tickets", error);
        } finally {
            setLoading(false);
        }
    };

    // Force fetch on mount
    useEffect(() => {
        fetchTickets();
    }, []);

    // Expose refresh method to parent if needed, or just auto-refresh on props change
    // For now, simple internal state.

    const filteredTickets = tickets.filter(ticket => {
        const matchesSearch = searchTerm === '' ||
            (ticket.title && ticket.title.toLowerCase().includes(searchTerm.toLowerCase())) ||
            (ticket.description && ticket.description.toLowerCase().includes(searchTerm.toLowerCase()));

        const matchesStatus = statusFilter === 'All Statuses' || ticket.status === statusFilter;
        const matchesPriority = priorityFilter === 'All Priorities' || ticket.priority === priorityFilter;

        return matchesSearch && matchesStatus && matchesPriority;
    });

    return (
        <div>
            <div className="card" style={{ marginBottom: '20px', padding: '15px', border: '2px solid black', fontFamily: 'monospace', backgroundColor: 'white' }}>
                <h3 style={{ textTransform: 'uppercase', marginTop: 0 }}>Filters</h3>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <input
                        placeholder="Search..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        style={{ padding: '10px', border: '2px solid black', fontFamily: 'monospace' }}
                    />
                    <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: '10px', border: '2px solid black', fontFamily: 'monospace' }}>
                        <option value="All Statuses">All Statuses</option>
                        <option value="open">Open</option>
                        <option value="in_progress">In Progress</option>
                        <option value="resolved">Resolved</option>
                        <option value="closed">Closed</option>
                    </select>
                    <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} style={{ padding: '10px', border: '2px solid black', fontFamily: 'monospace' }}>
                        <option value="All Priorities">All Priorities</option>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                    </select>
                </div>
            </div>

            {loading ? (
                <p style={{ fontFamily: 'monospace' }}>Loading tickets...</p>
            ) : splitByAssignment ? (
                <>
                    <h3 style={{ textTransform: 'uppercase', borderBottom: '2px dashed black', paddingBottom: '10px', marginTop: '30px' }}>Unassigned Queue</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem', marginBottom: '30px' }}>
                        {filteredTickets.filter(t => !t.assigned_to).length === 0 ? (
                            <p style={{ padding: '20px', border: '2px solid black', backgroundColor: '#f9f9f9', fontFamily: 'monospace', fontWeight: 'bold', gridColumn: '1 / -1' }}>No unassigned tickets found.</p>
                        ) : (
                            filteredTickets.filter(t => !t.assigned_to).map(ticket => (
                                <div key={ticket.id} style={{ cursor: 'pointer', padding: '15px', border: '2px solid black', boxShadow: '4px 4px 0px black', backgroundColor: 'white', fontFamily: 'monospace', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }} onClick={() => navigate(`/tickets/${ticket.id}`)}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
                                            <h4 style={{ margin: 0, fontSize: '1.2rem', textTransform: 'uppercase' }}>#{ticket.id} {ticket.title}</h4>
                                            {ticket.has_unread_updates && user?.role === 'customer' && (
                                                <span style={{ padding: '2px 8px', backgroundColor: '#d32f2f', color: 'white', fontWeight: 'bold', fontSize: '0.7rem', marginLeft: '10px', whiteSpace: 'nowrap' }}>🔴 NEW UPDATE</span>
                                            )}
                                        </div>
                                        <span style={{ padding: '5px 10px', backgroundColor: 'black', color: 'white', fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.8rem', whiteSpace: 'nowrap', marginLeft: '10px' }}>{ticket.status}</span>
                                    </div>
                                    <p style={{ margin: '15px 0', flexGrow: 1 }}>{ticket.description.length > 100 ? ticket.description.substring(0, 100) + '...' : ticket.description}</p>
                                    {ticket.comments && ticket.comments.length > 0 && (
                                        <div style={{ fontSize: '0.8rem', padding: '5px', backgroundColor: '#e0e0e0', border: '1px solid black', marginBottom: '10px', fontWeight: 'bold' }}>✓ CONVERSATION ACTIVE ({ticket.comments.length})</div>
                                    )}
                                    <div style={{ borderTop: '2px dashed black', paddingTop: '10px', fontSize: '0.9rem', display: 'flex', justifyContent: 'space-between' }}>
                                        <span><strong>Cat:</strong> {ticket.category} | <strong>Pri:</strong> {ticket.priority}</span>
                                        <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>

                    <h3 style={{ textTransform: 'uppercase', borderBottom: '2px dashed black', paddingBottom: '10px' }}>My Active Tickets</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem', marginBottom: '30px' }}>
                        {filteredTickets.filter(t => t.assigned_to && t.assigned_to.id === user?.id).length === 0 ? (
                            <p style={{ padding: '20px', border: '2px solid black', backgroundColor: '#f9f9f9', fontFamily: 'monospace', fontWeight: 'bold', gridColumn: '1 / -1' }}>You have no active tickets assigned.</p>
                        ) : (
                            filteredTickets.filter(t => t.assigned_to && t.assigned_to.id === user?.id).map(ticket => (
                                <div key={ticket.id} style={{ cursor: 'pointer', padding: '15px', border: '2px solid black', boxShadow: '4px 4px 0px black', backgroundColor: 'white', fontFamily: 'monospace', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }} onClick={() => navigate(`/tickets/${ticket.id}`)}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
                                            <h4 style={{ margin: 0, fontSize: '1.2rem', textTransform: 'uppercase' }}>#{ticket.id} {ticket.title}</h4>
                                            {ticket.has_unread_updates && user?.role === 'customer' && (
                                                <span style={{ padding: '2px 8px', backgroundColor: '#d32f2f', color: 'white', fontWeight: 'bold', fontSize: '0.7rem', marginLeft: '10px', whiteSpace: 'nowrap' }}>🔴 NEW UPDATE</span>
                                            )}
                                        </div>
                                        <span style={{ padding: '5px 10px', backgroundColor: 'black', color: 'white', fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.8rem', whiteSpace: 'nowrap', marginLeft: '10px' }}>{ticket.status}</span>
                                    </div>
                                    <p style={{ margin: '15px 0', flexGrow: 1 }}>{ticket.description.length > 100 ? ticket.description.substring(0, 100) + '...' : ticket.description}</p>
                                    {ticket.comments && ticket.comments.length > 0 && (
                                        <div style={{ fontSize: '0.8rem', padding: '5px', backgroundColor: '#e0e0e0', border: '1px solid black', marginBottom: '10px', fontWeight: 'bold' }}>✓ CONVERSATION ACTIVE ({ticket.comments.length})</div>
                                    )}
                                    <div style={{ borderTop: '2px dashed black', paddingTop: '10px', fontSize: '0.9rem', display: 'flex', justifyContent: 'space-between' }}>
                                        <span><strong>Cat:</strong> {ticket.category} | <strong>Pri:</strong> {ticket.priority}</span>
                                        <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
                    {filteredTickets.length === 0 ? (
                        <p style={{ padding: '20px', border: '2px solid black', backgroundColor: '#f9f9f9', fontFamily: 'monospace', fontWeight: 'bold', gridColumn: '1 / -1' }}>
                            No tickets match your filters.
                        </p>
                    ) : (
                        filteredTickets.map(ticket => (
                            <div
                                key={ticket.id}
                                style={{
                                    cursor: 'pointer',
                                    padding: '15px',
                                    border: '2px solid black',
                                    boxShadow: '4px 4px 0px black',
                                    backgroundColor: 'white',
                                    fontFamily: 'monospace',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    justifyContent: 'space-between'
                                }}
                                onClick={() => navigate(`/tickets/${ticket.id}`)}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
                                        <h4 style={{ margin: 0, fontSize: '1.2rem', textTransform: 'uppercase' }}>#{ticket.id} {ticket.title}</h4>
                                        {ticket.has_unread_updates && user?.role === 'customer' && (
                                            <span style={{ padding: '2px 8px', backgroundColor: '#d32f2f', color: 'white', fontWeight: 'bold', fontSize: '0.7rem', marginLeft: '10px', whiteSpace: 'nowrap' }}>🔴 NEW UPDATE</span>
                                        )}
                                    </div>
                                    <span style={{ padding: '5px 10px', backgroundColor: 'black', color: 'white', fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.8rem', whiteSpace: 'nowrap', marginLeft: '10px' }}>{ticket.status}</span>
                                </div>
                                <p style={{ margin: '15px 0', flexGrow: 1 }}>{ticket.description.length > 100 ? ticket.description.substring(0, 100) + '...' : ticket.description}</p>

                                {ticket.comments && ticket.comments.length > 0 && (
                                    <div style={{ fontSize: '0.8rem', padding: '5px', backgroundColor: '#e0e0e0', border: '1px solid black', marginBottom: '10px', fontWeight: 'bold' }}>
                                        ✓ CONVERSATION ACTIVE ({ticket.comments.length})
                                    </div>
                                )}

                                <div style={{ borderTop: '2px dashed black', paddingTop: '10px', fontSize: '0.9rem', display: 'flex', justifyContent: 'space-between' }}>
                                    <span><strong>Cat:</strong> {ticket.category} | <strong>Pri:</strong> {ticket.priority}</span>
                                    <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};

export default TicketList;
