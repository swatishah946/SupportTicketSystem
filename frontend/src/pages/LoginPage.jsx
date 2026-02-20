import React, { useState, useContext } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api';
import { AuthContext } from '../context/AuthContext';

function LoginPage() {
    const navigate = useNavigate();
    const { login } = useContext(AuthContext);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleGoogleSuccess = async (credentialResponse) => {
        try {
            const res = await api.post('/auth/google/', {
                access_token: credentialResponse.credential,
                id_token: credentialResponse.credential
            });
            const { access, refresh, user } = res.data;
            login(user, access, refresh);
            if (user.role === 'admin') {
                navigate('/admin');
            } else if (user.role === 'support_agent') {
                navigate('/agent');
            } else {
                navigate('/dashboard');
            }
        } catch (error) {
            console.error('Google Login failed', error);
            setError('Google Login Failed');
        }
    };

    const handleStandardLogin = async (e) => {
        e.preventDefault();
        setError('');
        try {
            const res = await api.post('/auth/login/', {
                email,
                password
            });
            const { access, refresh, user } = res.data;
            login(user, access, refresh);
            if (user.role === 'admin') {
                navigate('/admin');
            } else if (user.role === 'support_agent') {
                navigate('/agent');
            } else {
                navigate('/dashboard');
            }
        } catch (err) {
            console.error('Login failed', err);
            if (err.response && err.response.data) {
                const data = err.response.data;
                if (data.non_field_errors) {
                    setError(data.non_field_errors.join(' '));
                } else if (typeof data === 'string') {
                    setError('A server error occurred.');
                } else {
                    const errorMessages = Object.values(data).flat().join(' | ');
                    setError(errorMessages || 'Invalid credentials.');
                }
            } else {
                setError('Network error or server unreachable.');
            }
        }
    };

    const containerStyle = {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        marginTop: '50px',
        fontFamily: 'monospace',
    };

    const formStyle = {
        display: 'flex',
        flexDirection: 'column',
        padding: '2rem',
        border: '2px solid black',
        boxShadow: '4px 4px 0px black',
        backgroundColor: 'white',
        width: '300px',
    };

    const inputStyle = {
        padding: '10px',
        marginBottom: '1rem',
        border: '2px solid black',
        fontFamily: 'monospace',
        borderRadius: '0',
    };

    const buttonStyle = {
        padding: '10px',
        backgroundColor: 'black',
        color: 'white',
        border: 'none',
        cursor: 'pointer',
        fontFamily: 'monospace',
        fontWeight: 'bold',
        boxShadow: '4px 4px 0px #888',
        borderRadius: '0',
        marginBottom: '1rem',
    };

    return (
        <div style={containerStyle}>
            <h2 style={{ marginBottom: '20px', textTransform: 'uppercase' }}>Login</h2>

            {error && <div style={{ color: 'red', marginBottom: '10px', fontWeight: 'bold' }}>{error}</div>}

            <form onSubmit={handleStandardLogin} style={formStyle}>
                <label style={{ fontWeight: 'bold', marginBottom: '5px' }}>Email</label>
                <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    style={inputStyle}
                    required
                />

                <label style={{ fontWeight: 'bold', marginBottom: '5px' }}>Password</label>
                <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    style={inputStyle}
                    required
                />

                <button type="submit" style={buttonStyle}>LOGIN</button>

                <div style={{ textAlign: 'center', marginTop: '10px', fontSize: '0.9rem' }}>
                    Need an account? <Link to="/register" style={{ color: 'black', fontWeight: 'bold' }}>Register here</Link>
                </div>
            </form>

            <div style={{ marginTop: '20px' }}>
                <GoogleLogin
                    onSuccess={handleGoogleSuccess}
                    onError={() => setError('Google Login Failed')}
                />
            </div>
        </div>
    );
}

export default LoginPage;
