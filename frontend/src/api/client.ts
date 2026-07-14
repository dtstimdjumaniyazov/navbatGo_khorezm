import {
  Appointment,
  AppointmentCreatePayload,
  AppointmentStatus,
  Bay,
  Service,
  ServicePoint,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api';
const TOKEN_KEY = 'navbatgo_access';
const REFRESH_KEY = 'navbatgo_refresh';

// Публичные страницы политики/оферты отдаёт сам Django (не /api) — тот же
// хост, что и API, без суффикса /api
const SERVER_ROOT = BASE_URL.replace(/\/api\/?$/, '');
export function legalUrls(lang: 'ru' | 'uz') {
  const suffix = lang === 'uz' ? 'uz/' : '';
  return {
    privacy: `${SERVER_ROOT}/legal/privacy/${suffix}`,
    oferta: `${SERVER_ROOT}/legal/oferta/${suffix}`,
  };
}

// Кнопка «Хочу подключить автосервис» — открывает чат с контактом владельца
// платформы; null, если контакт не настроен (кнопка тогда просто не рисуется)
const PARTNER_USERNAME = import.meta.env.VITE_PARTNER_CONTACT_USERNAME ?? '';
export function partnerContactUrl(lang: 'ru' | 'uz'): string | null {
  if (!PARTNER_USERNAME) return null;
  const text =
    lang === 'uz'
      ? 'Ассалому алайкум! Автосервисимни NavbatGo’га улашни хоҳлайман.'
      : 'Здравствуйте! Хочу подключить свой автосервис к NavbatGo.';
  return `https://t.me/${PARTNER_USERNAME}?text=${encodeURIComponent(text)}`;
}

let authToken: string | null = localStorage.getItem(TOKEN_KEY);

export function setTokens(access: string | null, refresh?: string | null) {
  authToken = access;
  if (access) localStorage.setItem(TOKEN_KEY, access);
  else localStorage.removeItem(TOKEN_KEY);
  if (refresh !== undefined) {
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
    else localStorage.removeItem(REFRESH_KEY);
  }
}

export function hasToken(): boolean {
  return !!authToken;
}

// App регистрирует обработчик: токен протух → показать экран входа
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** тело ошибки сервера (например, needs_shift/conflicts у продления) */
    public body?: Record<string, unknown>,
  ) {
    super(message);
  }
}

