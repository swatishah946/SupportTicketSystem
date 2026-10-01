import React, { useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { AuthContext } from '../context/auth';
import { useDebouncedTicketEvents } from '../context/realtime';
import { Badge, Pager, SlaBadge } from './ui';
import { CATEGORIES, label, PRIORITIES, STATUSES } from '../lib/format';

const PAGE_SIZE = 12;

function TicketCard({ ticket, isCustomer }) {
    const navigate = useNavigate();
    const text = ticket.description.length > 110 ? `${ticket.description.slice(0, 110)}…` : ticket.description;
    return (
        <div className="ticket-card" onClick={() => navigate(`/tickets/${ticket.id}`)}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
                <h4>#{ticket.id} {ticket.title}</h4>
                <Badge value={ticket.status} />
            </div>
            <div className="row">
                <Badge kind="priority" value={ticket.priority} />
                <SlaBadge ticket={ticket} />
                {ticket.escalated && <span className="badge badge-sla-breached">Escalated</span>}
                {isCustomer && ticket.has_unread_updates && <span className="badge badge-new">New reply</span>}
            </div>
            <p>{text}</p>
            <div className="meta">
                <span>{label(ticket.category)} · {ticket.comment_count} repl{ticket.comment_count === 1 ? 'y' : 'ies'}</span>
                <span>{ticket.assigned_to ? `@${ticket.assigned_to.username}` : 'Unassigned'}</span>
            </div>
        </div>
    );
}

/**
 * Server-driven ticket list. `preset` holds fixed query params for a queue
 * (e.g. {assigned_to: 'me', active: true}); filters are added on top of it.
 */
const TicketList = ({ preset = {}, showFilters = true, emptyText = 'No tickets match your filters.' }) => {
    const { user } = useContext(AuthContext);
    const [response, setResponse] = useState({ key: null, data: { results: [], count: 0 }, error: '' });
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [filters, setFilters] = useState({ status: '', priority: '', category: '' });
    const [version, setVersion] = useState(0); // bumped by live updates to re-fetch

    useDebouncedTicketEvents(() => setVersion((v) => v + 1));

    // Everything that defines the request, as one stable key.
    const requestKey = JSON.stringify({ ...preset, ...filters, search: debouncedSearch, page, page_size: PAGE_SIZE });
    const fetchKey = `${requestKey}#${version}`;
    const loading = response.key === null;
    // Dim while the user's own filter/page change loads; live refreshes swap data in silently.
    const refreshing = !loading && response.key.split('#')[0] !== requestKey;
    const { data, error } = response;

    useEffect(() => {
        const t = setTimeout(() => {
            setDebouncedSearch(search.trim());
            setPage(1);
        }, 300);
        return () => clearTimeout(t);
    }, [search]);

    useEffect(() => {
        let cancelled = false;
        const params = Object.fromEntries(Object.entries(JSON.parse(fetchKey.split('#')[0])).filter(([, v]) => v !== ''));
        api.get('/tickets/', { params })
            .then((res) => { if (!cancelled) setResponse({ key: fetchKey, data: res.data, error: '' }); })
            .catch(() => {
                if (!cancelled) setResponse((r) => ({ ...r, key: fetchKey, error: 'Failed to load tickets.' }));
            });
        return () => { cancelled = true; };
    }, [fetchKey]);

    const setFilter = (key) => (e) => {
        setFilters((f) => ({ ...f, [key]: e.target.value }));
        setPage(1);
    };

    return (
        <div>
            {showFilters && (
                <div className="filters">
                    <input placeholder="Search title or description…" value={search}
                           onChange={(e) => setSearch(e.target.value)} />
                    <select value={filters.status} onChange={setFilter('status')}>
                        <option value="">All statuses</option>
                        {STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
                    </select>
                    <select value={filters.priority} onChange={setFilter('priority')}>
                        <option value="">All priorities</option>
                        {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                    <select value={filters.category} onChange={setFilter('category')}>
                        <option value="">All categories</option>
                        {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                </div>
            )}
            {error && <p className="error">{error}</p>}
            {loading && !data.results.length ? (
                <p>Loading tickets…</p>
            ) : data.results.length === 0 ? (
                <p className="empty">{emptyText}</p>
            ) : (
                <div className="ticket-grid" style={{ opacity: refreshing ? 0.6 : 1 }}>
                    {data.results.map((t) => <TicketCard key={t.id} ticket={t} isCustomer={user?.role === 'customer'} />)}
                </div>
            )}
            <Pager page={page} count={data.count} pageSize={PAGE_SIZE} onChange={setPage} />
        </div>
    );
};

export default TicketList;
