/**
 * API client dùng chung.
 * - Luôn gọi đường dẫn TƯƠNG ĐỐI (/api/v1, /public/v1) → chạy local qua Vite proxy,
 *   chạy cloud qua Nginx cùng origin. KHÔNG hardcode host.
 * - Không đưa secret vào FE. JWT chỉ lưu trong memory (module này).
 */

let accessToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export interface ApiErrorBody {
  code?: string;
  message?: string;
  detail?: string | { code?: string; message?: string };
  correlation_id?: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  correlationId?: string;
  body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    const code = body.code ?? (typeof body.detail === 'object' ? body.detail?.code : undefined) ?? 'HTTP_ERROR';
    const message =
      body.message ??
      (typeof body.detail === 'string' ? body.detail : undefined) ??
      (typeof body.detail === 'object' ? body.detail?.message : undefined) ??
      'Request failed';
    super(message);
    this.status = status;
    this.code = code;
    this.body = body;
    this.correlationId = body.correlation_id;
  }
}

async function readBody(res: Response): Promise<ApiErrorBody> {
  try {
    const text = await res.text();
    if (!text) return {};
    const parsed = JSON.parse(text);
    return typeof parsed === 'object' && parsed !== null ? parsed : { message: text };
  } catch {
    return {};
  }
}

async function request<T>(
  method: string,
  path: string,
  options: {
    body?: unknown;
    auth?: boolean;
    headers?: Record<string, string>;
  } = {},
): Promise<T> {
  const { body, auth = true, headers = {} } = options;

  const finalHeaders: Record<string, string> = {
    Accept: 'application/json',
    ...headers,
  };

  if (body !== undefined) finalHeaders['Content-Type'] = 'application/json';
  if (auth && accessToken) finalHeaders.Authorization = `Bearer ${accessToken}`;

  const res = await fetch(path, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    setAccessToken(null);
    onUnauthorized?.();
  }

  if (!res.ok) {
    const errBody = await readBody(res);
    throw new ApiError(res.status, errBody);
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export const api = {
  get: <T>(path: string, opts?: { auth?: boolean; headers?: Record<string, string> }) =>
    request<T>('GET', path, opts),
  post: <T>(path: string, body?: unknown, opts?: { auth?: boolean; headers?: Record<string, string> }) =>
    request<T>('POST', path, { ...opts, body }),
  patch: <T>(path: string, body?: unknown, opts?: { auth?: boolean; headers?: Record<string, string> }) =>
    request<T>('PATCH', path, { ...opts, body }),
  delete: <T>(path: string, opts?: { auth?: boolean; headers?: Record<string, string> }) =>
    request<T>('DELETE', path, opts),
};