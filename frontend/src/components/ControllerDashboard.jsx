import React from 'react';
import TicketList from './TicketList';

const ControllerDashboard = () => {
    return (
        <div style={{ padding: '20px', fontFamily: 'monospace' }}>
            <div style={{ marginBottom: '20px' }}>
                <h1 style={{ textTransform: 'uppercase', borderBottom: '2px solid black', paddingBottom: '10px' }}>Agent Dashboard</h1>
                <p>Welcome to the support queue. Below are the open and assigned tickets awaiting resolution.</p>
            </div>

            <section>
                <TicketList splitByAssignment={true} />
            </section>
        </div>
    );
};

export default ControllerDashboard;
