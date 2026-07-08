import {
  Appointment,
  AppointmentCreatePayload,
  AppointmentStatus,
  Bay,
  Service,
  ServicePoint,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api';

// Задел под авторизацию мастера (этап 2+): выставить токен один раз,
// все запросы начнут слать Authorization.
let authToken: string | null = null;
export function setAuthToken(token: string | null) {
  authToken = token;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (authToken) headers['Authorization'] = `Token ${authToken}`;

  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, 'Нет подключения к серверу');
  }
  if (!resp.ok) {
    let detail = `Ошибка ${resp.status}`;
    try {
      const body = await resp.json();
      if (body.detail) detail = body.detail;
    } catch {
      /* тело не JSON — оставляем код */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export const api = {
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

  updateAppointmentStatus: (id: string, status: AppointmentStatus) =>
    request<Appointment>(`/appointments/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
};
