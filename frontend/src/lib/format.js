// Plain helpers shared by components (kept out of .jsx for fast refresh).

export const PRIORITIES = ['low', 'medium', 'high', 'critical'];
export const CATEGORIES = ['billing', 'technical', 'account', 'general'];
export const STATUSES = ['open', 'in_progress', 'resolved', 'closed'];

export const label = (value) => (value || '').replace(/_/g, ' ');

export function timeFromNow(iso) {
    if (!iso) return '';
    const diffMin = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
    const abs = Math.abs(diffMin);
    const text = abs < 60 ? `${abs}m` : abs < 60 * 48 ? `${Math.round(abs / 60)}h` : `${Math.round(abs / 1440)}d`;
    return diffMin >= 0 ? `in ${text}` : `${text} ago`;
}

/** Deadline wording: "due in 3h" before it, "overdue 2d" after it. */
export function deadline(iso) {
    if (!iso) return '';
    const text = timeFromNow(iso);
    return text.startsWith('in ') ? `due ${text}` : `overdue ${text.replace(' ago', '')}`;
}

export function formatMinutes(minutes) {
    if (minutes === null || minutes === undefined) return '—';
    if (minutes < 60) return `${Math.round(minutes)}m`;
    if (minutes < 60 * 48) return `${(minutes / 60).toFixed(1)}h`;
    return `${(minutes / 1440).toFixed(1)}d`;
}

export const pct = (value) => (value === null || value === undefined ? '—' : `${value}%`);
