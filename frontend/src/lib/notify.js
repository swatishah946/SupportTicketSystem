import { label } from './format';

/**
 * Decide whether a live ticket event deserves a pop-up for this user.
 * Returns the message text, or null. Your own actions never notify you.
 */
export function notificationFor(event, user) {
    if (!user || event.actor_id === user.id) return null;
    const t = `#${event.ticket}`;
    const fields = event.fields || [];

    if (user.role === 'customer') {
        if (event.change === 'comment') return `New reply on ${t} from ${event.actor}`;
        if (event.change === 'updated' && fields.includes('status')) return `${t} is now ${label(event.status)}`;
        return null;
    }

    const mine = event.assigned_to === user.id;
    if (event.change === 'created' && mine) return `New ticket ${t} assigned to you`;
    if (event.change === 'updated' && fields.includes('assigned_to') && mine) return `${t} was assigned to you`;
    if (event.change === 'comment' && mine) return `${event.actor} replied on ${t}`;
    if (event.change === 'rated' && mine) return `${t} was rated by the customer`;
    if (event.change === 'escalated' && (mine || user.role === 'admin')) return `${t} escalated: past its deadline`;
    return null;
}
