/**
 * API client.
 *
 * Auth is a JWT in an HttpOnly cookie that Django sets, so every request just
 * sends `credentials: 'include'` — the token is never readable from JS. The
 * active tenant travels in the `X-Company-Id` header, which the backend
 * validates against the user's memberships on every request.
 *
 * The access cookie lives 30 minutes and the refresh cookie 14 days, so a 401
 * is the *expected* steady state of a tab left open — see `apiFetch`.
 */

import { routing } from '@/i18n/routing';

const BROWSER_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8010';
const SERVER_BASE = process.env.INTERNAL_API_URL ?? BROWSER_BASE;

export const COMPANY_COOKIE = 'hrms_company';

export function apiUrl(path: string): string {
  const base = typeof window === 'undefined' ? SERVER_BASE : BROWSER_BASE;
  return `${base.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;
}

export class ApiError extends Error {
  status: number;
  /** DRF field errors, e.g. `{ code: ['This code is already in use.'] }`. */
  fields: Record<string, string[]>;

  constructor(status: number, message: string, fields: Record<string, string[]> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
  }

  /** 409 — the month is closed and must be reopened before editing. */
  get isPeriodClosed() {
    return this.status === 409;
  }
}

function readCompanyCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${COMPANY_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
  companyId?: string | number | null;
  /** Send a FormData body untouched (file uploads). */
  formData?: FormData;
};

async function parseError(response: Response): Promise<ApiError> {
  let detail = `HTTP ${response.status}`;
  let fields: Record<string, string[]> = {};

  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') {
      detail = data.detail;
    } else if (data && typeof data === 'object') {
      fields = Object.fromEntries(
        Object.entries(data).map(([key, value]) => [
          key,
          Array.isArray(value) ? value : [String(value)],
        ]),
      );
      const first = Object.values(fields)[0];
      if (first?.length) detail = first[0];
    }
  } catch {
    // Non-JSON error body (a 502 page, say) — keep the status line.
  }

  return new ApiError(response.status, detail, fields);
}

function send(path: string, options: RequestOptions): Promise<Response> {
  const { body, companyId, formData, headers, ...rest } = options;

  const activeCompany = companyId ?? readCompanyCookie();
  const finalHeaders = new Headers(headers);
  if (activeCompany) finalHeaders.set('X-Company-Id', String(activeCompany));
  if (body !== undefined && !formData) finalHeaders.set('Content-Type', 'application/json');

  return fetch(apiUrl(path), {
    ...rest,
    headers: finalHeaders,
    credentials: 'include',
    body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
  });
}

async function readBody<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) return (await response.blob()) as T;
  return (await response.json()) as T;
}

/** The auth dance itself — refreshing these on a 401 would only loop. */
const AUTH_PATHS = ['/api/v1/auth/login', '/api/v1/auth/refresh', '/api/v1/auth/logout'];

type RefreshOutcome =
  /** A new access cookie is set — replay the request. */
  | 'ok'
  /** The backend refused the token: the session is over. */
  | 'expired'
  /** Network error, throttle, 5xx — unknown, so leave the session alone. */
  | 'unreachable';

/**
 * The in-flight refresh, so a burst of 401s buys exactly one new token.
 *
 * A page paints half a dozen queries at once, and they all expire together.
 * `ROTATE_REFRESH_TOKENS` is on, so parallel refreshes would each mint a new
 * refresh token and only the last one to land would still be valid.
 */
let refreshing: Promise<RefreshOutcome> | null = null;

function refreshSession(): Promise<RefreshOutcome> {
  if (!refreshing) {
    const attempt: Promise<RefreshOutcome> = fetch(apiUrl('/api/v1/auth/refresh'), {
      method: 'POST',
      credentials: 'include',
    })
      .then((response) => {
        if (response.ok) return 'ok';
        // Only a refusal of the token itself ends the session. A 429 from the
        // auth throttle or a 502 must not sign a perfectly valid user out.
        return response.status === 401 || response.status === 403 ? 'expired' : 'unreachable';
      })
      .catch(() => 'unreachable' as const);

    refreshing = attempt;
    // Free the slot once it settles, so the next expiry can refresh again.
    void attempt.finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

let endingSession = false;

/**
 * Leave the app when the session is gone for good.
 *
 * The Next middleware only checks that *a* cookie exists, and the refresh
 * cookie outlives the access one by 14 days — so without this the user sits in
 * a signed-in shell where every query returns nothing and no page ever says why.
 *
 * Clearing the cookies first is not tidiness. That same middleware bounces
 * anyone holding a cookie *off* `/login`, so redirecting while the dead one is
 * still set ping-pongs between the two pages. `/auth/logout` is `AllowAny` and
 * clears them whatever state the token is in.
 */
async function endSession() {
  if (typeof window === 'undefined' || endingSession) return;
  endingSession = true;

  await fetch(apiUrl('/api/v1/auth/logout'), { method: 'POST', credentials: 'include' }).catch(
    () => undefined,
  );

  const { pathname, search, origin } = window.location;
  const [, first] = pathname.split('/');
  const locale = (routing.locales as readonly string[]).includes(first)
    ? first
    : routing.defaultLocale;
  const path = pathname.startsWith(`/${locale}`) ? pathname.slice(locale.length + 1) : pathname;
  if (path === '/login') return;

  const url = new URL(`/${locale}/login`, origin);
  if (path && path !== '/') url.searchParams.set('next', `${path}${search}`);
  window.location.replace(url.toString());
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const response = await send(path, options);

  // A 401 on a signed-in tab usually just means the 30-minute access token
  // aged out. Trade the 14-day refresh cookie for a new one and replay the
  // request; only give up — and say so — when that fails too.
  if (
    response.status === 401 &&
    typeof window !== 'undefined' &&
    !AUTH_PATHS.some((auth) => path.startsWith(auth))
  ) {
    const outcome = await refreshSession();
    if (outcome === 'ok') {
      const retried = await send(path, options);
      if (!retried.ok) throw await parseError(retried);
      return readBody<T>(retried);
    }
    if (outcome === 'expired') await endSession();
  }

  if (!response.ok) throw await parseError(response);
  return readBody<T>(response);
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'PUT', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: 'POST', formData }),
};
