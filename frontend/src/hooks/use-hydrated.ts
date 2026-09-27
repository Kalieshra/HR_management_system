'use client';

import { useEffect, useState } from 'react';

/**
 * False during server rendering and until React has hydrated on the client.
 *
 * Forms use this to keep their submit button disabled until the React handler
 * is attached. Without it, a click on a not-yet-hydrated page performs the
 * browser's *native* form submission — a GET that puts every field, passwords
 * included, into the URL, the browser history and the server log.
 */
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  return hydrated;
}
