import { createContext, useContext, useEffect, useRef } from 'react';

// Live updates: one WebSocket per tab (see RealtimeProvider). Components either
// read the connection status or subscribe to ticket events.
export const RealtimeContext = createContext({ status: 'offline', subscribe: () => () => {} });

export function useRealtimeStatus() {
    return useContext(RealtimeContext).status;
}

/** Call `handler(event)` for every ticket event while the component is mounted. */
export function useTicketEvents(handler) {
    const { subscribe } = useContext(RealtimeContext);
    const latest = useRef(handler);
    useEffect(() => {
        latest.current = handler;
    });
    useEffect(() => subscribe((event) => latest.current(event)), [subscribe]);
}

/** Like useTicketEvents, but coalesces bursts into one call after `delay` ms. */
export function useDebouncedTicketEvents(handler, delay = 400) {
    const timer = useRef(null);
    useEffect(() => () => clearTimeout(timer.current), []);
    useTicketEvents((event) => {
        clearTimeout(timer.current);
        timer.current = setTimeout(() => handler(event), delay);
    });
}
