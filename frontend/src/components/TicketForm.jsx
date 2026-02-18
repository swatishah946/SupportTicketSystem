import React, { useState } from 'react';
import api from '../api';

const TicketForm = ({ onTicketCreated }) => {
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [category, setCategory] = useState('general');
    const [priority, setPriority] = useState('medium');
    const [isProcessing, setIsProcessing] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleDescriptionBlur = async () => {
        if (!description.trim()) return;

        setIsProcessing(true);
        try {
            const response = await api.post('/tickets/classify/', { description });
            if (response.data) {
                if (response.data.suggested_category) setCategory(response.data.suggested_category);
                if (response.data.suggested_priority) setPriority(response.data.suggested_priority);
            }
        } catch (error) {
            console.error("Classification failed:", error);
        } finally {
            setIsProcessing(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            await api.post('/tickets/', { title, description, category, priority });
            setTitle('');
            setDescription('');
            setCategory('general');
            setPriority('medium');
            if (onTicketCreated) onTicketCreated();
        } catch (error) {
            console.error("Submission failed:", error);
            alert("Failed to create ticket.");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="card">
            <h2>Create Ticket</h2>
            <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: '15px' }}>
                    <label>Title</label>
                    <input
                        type="text"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        required
                    />
                </div>
                <div style={{ marginBottom: '15px' }}>
                    <label>Description</label>
                    <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        onBlur={handleDescriptionBlur}
                        rows="4"
                        required
                    />
                    {isProcessing && <span style={{ fontSize: '0.8rem', color: '#666' }}>Processing classification... <div className="loading-spinner"></div></span>}
                </div>
                <div className="grid">
                    <div style={{ marginBottom: '15px' }}>
                        <label>Category</label>
                        <select value={category} onChange={(e) => setCategory(e.target.value)}>
                            <option value="billing">Billing</option>
                            <option value="technical">Technical</option>
                            <option value="account">Account</option>
                            <option value="general">General</option>
                        </select>
                    </div>
                    <div style={{ marginBottom: '15px' }}>
                        <label>Priority</label>
                        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                            <option value="critical">Critical</option>
                        </select>
                    </div>
                </div>
                <button type="submit" disabled={isSubmitting || isProcessing}>
                    {isSubmitting ? 'Submitting...' : 'Submit Ticket'}
                </button>
            </form>
        </div>
    );
};

export default TicketForm;
