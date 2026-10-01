import api from '../api';

// Runtime config from the backend (e.g. the Google Client ID), fetched once.
// Served by the API so one GOOGLE_CLIENT_ID setting configures both halves
// and the frontend never needs rebuilding per environment.
let pending = null;

export function loadConfig() {
    pending = pending || api.get('/auth/config/')
        .then((res) => res.data)
        .catch(() => {
            pending = null; // retry on the next call
            return { google_client_id: null };
        });
    return pending;
}
