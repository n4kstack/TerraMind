import { useEffect, useState } from 'react';

/**
 * Subscribe to a media query.
 *
 * Used to shed animated detail on small screens rather than to change layout —
 * layout breakpoints belong in CSS, where they cost nothing. This exists for
 * the cases CSS cannot reach: how many elements JavaScript animates per frame.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  );

  useEffect(() => {
    const list = window.matchMedia(query);
    const sync = () => setMatches(list.matches);
    sync();
    list.addEventListener('change', sync);
    return () => list.removeEventListener('change', sync);
  }, [query]);

  return matches;
}
