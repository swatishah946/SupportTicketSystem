import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import TicketForm from './components/TicketForm';
import TicketList from './components/TicketList';
import Dashboard from './components/Dashboard';

function App() {
  const handleTicketCreated = () => {
    // Optionally refresh list or navigate
    window.location.reload(); // Simple refresh for now
  };

  return (
    <Router>
      <div className="container">
        <nav>
          <div>
            <span style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>TICKET SYSTEM v1.0</span>
          </div>
          <div>
            <Link to="/">Dashboard</Link>
            <Link to="/tickets">Tickets</Link>
            <Link to="/new">New Ticket</Link>
          </div>
        </nav>

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tickets" element={<TicketList />} />
          <Route path="/new" element={<TicketForm onTicketCreated={handleTicketCreated} />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
