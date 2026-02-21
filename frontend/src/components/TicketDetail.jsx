import React, { useState, useEffect, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { AuthContext } from '../context/AuthContext';

const TicketDetail = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user } = useContext(AuthContext);

    const [ticket, setTicket] = useState(null);
    const [status, setStatus] = useState('');
    const [newComment, setNewComment] = useState('');
    const [loading, setLoading] = useState(true);
    const [isGenerating, setIsGenerating] = useState(false);
    const [toastMessage, setToastMessage] = useState('');
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchTicket = async () => {
            try {
                const response = await api.get(`/tickets/${id}/`);
                setTicket(response.data);
                setStatus(response.data.status);
            } catch (err) {
                console.error("Failed to fetch ticket", err);
                setError("Failed to load ticket details.");
            } finally {
                setLoading(false);
            }
        };
        fetchTicket();
    }, [id]);

    const handleUpdateStatus = async () => {
        try {
            await api.patch(`/tickets/${id}/`, { status });
            alert('Ticket status updated successfully!');
            const response = await api.get(`/tickets/${id}/`);
            setTicket(response.data);
            setStatus(response.data.status);
        } catch (err) {
            console.error("Failed to update status", err);
            alert('Failed to update status.');
        }
    };

    const handleClaimTicket = async () => {
        try {
            await api.patch(`/tickets/${id}/`, { assigned_to_id: user.id });
            alert('Ticket claimed successfully!');
            const response = await api.get(`/tickets/${id}/`);
            setTicket(response.data);
            setStatus(response.data.status);
        } catch (err) {
            console.error("Failed to claim ticket", err);
            alert('Failed to claim ticket.');
        }
    };

    const handleAddComment = async () => {
        if (!newComment.trim()) return;
        try {
            const response = await api.post(`/tickets/${id}/add_comment/`, { body: newComment });
            // Append new comment locally
            setTicket(prev => ({
                ...prev,
                comments: [...prev.comments, response.data]
            }));
            setNewComment('');
        } catch (err) {
            console.error("Failed to add comment", err);
            alert('Failed to send reply.');
        }
    };

    const handleSuggestReply = async () => {
        setIsGenerating(true);
        try {
            const response = await api.get(`/tickets/${id}/suggest_reply/`);
            if (response.data.suggestion) {
                setNewComment(response.data.suggestion);

                if (response.data.suggested_status) {
                    setStatus(response.data.suggested_status);
                    setToastMessage(`AI drafted a reply and suggested status: ${response.data.suggested_status}`);

                    // Hide toast after 4 seconds
                    setTimeout(() => setToastMessage(''), 4000);
                }
            } else if (response.data.error) {
                alert("AI Error: " + response.data.error);
            }
        } catch (err) {
            console.error("Failed to generate suggestion", err);
            alert("Failed to connect to AI Copilot.");
        } finally {
            setIsGenerating(false);
        }
    };

    if (loading) return <div style={{ padding: '20px', fontFamily: 'monospace' }}>Loading ticket...</div>;
    if (error) return <div style={{ padding: '20px', fontFamily: 'monospace', color: 'red', fontWeight: 'bold' }}>{error}</div>;
    if (!ticket) return null;

    const isAgentOrAdmin = user?.role === 'admin' || user?.role === 'support_agent';

    // Theme styles
    const containerStyle = { padding: '20px', fontFamily: 'monospace', maxWidth: '800px', margin: '0 auto' };
    const cardStyle = { border: '2px solid black', padding: '20px', boxShadow: '4px 4px 0px black', marginBottom: '20px', backgroundColor: 'white' };
    const inputStyle = { width: '100%', padding: '10px', marginBottom: '15px', border: '2px solid black', fontFamily: 'monospace', borderRadius: '0', boxSizing: 'border-box' };
    const btnStyle = { padding: '10px 20px', backgroundColor: 'black', color: 'white', border: 'none', boxShadow: '4px 4px 0px #888', cursor: 'pointer', fontWeight: 'bold', fontFamily: 'monospace', textTransform: 'uppercase' };

    return (
        <div style={containerStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h1 style={{ textTransform: 'uppercase', margin: 0 }}>Ticket #{ticket.id}</h1>
                <button onClick={() => navigate(-1)} style={{ ...btnStyle, backgroundColor: 'white', color: 'black', border: '2px solid black', boxShadow: '2px 2px 0px black' }}>Back</button>
            </div>

            <div style={cardStyle}>
                <h2 style={{ borderBottom: '2px solid black', paddingBottom: '10px' }}>{ticket.title}</h2>
                <div style={{ marginBottom: '20px' }}>
                    <p style={{ margin: '5px 0' }}><strong>Status:</strong> <span style={{ padding: '2px 8px', background: 'black', color: 'white', textTransform: 'uppercase', marginLeft: '5px' }}>{ticket.status}</span></p>
                    <p style={{ margin: '5px 0' }}><strong>Priority:</strong> {ticket.priority}</p>
                    <p style={{ margin: '5px 0' }}><strong>Customer Email:</strong> {ticket.customer_email || (ticket.created_by && ticket.created_by.email) || 'N/A'}</p>
                    <div style={{ margin: '15px 0', padding: '10px', backgroundColor: '#f0f0f0', border: '1px solid black' }}>
                        {ticket.assigned_to ? (
                            <p style={{ margin: 0, fontWeight: 'bold' }}>Assigned to: {ticket.assigned_to.email}</p>
                        ) : (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <p style={{ margin: 0, fontWeight: 'bold', color: '#d32f2f' }}>Unassigned</p>
                                {isAgentOrAdmin && (
                                    <button onClick={handleClaimTicket} style={{ ...btnStyle, padding: '5px 15px', backgroundColor: '#d32f2f', color: 'white', border: '2px solid black' }}>CLAIM TICKET</button>
                                )}
                            </div>
                        )}
                    </div>
                    <div style={{ marginTop: '15px' }}>
                        <strong>Description:</strong>
                        <p style={{ whiteSpace: 'pre-wrap', background: '#f9f9f9', padding: '10px', border: '1px solid black', marginTop: '5px' }}>{ticket.description}</p>
                    </div>
                </div>

                {/* Threaded Conversation */}
                <div style={{ marginTop: '20px', borderTop: '2px dashed black', paddingTop: '20px' }}>
                    <h3 style={{ textTransform: 'uppercase', marginTop: 0 }}>Conversation Activity</h3>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginBottom: '20px' }}>
                        {ticket.comments && ticket.comments.length > 0 ? (
                            ticket.comments.map(comment => {
                                const isStaff = comment.author.role === 'admin' || comment.author.role === 'support_agent';
                                return (
                                    <div key={comment.id} style={{
                                        padding: '15px',
                                        border: '2px solid black',
                                        backgroundColor: isStaff ? '#e0e0e0' : 'white',
                                        alignSelf: isStaff ? 'flex-start' : 'flex-end',
                                        width: '80%',
                                        boxShadow: isStaff ? '-4px 4px 0px black' : '4px 4px 0px black'
                                    }}>
                                        <div style={{ fontWeight: 'bold', borderBottom: '1px solid #ccc', paddingBottom: '5px', marginBottom: '10px', display: 'flex', justifyContent: 'space-between' }}>
                                            <span>{isStaff ? `Agent: ${comment.author.username}` : `Customer: ${comment.author.username}`}</span>
                                            <span style={{ fontSize: '0.8rem', fontWeight: 'normal' }}>{new Date(comment.created_at).toLocaleString()}</span>
                                        </div>
                                        <div style={{ whiteSpace: 'pre-wrap' }}>{comment.body}</div>
                                    </div>
                                );
                            })
                        ) : (
                            <div style={{ padding: '10px', fontStyle: 'italic', color: '#666' }}>No replies yet.</div>
                        )}
                    </div>

                    {/* AI Toast Notification */}
                    {toastMessage && (
                        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#e6ffe6', border: '2px solid #00cc00', color: '#006600', fontWeight: 'bold' }}>
                            ✨ {toastMessage}
                        </div>
                    )}

                    {/* Reply Box for Everyone */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        <textarea
                            value={newComment}
                            onChange={(e) => setNewComment(e.target.value)}
                            placeholder="Type your reply here..."
                            style={{ ...inputStyle, minHeight: '80px', marginBottom: '0' }}
                        />
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            {isAgentOrAdmin ? (
                                <button
                                    onClick={handleSuggestReply}
                                    disabled={isGenerating}
                                    style={{ ...btnStyle, backgroundColor: '#6200ea', color: 'white', opacity: isGenerating ? 0.7 : 1 }}
                                >
                                    {isGenerating ? '⏳ GENERATING DRAFT...' : '✨ ASK AI COPILOT'}
                                </button>
                            ) : <div />}
                            <button onClick={handleAddComment} style={{ ...btnStyle }}>Send Reply</button>
                        </div>
                    </div>
                </div>

                {/* Status Controls for Agents/Admins only */}
                {isAgentOrAdmin && (
                    <div style={{ borderTop: '2px dashed black', paddingTop: '20px', marginTop: '30px' }}>
                        <h3 style={{ textTransform: 'uppercase', marginTop: 0 }}>Ticket Controls</h3>
                        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                            <label style={{ fontWeight: 'bold' }}>Update Status:</label>
                            <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ ...inputStyle, width: 'auto', marginBottom: 0 }}>
                                <option value="open">Open</option>
                                <option value="in_progress">In Progress</option>
                                <option value="resolved">Resolved</option>
                                <option value="closed">Closed</option>
                            </select>
                            <button onClick={handleUpdateStatus} style={btnStyle}>Save Status</button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default TicketDetail;
