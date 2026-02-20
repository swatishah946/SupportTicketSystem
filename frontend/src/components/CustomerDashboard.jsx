import React from 'react';
import { Link } from 'react-router-dom';
import TicketList from './TicketList';

const CustomerDashboard = () => {
    return (
        <div style={{ padding: '20px', fontFamily: 'monospace' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h1 style={{ textTransform: 'uppercase' }}>My Dashboard</h1>
                <Link to="/new">
                    <button style={{
                        padding: '10px 20px',
                        backgroundColor: 'black',
                        color: 'white',
                        border: '2px solid black',
                        boxShadow: '4px 4px 0px #888',
                        cursor: 'pointer',
                        fontWeight: 'bold',
                        textTransform: 'uppercase'
                    }}>
                        Create New Ticket
                    </button>
                </Link>
            </div>

            <section>
                <h2 style={{ textTransform: 'uppercase', borderBottom: '2px solid black', paddingBottom: '10px' }}>My Tickets</h2>
                <TicketList />
            </section>
        </div>
    );
};

export default CustomerDashboard;
