import React from 'react';
import { label, timeFromNow } from '../lib/format';

export function Badge({ kind = 'status', value }) {
    return <span className={`badge badge-${kind} badge-${kind}-${value}`}>{label(value)}</span>;
}

const SLA_TEXT = {
    on_track: 'SLA on track',
    at_risk: 'SLA at risk',
    breached: 'SLA breached',
    met: 'SLA met',
};

export function SlaBadge({ ticket }) {
    const state = ticket.sla_state;
    if (!state || state === 'none') return null;
    const active = ticket.status === 'open' || ticket.status === 'in_progress';
    const due = active && ticket.resolution_due ? ` · due ${timeFromNow(ticket.resolution_due)}` : '';
    return <span className={`badge badge-sla badge-sla-${state}`} title="Resolution SLA">{SLA_TEXT[state]}{due}</span>;
}

export function Stat({ title, value, hint, tone }) {
    return (
        <div className={`stat ${tone ? `stat-${tone}` : ''}`}>
            <div className="stat-title">{title}</div>
            <div className="stat-value">{value}</div>
            {hint && <div className="stat-hint">{hint}</div>}
        </div>
    );
}

export function Pager({ page, count, pageSize, onChange }) {
    const pages = Math.max(1, Math.ceil(count / pageSize));
    if (pages <= 1) return null;
    return (
        <div className="pager">
            <button disabled={page <= 1} onClick={() => onChange(page - 1)}>Prev</button>
            <span>Page {page} / {pages} · {count} tickets</span>
            <button disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button>
        </div>
    );
}