interface RequestOpts {
  withAuth?: boolean;
  allowRefresh?: boolean;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  { withAuth = true, allowRefresh = true }: RequestOpts = {},
): Promise<T> {
  // Для FormData Content-Type ставит браузер (с boundary), руками нельзя
  const isForm = options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isForm ? {} : { 'Content-Type': 'application/json' }),
    // Бесплатный ngrok отдаёт HTML-предупреждение вместо ответа API,
    // если не передать этот заголовок; вне ngrok он безвреден
    'ngrok-skip-browser-warning': 'true',
    ...(options.headers as Record<string, string>),
  };
  if (withAuth && authToken) headers['Authorization'] = `Bearer ${authToken}`;

  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, 'Нет подключения к серверу');
  }
  if (resp.status === 401 && withAuth) {
    // Пробуем обновить access по refresh-токену — один раз, без рекурсии
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (refresh && allowRefresh) {
      try {
        const fresh = await request<{ access: string }>(
          '/auth/refresh/',
          { method: 'POST', body: JSON.stringify({ refresh }) },
          { withAuth: false },
        );
        setTokens(fresh.access);
        return request<T>(path, options, { allowRefresh: false });
      } catch {
        /* refresh тоже протух — выходим на экран входа */
      }
    }
    setTokens(null, null);
    onUnauthorized?.();
    throw new ApiError(401, 'Требуется вход');
  }
  if (!resp.ok) {
    let detail = `Ошибка ${resp.status}`;
    let body: Record<string, unknown> | undefined;
    try {
      body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* тело не JSON — оставляем код */
    }
    throw new ApiError(resp.status, detail, body);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export interface ClientInfo {
  id: string;
  name: string;
  phone: string;
  language: 'ru' | 'uz';
}

export interface MeResponse {
  username: string;
  manager: {
    name: string;
    role: string;
    service_point: string;
    service_point_name: string;
  } | null;
  client: ClientInfo | null;
}

// Публичная витрина (клиентский каталог)
export interface PublicMediaItem {
  id: string;
  media_type: 'photo' | 'video';
  image: string | null;
  video_url: string;
  caption: string;
  order: number;
}

export interface PublicManager {
  id: string;
  name: string;
  bio: string;
  bio_uz: string;
  experience_years: number | null;
  avatar: string | null;
  role: string;
}

export interface PublicService {
  id: string;
  name: string;
  name_uz: string;
  service_type: 'fixed' | 'flexible';
  duration_minutes: number;
  price: string | null;
}

export interface ScheduleDay {
  weekday: number; // 0=Пн … 6=Вс
  start: string | null; // null — выходной
  end: string | null;
}

export interface PublicPoint {
  id: string;
  name: string;
  description: string;
  description_uz: string;
  address: string;
  address_uz: string;
  schedule: ScheduleDay[];
  latitude: string | null;
  longitude: string | null;
  instagram: string;
  work_start: string;
  work_end: string;
  work_days: number[];
  media: PublicMediaItem[];
  managers: PublicManager[];
  services: PublicService[];
}

export const api = {
  login: async (username: string, password: string) => {
    const tokens = await request<{ access: string; refresh: string }>(
      '/auth/login/',
      { method: 'POST', body: JSON.stringify({ username, password }) },
      { withAuth: false },
    );
    setTokens(tokens.access, tokens.refresh);
  },

  logout: () => setTokens(null, null),

  // Вход через Telegram (device-code flow): start → пользователь жмёт Start
  // в боте → poll возвращает токены
  tgLoginStart: () =>
    request<{ code: string; deep_link: string | null; expires_in: number }>(
      '/auth/telegram/start/',
      { method: 'POST' },
      { withAuth: false },
    ),

  tgLoginPoll: async (code: string) => {
    const res = await request<{ status: string; access?: string; refresh?: string }>(
      '/auth/telegram/poll/',
      { method: 'POST', body: JSON.stringify({ code }) },
      { withAuth: false },
    );
    if (res.status === 'ok' && res.access && res.refresh) {
      setTokens(res.access, res.refresh);
    }
    return res;
  },

  getMe: () => request<MeResponse>('/auth/me/'),

  getBays: () => request<Bay[]>('/bays/?active=1'),

  getServices: () => request<Service[]>('/services/?active=1'),

  getServicePoint: async (): Promise<ServicePoint | null> => {
    const points = await request<ServicePoint[]>('/service-points/');
    return points[0] ?? null;
  },

  getAppointments: (date: string) =>
    request<Appointment[]>(`/appointments/?date=${date}`),

  createAppointment: (payload: AppointmentCreatePayload) =>
    request<Appointment>('/appointments/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** reason обязателен при status === 'cancelled' — уходит клиенту в Telegram */
  updateAppointmentStatus: (id: string, status: AppointmentStatus, reason?: string) =>
    request<Appointment>(`/appointments/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(reason ? { status, reason } : { status }),
    }),

  /** Продлить in_progress-запись; 409 с body.needs_shift — нужен сдвиг очереди */
  extendAppointment: (id: string, minutes: number) =>
    request<Appointment>(`/appointments/${id}/extend/`, {
      method: 'POST',
      body: JSON.stringify({ extra_minutes: minutes }),
    }),

  shiftQueue: (id: string, minutes: number) =>
    request<{ shifted_count: number; notified: number; notify_failed: number }>(
      `/appointments/${id}/shift_queue/`,
      { method: 'POST', body: JSON.stringify({ minutes }) },
    ),

  // ---- профиль мастера ----

  getProfile: () => request<ManagerProfile>('/profile/'),

  patchProfile: (data: FormData | Record<string, unknown>) =>
    request<ManagerProfile>('/profile/', {
      method: 'PATCH',
      body: data instanceof FormData ? data : JSON.stringify(data),
    }),

  addMedia: (data: FormData) =>
    request<ManagerMediaItem>('/profile/media/', { method: 'POST', body: data }),

  deleteMedia: (id: string) =>
    request<void>(`/profile/media/${id}/`, { method: 'DELETE' }),

  patchServicePoint: (id: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/service-points/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // ---- клиентский режим ----

  getPublicPoints: () =>
    request<PublicPoint[]>('/public/service-points/', {}, { withAuth: false }),

  getMyBookings: () => request<Appointment[]>('/my/appointments/'),

  bookMy: (payload: {
    service: string;
    start_time: string;
    name?: string;
    phone?: string;
    car_details?: string;
  }) =>
    request<Appointment>('/my/appointments/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  cancelMy: (id: string) =>
    request<Appointment>(`/my/appointments/${id}/cancel/`, { method: 'POST' }),

  getSlots: (serviceId: string, date: string) =>
    request<{ start: string; end: string; bay_ids: string[] }[]>(
      `/slots/?service=${serviceId}&date=${date}`,
    ),
};

export interface ManagerMediaItem {
  id: string;
  media_type: 'photo' | 'video';
  image: string | null;
  video_url: string;
  caption: string;
  order: number;
}

export interface ManagerProfile {
  id: string;
  name: string;
  bio: string;
  bio_uz: string;
  experience_years: number | null;
  avatar: string | null;
  role: string;
  service_point: string;
  service_point_name: string;
  media: ManagerMediaItem[];
}
