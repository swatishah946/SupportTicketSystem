import React, { useEffect, useState } from 'react';
import api from '../api';
import { Stat } from './ui';
import { formatMinutes, label, pct } from '../lib/format';

function Breakdown({ title, data }) {
    const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
    return (
        <div className="card">
            <h3 style={{ marginTop: 0 }}>{title}</h3>
            {Object.entries(data).sort((a, b) => b[1] - a[1]).map(([key, n]) => (
                <div key={key} style={{ marginBottom: 6 }}>
                    <div className="row" style={{ justifyContent: 'space-between' }}>
                        <span>{label(key)}</span><strong>{n}</strong>
                    </div>
                    <div style={{ height: 8, border: '1px solid #2a2a2a' }}>
                        <div style={{ width: `${(100 * n) / total}%`, height: '100%', background: '#2a2a2a' }} />
                    </div>
                </div>
            ))}
        </div>
    );
}

/** Admin analytics: SLA performance, AI quality, volume and agent workload. */
const Dashboard = () => {
    const [stats, setStats] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        api.get('/analytics/')
            .then((res) => setStats(res.data))
            .catch(() => setError('Failed to load analytics.'));
    }, []);

    if (error) return <p className="error">{error}</p>;
    if (!stats) return <p>Loading analytics…</p>;

    const { totals, sla, ai } = stats;
    const peak = Math.max(1, ...stats.daily_volume.map((d) => d.count));

    return (
        <div>
            <div className="stats">
                <Stat title="Open queue" value={totals.open + totals.in_progress}
                      hint={`${totals.unassigned} unassigned`} />
                <Stat title="SLA breached now" value={totals.breached_active}
                      hint={`${totals.escalated_active} escalated`} tone={totals.breached_active ? 'bad' : 'good'} />
                <Stat title="Resolved within SLA" value={pct(sla.resolution_compliance_pct)}
                      hint={`first reply in SLA: ${pct(sla.first_response_compliance_pct)}`} />
                <Stat title="Avg first response" value={formatMinutes(sla.avg_first_response_minutes)} />
                <Stat title="Avg resolution" value={formatMinutes(sla.avg_resolution_minutes)} />
                <Stat title="AI triage kept by agents" value={pct(ai.category_agreement_pct)}
                      hint={`priority kept: ${pct(ai.priority_agreement_pct)} · n=${ai.labelled_tickets}`} />
            </div>

            <div className="card" style={{ marginTop: 20 }}>
                <h3 style={{ marginTop: 0 }}>New tickets, last 14 days</h3>
                <div className="bars">
                    {stats.daily_volume.map((d) => (
                        <div key={d.date} className="bar" style={{ height: `${(100 * d.count) / peak}%` }}
                             title={`${d.date}: ${d.count}`}>
                            {d.count > 0 && <span>{d.count}</span>}
                        </div>
                    ))}
                </div>
                <div className="bar-labels">
                    {stats.daily_volume.map((d) => <span key={d.date}>{d.date.slice(8)}</span>)}
                </div>
            </div>

            <div className="grid" style={{ marginTop: 20 }}>
                <Breakdown title="By priority" data={stats.by_priority} />
                <Breakdown title="By category" data={stats.by_category} />
                <Breakdown title="By status" data={stats.by_status} />
            </div>

            <h3 className="section-title">Agent workload</h3>
            <div className="table-wrap">
                <table className="data">
                    <thead>
                        <tr><th>Agent</th><th>Role</th><th>Active</th><th>Breached</th><th>Resolved (7d)</th></tr>
                    </thead>
                    <tbody>
                        {stats.agents.map((a) => (
                            <tr key={a.id}>
                                <td>{a.username}<div className="muted" style={{ fontSize: '0.75rem' }}>{a.email}</div></td>
                                <td>{label(a.role)}</td>
                                <td>{a.active}</td>
                                <td style={{ color: a.breached ? '#b00020' : undefined, fontWeight: a.breached ? 'bold' : undefined }}>
                                    {a.breached}
                                </td>
                                <td>{a.resolved_7d}</td>
                            </tr>
                        ))}
                        {stats.agents.length === 0 && <tr><td colSpan="5">No agents yet.</td></tr>}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default Dashboard;
