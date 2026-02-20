import React, { useContext } from 'react';
import { Link } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

const NavBar = () => {
    const { user, logout } = useContext(AuthContext);

    const navStyle = {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '1rem 2rem',
        borderBottom: '2px solid black',
        backgroundColor: '#fff',
        fontFamily: 'monospace',
    };

    const logoStyle = {
        fontSize: '1.5rem',
        fontWeight: 'bold',
        textDecoration: 'none',
        color: 'black',
    };

    const linkStyle = {
        margin: '0 1rem',
        textDecoration: 'none',
        color: 'black',
        fontWeight: 'bold',
    };

    const buttonStyle = {
        padding: '0.5rem 1rem',
        backgroundColor: 'black',
        color: 'white',
        border: 'none',
        cursor: 'pointer',
        fontFamily: 'monospace',
        fontWeight: 'bold',
        boxShadow: '4px 4px 0px #888', // Hard shadow
        marginLeft: '1rem',
    };

    // Tech Blueprint Theme: Monospace, Sharp edges, Thick borders
    const techBtnStyle = {
        ...buttonStyle,
        borderRadius: '0',
        border: '2px solid black',
        backgroundColor: 'white',
        color: 'black',
        boxShadow: '4px 4px 0px black',
        transition: 'transform 0.1s',
    };

    return (
        <nav style={navStyle}>
            <Link to="/" style={logoStyle}>TICKET_SYSTEM</Link>
            <div>
                {!user ? (
                    <>
                        <Link to="/login" style={linkStyle}>LOGIN</Link>
                        <Link to="/register" style={techBtnStyle}>REGISTER</Link>
                    </>
                ) : (
                    <>
                        {user.role === 'admin' && (
                            <>
                                <Link to="/" style={linkStyle}>DASHBOARD</Link>
                                <Link to="/tickets" style={linkStyle}>ALL TICKETS</Link>
                            </>
                        )}
                        {user.role === 'support_agent' && (
                            <Link to="/tickets" style={linkStyle}>ALL TICKETS</Link>
                        )}
                        {user.role === 'customer' && (
                            <Link to="/tickets" style={linkStyle}>MY TICKETS</Link>
                        )}

                        <Link to="/new" style={linkStyle}>NEW TICKET</Link>

                        <button onClick={logout} style={techBtnStyle}>LOGOUT</button>
                    </>
                )}
            </div>
        </nav>
    );
};

export default NavBar;
