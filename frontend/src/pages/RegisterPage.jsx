import React, { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api';

function RegisterPage() {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');

    const handleGoogleSuccess = async (credentialResponse) => {
        // ... (existing google logic)
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setError('');

        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        if (password.length < 8) {
            setError('Password must be at least 8 characters');
            return;
        }

        try {
            const derivedUsername = email.split('@')[0] + Math.floor(Math.random() * 1000);

            await api.post('/auth/registration/', {
                username: derivedUsername,
                email: email,
                password1: password,
                password2: confirmPassword
            });
            alert('Account created! Please log in.');
            navigate('/login');
        } catch (err) {
            console.error('Registration failed', err);
            if (err.response && err.response.data) {
                const data = err.response.data;
                if (typeof data === 'string') {
                    // Likely a 500 HTML error page
                    setError('A server error occurred. Please try again later.');
                } else if (typeof data === 'object') {
                    // Extract all error messages from the object (e.g. {"email": ["Invalid"], "password": ["Too short"]})
                    const errorMessages = Object.values(data)
                        .flat()
                        .join(' | ');
                    setError(errorMessages || 'Registration failed.');
                } else {
                    setError('Registration failed.');
                }
            } else {
                setError('Network error. Cannot reach server.');
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
            <h2 style={{ marginBottom: '20px', textTransform: 'uppercase' }}>Register</h2>

            {error && <div style={{ color: 'red', marginBottom: '10px', fontWeight: 'bold', maxWidth: '300px', wordWrap: 'break-word' }}>{error}</div>}

            <form onSubmit={handleRegister} style={formStyle}>
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

                <label style={{ fontWeight: 'bold', marginBottom: '5px' }}>Confirm Password</label>
                <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    style={inputStyle}
                    required
                />

                <button type="submit" style={buttonStyle}>REGISTER</button>

                <div style={{ textAlign: 'center', marginTop: '10px', fontSize: '0.9rem' }}>
                    Already have an account? <Link to="/login" style={{ color: 'black', fontWeight: 'bold' }}>Login here</Link>
                </div>
            </form>

            <div style={{ marginTop: '20px' }}>
                <GoogleLogin
                    onSuccess={handleGoogleSuccess}
                    onError={() => setError('Google Registration Failed')}
                    text="signup_with"
                />
            </div>
        </div>
    );
}

export default RegisterPage;
