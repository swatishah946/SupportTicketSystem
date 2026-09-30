import React, { useCallback, useContext, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api, { errorMessage } from '../api';
import { AuthContext } from '../context/auth';
import { Badge, SlaBadge } from './ui';
import { CATEGORIES, label, PRIORITIES, STATUSES, timeFromNow } from '../lib/format';

const EVENT_TEXT = {
    created: (e) => `created the ticket (${e.to_value})`,
    status_changed: (e) => `changed status ${label(e.from_value)} → ${label(e.to_value)}`,
    priority_changed: (e) => `changed priority ${e.from_value} → ${e.to_value}`,
    category_changed: (e) => `changed category ${e.from_value} → ${e.to_value}`,
    assigned: (e) => (e.to_value ? `assigned to ${e.to_value}` : 'unassigned the ticket'),
    commented: () => 'replied',
    internal_note: () => 'added an internal note',
    escalated: (e) => `escalated for SLA breach (${e.from_value} → ${e.to_value})`,
    marked_duplicate: (e) => `marked as duplicate of ${e.to_value}`,
    rated: (e) => `rated the support ${e.to_value}`,
};

const when = (iso) => (iso ? new Date(iso).toLocaleString() : '—');
const stars = (n) => '★'.repeat(n) + '☆'.repeat(5 - n);

/** Customer satisfaction survey shown once a ticket is resolved. */
function RatingCard({ ticketId, onRated }) {
    const [score, setScore] = useState(0);
    const [comment, setComment] = useState('');
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);

    const submit = async () => {
        setSaving(true);
        setError('');
        try {
            const res = await api.post(`/tickets/${ticketId}/rate/`, { score, comment });
            onRated(res.data);
        } catch (err) {
            setError(errorMessage(err, 'Could not save your rating.'));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="card callout-ai">
            <h3 style={{ marginTop: 0 }}>How did we do?</h3>
            <div className="row" role="radiogroup" aria-label="Rating">
                {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} type="button" role="radio" aria-checked={score === n}
                            className={`star ${n <= score ? 'star-on' : ''}`} onClick={() => setScore(n)}
                            title={`${n} / 5`}>★</button>
                ))}
            </div>
            <textarea rows="2" placeholder="Anything we could do better? (optional)" value={comment}
                      onChange={(e) => setComment(e.target.value)} style={{ marginTop: 10 }} />
            {error && <p className="error">{error}</p>}
            <button className="btn-primary" disabled={!score || saving} onClick={submit} style={{ marginTop: 10 }}>
                {saving ? 'Sending…' : 'Submit rating'}
            </button>
        </div>
    );
}

function StaffControls({ ticket, onSaved }) {
    const [agents, setAgents] = useState([]);
    const [form, setForm] = useState({});
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        api.get('/agents/').then((res) => setAgents(res.data)).catch(() => setAgents([]));
    }, []);

    useEffect(() => {
        setForm({
            status: ticket.status,
            priority: ticket.priority,
            category: ticket.category,
            assigned_to_id: ticket.assigned_to?.id ?? '',
            duplicate_of_id: ticket.duplicate_of ?? '',
            resolution_notes: ticket.resolution_notes || '',
        });
    }, [ticket]);

    const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

    const save = async () => {
        const original = {
            status: ticket.status, priority: ticket.priority, category: ticket.category,
            assigned_to_id: ticket.assigned_to?.id ?? '', duplicate_of_id: ticket.duplicate_of ?? '',
            resolution_notes: ticket.resolution_notes || '',
        };
        const changes = {};
        Object.entries(form).forEach(([k, v]) => {
            if (String(v) !== String(original[k])) {
                changes[k] = (k.endsWith('_id') && v === '') ? null : (k.endsWith('_id') ? Number(v) : v);
            }
        });
        if (!Object.keys(changes).length) return;
        setSaving(true);
        setError('');
        try {
            const res = await api.patch(`/tickets/${ticket.id}/`, changes);
            onSaved(res.data);
        } catch (err) {
            setError(errorMessage(err, 'Update failed.'));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="card">
            <h3 style={{ marginTop: 0 }}>Triage</h3>
            <label>Status</label>
            <select value={form.status || ''} onChange={set('status')}>
                {STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
            </select>
            <label>Priority</label>
            <select value={form.priority || ''} onChange={set('priority')}>
                {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <label>Category</label>
            <select value={form.category || ''} onChange={set('category')}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <label>Assignee</label>
            <select value={form.assigned_to_id} onChange={set('assigned_to_id')}>
                <option value="">Unassigned</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.username} ({label(a.role)})</option>)}
            </select>
            <label>Duplicate of ticket #</label>
            <input type="number" min="1" value={form.duplicate_of_id} onChange={set('duplicate_of_id')}
                   placeholder="closes this ticket" />
            <label>Resolution notes (reused by the AI copilot)</label>
            <textarea rows="3" value={form.resolution_notes} onChange={set('resolution_notes')} />
            {error && <p className="error">{error}</p>}
            <button className="btn-primary" onClick={save} disabled={saving} style={{ marginTop: 10 }}>
                {saving ? 'Saving…' : 'Save changes'}
            </button>
            {ticket.ai_category && (
                <p className="muted" style={{ fontSize: '0.8rem' }}>
                    AI triage ({ticket.ai_source === 'llm' ? 'Gemini' : 'rules'}): {ticket.ai_category} / {ticket.ai_priority}
                </p>
            )}
        </div>
    );
}

