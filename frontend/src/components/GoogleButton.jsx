import React, { useEffect, useState } from 'react';
import { GoogleLogin, GoogleOAuthProvider } from '@react-oauth/google';
import { loadConfig } from '../lib/config';

/**
 * "Sign in with Google" button. Renders nothing unless the server has a
 * Google Client ID configured. On success it hands Google's signed ID token
 * (the "credential") to `onCredential`; the backend verifies it.
 */
const GoogleButton = ({ onCredential, onError, text = 'signin_with' }) => {
    const [clientId, setClientId] = useState(null);

    useEffect(() => {
        let active = true;
        loadConfig().then((config) => { if (active) setClientId(config.google_client_id); });
        return () => { active = false; };
    }, []);

    if (!clientId) return null;
    return (
        <div style={{ marginTop: '20px' }} data-testid="google-signin">
            <GoogleOAuthProvider clientId={clientId}>
                <GoogleLogin
                    text={text}
                    onSuccess={(response) => onCredential(response.credential)}
                    onError={() => onError('Google sign-in was cancelled or failed.')}
                />
            </GoogleOAuthProvider>
        </div>
    );
};

export default GoogleButton;
