import React from 'react';
import { Link } from 'react-router-dom';
import Dashboard from './Dashboard';
import TicketList from './TicketList';

const AdminDashboard = () => {
    return (
        <div style={{ padding: '20px', fontFamily: 'monospace' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h1 style={{ textTransform: 'uppercase' }}>Admin Dashboard</h1>
                <Link to="/manage-users">
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
                        Manage User Accounts
                    </button>
                </Link>
            </div>

            <section style={{ marginBottom: '40px' }}>
                <h2 style={{ textTransform: 'uppercase', borderBottom: '2px solid black', paddingBottom: '10px' }}>System Overview</h2>
                <Dashboard />
            </section>

            <section>
                <h2 style={{ textTransform: 'uppercase', borderBottom: '2px solid black', paddingBottom: '10px' }}>All Tickets</h2>
                <TicketList />
            </section>
        </div>
    );
};

export default AdminDashboard;
