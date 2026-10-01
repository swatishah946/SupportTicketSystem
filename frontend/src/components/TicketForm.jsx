import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api, { errorMessage } from '../api';
import { CATEGORIES, label, PRIORITIES } from '../lib/format';

const TicketForm = () => {
    const navigate = useNavigate();
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [category, setCategory] = useState('');
    const [priority, setPriority] = useState('');
    const [suggestion, setSuggestion] = useState(null);
    const [duplicates, setDuplicates] = useState([]);
    const [isClassifying, setIsClassifying] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');
    const touched = useRef({ category: false, priority: false });

    // Duplicate detection while typing (debounced).
    useEffect(() => {
        const text = `${title} ${description}`.trim();
        if (text.length < 15) {
            setDuplicates([]);
            return undefined;
        }
        const t = setTimeout(() => {
            api.post('/tickets/similar/', { title, description })
                .then((res) => setDuplicates(res.data))
                .catch(() => setDuplicates([]));
        }, 600);
        return () => clearTimeout(t);
    }, [title, description]);

    const classify = async () => {
        if (!description.trim()) return;
        setIsClassifying(true);
        try {
            const res = await api.post('/tickets/classify/', { title, description });
            setSuggestion(res.data);
            // Only fill fields the user hasn't chosen themselves.
            if (!touched.current.category) setCategory(res.data.category);
            if (!touched.current.priority) setPriority(res.data.priority);
        } catch {
            setSuggestion(null); // AI is optional; the form still works
        } finally {
            setIsClassifying(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        setError('');
        try {
            const payload = { title, description };
            if (category) payload.category = category;
            if (priority) payload.priority = priority;
            const res = await api.post('/tickets/', payload);
            navigate(`/tickets/${res.data.id}`);
        } catch (err) {
            setError(errorMessage(err, 'Failed to create ticket.'));
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="page" style={{ maxWidth: 760 }}>
            <div className="card">
                <h2>Create ticket</h2>
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: 15 }}>
                        <label>Title</label>
                        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
                    </div>
                    <div style={{ marginBottom: 15 }}>
                        <label>Description</label>
                        <textarea value={description} onChange={(e) => setDescription(e.target.value)}
                                  onBlur={classify} rows="5" required />
                        {isClassifying && <span className="muted">Triaging… <span className="loading-spinner" /></span>}
                    </div>

                    {duplicates.length > 0 && (
                        <div className="callout">
                            <strong>Is this the same as one of your open tickets?</strong>
                            <ul>
                                {duplicates.map((d) => (
                                    <li key={d.id}>
                                        <Link to={`/tickets/${d.id}`}>#{d.id} {d.title}</Link>{' '}
                                        <span className="muted">({label(d.status)}, {Math.round(d.score * 100)}% match)</span>
                                    </li>
                                ))}
                            </ul>
                            <span className="muted">Replying there gets you help faster than a new ticket.</span>
                        </div>
                    )}

                    {suggestion && (
                        <div className="callout callout-ai">
                            Suggested <strong>{suggestion.category}</strong> / <strong>{suggestion.priority}</strong>
                            <span className="muted"> · {suggestion.source === 'llm' ? 'Gemini' : 'rule-based fallback'}</span>
                        </div>
                    )}

                    <div className="grid">
                        <div style={{ marginBottom: 15 }}>
                            <label>Category</label>
                            <select value={category} onChange={(e) => { touched.current.category = true; setCategory(e.target.value); }}>
                                <option value="">Let AI decide</option>
                                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>
                        <div style={{ marginBottom: 15 }}>
                            <label>Priority</label>
                            <select value={priority} onChange={(e) => { touched.current.priority = true; setPriority(e.target.value); }}>
                                <option value="">Let AI decide</option>
                                {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                            </select>
                        </div>
                    </div>
                    {error && <p className="error">{error}</p>}
                    <button type="submit" className="btn-primary" disabled={isSubmitting}>
                        {isSubmitting ? 'Submitting…' : 'Submit ticket'}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default TicketForm;
