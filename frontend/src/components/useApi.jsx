import { useEffect, useState } from "react";

/** Fetch helper: re-runs when deps change, ignores stale responses. */
export function useApi(fn, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error) => live && setState({ data: null, error, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function Status({ loading, error, empty, children }) {
  if (error) return <p className="error">{error.message}. Check that the API is running on port 8000.</p>;
  if (loading) return <p className="empty">Loading…</p>;
  if (empty) return <p className="empty">{empty}</p>;
  return children;
}