const TicketDetail = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user } = useContext(AuthContext);
    const isStaff = user?.role === 'admin' || user?.role === 'support_agent';

    const [ticket, setTicket] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [reply, setReply] = useState('');
    const [internal, setInternal] = useState(false);
    const [sending, setSending] = useState(false);
    const [draft, setDraft] = useState(null);
    const [drafting, setDrafting] = useState(false);

    const load = useCallback(async () => {
        try {
            const res = await api.get(`/tickets/${id}/`);
            setTicket(res.data);
            setError('');
        } catch (err) {
            setError(err.response?.status === 404 ? 'Ticket not found.' : 'Failed to load ticket.');
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => { load(); }, [load]);

    const sendReply = async () => {
        if (!reply.trim()) return;
        setSending(true);
        try {
            await api.post(`/tickets/${id}/comments/`, { body: reply, is_internal: internal });
            setReply('');
            setInternal(false);
            setDraft(null);
            await load();
        } catch (err) {
            alert(errorMessage(err, 'Failed to send reply.'));
        } finally {
            setSending(false);
        }
    };

    const askCopilot = async () => {
        setDrafting(true);
        try {
            const res = await api.post(`/tickets/${id}/suggest_reply/`);
            setDraft(res.data);
            setReply(res.data.reply);
            setInternal(false);
        } catch (err) {
            alert(errorMessage(err, 'The AI copilot is unavailable right now.'));
        } finally {
            setDrafting(false);
        }
    };

    const closeTicket = async () => {
        if (!window.confirm('Close this ticket?')) return;
        try {
            const res = await api.patch(`/tickets/${id}/`, { status: 'closed' });
            setTicket(res.data);
        } catch (err) {
            alert(errorMessage(err, 'Could not close the ticket.'));
        }
    };

    if (loading) return <div className="page">Loading ticket…</div>;
    if (error) return <div className="page error">{error}</div>;
    if (!ticket) return null;

    const active = ticket.status === 'open' || ticket.status === 'in_progress';

    return (
        <div className="page">
            <div className="page-head">
                <div>
                    <h1>#{ticket.id} {ticket.title}</h1>
                    <div className="row" style={{ marginTop: 8 }}>
                        <Badge value={ticket.status} />
                        <Badge kind="priority" value={ticket.priority} />
                        <span className="badge">{ticket.category}</span>
                        <SlaBadge ticket={ticket} />
                        {ticket.escalated && <span className="badge badge-sla-breached">Escalated</span>}
                        {ticket.duplicate_of && (
                            <Link className="badge" to={`/tickets/${ticket.duplicate_of}`}>Duplicate of #{ticket.duplicate_of}</Link>
                        )}
                    </div>
                </div>
                <button onClick={() => navigate(-1)}>Back</button>
            </div>

            <div className="split">
                <div>
                    <div className="card">
                        <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{ticket.description}</p>
                    </div>

                    <h3 className="section-title">Conversation</h3>
                    <div className="thread">
                        {ticket.comments.length === 0 && <p className="muted">No replies yet.</p>}
                        {ticket.comments.map((c) => {
                            const staff = c.author.role !== 'customer';
                            const cls = c.is_internal ? 'comment-internal' : staff ? 'comment-agent' : 'comment-customer';
                            return (
                                <div key={c.id} className={`comment ${cls}`}>
                                    <div className="comment-head">
                                        <span>
                                            {staff ? 'Agent' : 'Customer'}: {c.author.username}{' '}
                                            {c.is_internal && <span className="badge badge-internal">Internal note</span>}
                                        </span>
                                        <span style={{ fontWeight: 'normal' }}>{when(c.created_at)}</span>
                                    </div>
                                    <div style={{ whiteSpace: 'pre-wrap' }}>{c.body}</div>
                                </div>
                            );
                        })}
                    </div>

                    {draft && (
                        <div className="callout callout-ai">
                            <strong>AI draft</strong> ({draft.source === 'llm' ? 'Gemini' : 'retrieval fallback'}) · suggested
                            status: <strong>{label(draft.suggested_status)}</strong>
                            {draft.grounded_on.length > 0 ? (
                                <ul>
                                    {draft.grounded_on.map((g) => (
                                        <li key={g.id}>
                                            grounded on <Link to={`/tickets/${g.id}`}>#{g.id} {g.title}</Link>{' '}
                                            <span className="muted">({Math.round(g.score * 100)}% similar)</span>
                                        </li>
                                    ))}
                                </ul>
                            ) : <div className="muted">No similar resolved tickets found. Review carefully.</div>}
                        </div>
                    )}

                    <textarea value={reply} onChange={(e) => setReply(e.target.value)} rows="5"
                              placeholder={internal ? 'Internal note (customer will not see this)…' : 'Write a reply…'} />
                    <div className="row" style={{ justifyContent: 'space-between', marginTop: 10 }}>
                        <div className="row">
                            {isStaff && (
                                <>
                                    <button className="btn-ai" onClick={askCopilot} disabled={drafting}>
                                        {drafting ? 'Drafting…' : 'Ask AI copilot'}
                                    </button>
                                    <label className="checkbox">
                                        <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
                                        Internal note
                                    </label>
                                </>
                            )}
                        </div>
                        <button className="btn-primary" onClick={sendReply} disabled={sending || !reply.trim()}>
                            {sending ? 'Sending…' : internal ? 'Add note' : 'Send reply'}
                        </button>
                    </div>
                    {!isStaff && ticket.status === 'resolved' && (
                        <p className="muted">Still not fixed? Reply above and the ticket reopens automatically.</p>
                    )}
                </div>

                <aside>
                    <div className="card">
                        <dl className="kv">
                            <dt>Customer</dt><dd>{ticket.created_by?.email || '—'}</dd>
                            <dt>Assignee</dt><dd>{ticket.assigned_to ? ticket.assigned_to.username : 'Unassigned'}</dd>
                            <dt>Created</dt><dd>{when(ticket.created_at)}</dd>
                            <dt>First reply</dt>
                            <dd>{ticket.first_response_at ? when(ticket.first_response_at)
                                : `due ${timeFromNow(ticket.first_response_due)}`}</dd>
                            <dt>Resolution</dt>
                            <dd>{ticket.resolved_at ? when(ticket.resolved_at)
                                : `due ${timeFromNow(ticket.resolution_due)}`}</dd>
                            {ticket.csat_score && (
                                <>
                                    <dt>Rating</dt>
                                    <dd title={`${ticket.csat_score} / 5`}>
                                        {stars(ticket.csat_score)}
                                        {ticket.csat_comment && <div className="muted">“{ticket.csat_comment}”</div>}
                                    </dd>
                                </>
                            )}
                        </dl>
                        {!isStaff && active && (
                            <button className="btn-danger" onClick={closeTicket} style={{ marginTop: 12 }}>Close ticket</button>
                        )}
                    </div>

                    {!isStaff && !active && !ticket.csat_score && (
                        <RatingCard ticketId={ticket.id} onRated={setTicket} />
                    )}

                    {isStaff && <StaffControls ticket={ticket} onSaved={setTicket} />}

                    <div className="card">
                        <h3 style={{ marginTop: 0 }}>Activity</h3>
                        <ul className="timeline">
                            {ticket.events.map((e) => (
                                <li key={e.id}>
                                    <strong>{e.actor}</strong> {(EVENT_TEXT[e.kind] || (() => e.kind))(e)}
                                    <div className="muted">{when(e.created_at)}</div>
                                </li>
                            ))}
                        </ul>
                    </div>
                </aside>
            </div>
        </div>
    );
};

export default TicketDetail;
