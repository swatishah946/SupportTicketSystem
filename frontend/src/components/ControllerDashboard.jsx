import React from 'react';
import TicketList from './TicketList';

/** Agent home: their own queue sorted by SLA deadline, then the shared pool. */
const ControllerDashboard = () => (
    <div className="page">
        <div className="page-head">
            <h1>Agent dashboard</h1>
        </div>

        <h2 className="section-title">My queue (most urgent deadline first)</h2>
        <TicketList preset={{ assigned_to: 'me', active: true, ordering: 'resolution_due' }} showFilters={false}
                    emptyText="Nothing assigned to you. Pick something from the unassigned pool." />

        <h2 className="section-title">Unassigned</h2>
        <TicketList preset={{ unassigned: true, active: true, ordering: 'resolution_due' }} showFilters={false}
                    emptyText="No unassigned tickets." />

        <h2 className="section-title">Breaching SLA (all agents)</h2>
        <TicketList preset={{ sla_breached: true, ordering: 'resolution_due' }} showFilters={false}
                    emptyText="No active ticket is past its SLA." />
    </div>
);

export default ControllerDashboard;
