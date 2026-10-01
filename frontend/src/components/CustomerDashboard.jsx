import React from 'react';
import { Link } from 'react-router-dom';
import TicketList from './TicketList';

const CustomerDashboard = () => (
    <div className="page">
        <div className="page-head">
            <h1>My tickets</h1>
            <Link to="/new"><button className="btn-primary">New ticket</button></Link>
        </div>
        <TicketList emptyText="You haven't raised any tickets yet." />
    </div>
);

export default CustomerDashboard;
