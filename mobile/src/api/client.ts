/**
 * HTTP-клиент API: JWT в AsyncStorage, авто-refresh access-токена по 401,
 * заголовок против интерстишла бесплатного ngrok. Та же логика, что в
 * веб-панели (frontend/src/api/client.ts), но на React Native.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

import {
  Appointment,
  ClientInfo,
  ManagerInfo,
  ManagerProfile,
  Me,
  NotificationChannel,
  PublicPoint,
  Service,
  ServicePoint,
  Slot,
} from '../types';

const BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? 'https://crack-troll-maximum.ngrok-free.app/api';

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
const PARTNER_USERNAME = process.env.EXPO_PUBLIC_PARTNER_CONTACT_USERNAME ?? '';
export function partnerContactUrl(lang: 'ru' | 'uz'): string | null {
  if (!PARTNER_USERNAME) return null;
  const text =
    lang === 'uz'
      ? 'Ассалому алайкум! Автосервисимни NavbatGo’га улашни хоҳлайман.'
      : 'Здравствуйте! Хочу подключить свой автосервис к NavbatGo.';
  return `https://t.me/${PARTNER_USERNAME}?text=${encodeURIComponent(text)}`;
}

const ACCESS_KEY = 'navbatgo_access';
const REFRESH_KEY = 'navbatgo_refresh';

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

let onUnauthorized: () => void = () => {};
export function setOnUnauthorized(cb: () => void) {
  onUnauthorized = cb;
}

export async function saveTokens(access: string, refresh: string): Promise<void> {
  await AsyncStorage.multiSet([
    [ACCESS_KEY, access],
    [REFRESH_KEY, refresh],
  ]);
}

export async function clearTokens(): Promise<void> {
  await AsyncStorage.multiRemove([ACCESS_KEY, REFRESH_KEY]);
}

export async function hasTokens(): Promise<boolean> {
  return (await AsyncStorage.getItem(ACCESS_KEY)) !== null;
}

async function refreshAccess(): Promise<boolean> {
  const refresh = await AsyncStorage.getItem(REFRESH_KEY);
  if (!refresh) return false;
  try {
    const resp = await fetch(`${BASE_URL}/auth/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': '1',
      },
      body: JSON.stringify({ refresh }),
    });
    if (!resp.ok) return false;
    const data = await resp.json();
    await AsyncStorage.setItem(ACCESS_KEY, data.access);
    return true;
  } catch {
    return false;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean; // false — анонимный запрос (вход)
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
  allowRefresh = true,
): Promise<T> {
  const headers: Record<string, string> = { 'ngrok-skip-browser-warning': '1' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.auth !== false) {
    const token = await AsyncStorage.getItem(ACCESS_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'Нет соединения с сервером');
  }

  if (resp.status === 401 && options.auth !== false && allowRefresh) {
    if (await refreshAccess()) return request<T>(path, options, false);
    await clearTokens();
    onUnauthorized();
    throw new ApiError(401, 'Сессия истекла — войдите заново');
  }

  if (resp.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await resp.json();
  } catch {
    // не-JSON ответ (например, HTML от прокси) — оставим data = null
  }
  if (!resp.ok) {
    throw new ApiError(resp.status, data?.detail ?? `Ошибка сервера (${resp.status})`, data);
  }
  return data as T;
}

export const api = {
  // Вход через Telegram (device-code flow)
  tgLoginStart: () =>
    request<{ code: string; deep_link: string | null; expires_in: number }>(
      '/auth/telegram/start/',
      { method: 'POST', auth: false },
    ),
  tgLoginPoll: (code: string) =>
    request<{
      status: string;
      role?: 'master' | 'client';
      access?: string;
      refresh?: string;
      manager?: ManagerInfo;
      client?: ClientInfo;
    }>('/auth/telegram/poll/', { method: 'POST', body: { code }, auth: false }),
  getMe: () => request<Me>('/auth/me/'),

  // Клиентский режим
  getPublicPoints: () => request<PublicPoint[]>('/public/service-points/', { auth: false }),
  getMyBookings: () => request<Appointment[]>('/my/appointments/'),
  bookMy: (payload: {
    service: string;
    start_time: string;
    name?: string;
    phone?: string;
    car_details?: string;
  }) => request<Appointment>('/my/appointments/', { method: 'POST', body: payload }),
  cancelMy: (id: string) =>
    request<Appointment>(`/my/appointments/${id}/cancel/`, { method: 'POST', body: {} }),

  // Записи
  getAppointments: (date: string) => request<Appointment[]>(`/appointments/?date=${date}`),
  appointmentAction: (
    id: string,
    action: 'start' | 'finish' | 'no_show' | 'cancel',
    reason?: string,
  ) =>
    request<Appointment>(`/appointments/${id}/${action}/`, {
      method: 'POST',
      body: reason ? { reason } : {},
    }),
  extend: (id: string, minutes: number) =>
    request<Appointment>(`/appointments/${id}/extend/`, {
      method: 'POST',
      body: { extra_minutes: minutes },
    }),
  shiftQueue: (id: string, minutes: number) =>
    request<{ shifted_count: number; notified: number; notify_failed: number }>(
      `/appointments/${id}/shift_queue/`,
      { method: 'POST', body: { minutes } },
    ),
  createAppointment: (payload: {
    client_name: string;
    client_phone: string;
    service: string;
    start_time: string;
    car_details?: string;
    note?: string;
  }) =>
    request<Appointment>('/appointments/', {
      method: 'POST',
      body: { ...payload, source: 'manual' },
    }),

  // Услуги и слоты
  getServices: () => request<Service[]>('/services/?active=1'),
  getSlots: (serviceId: string, date: string) =>
    request<Slot[]>(`/slots/?service=${serviceId}&date=${date}`),

  // Профиль мастера и настройки сервиса
  getProfile: () => request<ManagerProfile>('/profile/'),
  patchProfile: (
    data: Partial<
      Pick<
        ManagerProfile,
        'name' | 'bio' | 'bio_uz' | 'experience_years' | 'language' | 'notification_channel'
      >
    >,
  ) => request<ManagerProfile>('/profile/', { method: 'PATCH', body: data }),

  // Настройки клиента (канал уведомлений) + push-токен (общий для клиента и мастера)
  getMySettings: () => request<{ notification_channel: NotificationChannel }>('/my/settings/'),
  patchMySettings: (channel: NotificationChannel) =>
    request<{ notification_channel: NotificationChannel }>('/my/settings/', {
      method: 'PATCH',
      body: { notification_channel: channel },
    }),
  registerPushToken: (token: string) =>
    request<{ status: string }>('/notifications/push-token/', {
      method: 'POST',
      body: { token },
    }),
  getServicePoint: (id: string) => request<ServicePoint>(`/service-points/${id}/`),
  patchServicePoint: (
    id: string,
    data: Partial<
      Pick<
        ServicePoint,
        | 'description'
        | 'description_uz'
        | 'instagram'
        | 'reminder_hours_before'
        | 'min_lead_minutes'
      >
    >,
  ) => request<ServicePoint>(`/service-points/${id}/`, { method: 'PATCH', body: data }),
};
