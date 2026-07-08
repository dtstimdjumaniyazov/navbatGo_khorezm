// Типы выровнены с контрактом DRF API (см. api/serializers.py на бэкенде)

export type AppointmentStatus =
  | 'scheduled'
  | 'confirmed'
  | 'in_progress'
  | 'done'
  | 'no_show'
  | 'cancelled'
  | 'rescheduled';

// ВАЖНО: в бэкенде тип называется 'flexible' (не 'floating' как в прототипе)
export type ServiceType = 'fixed' | 'flexible';
export type Source = 'telegram' | 'manual';

export interface Bay {
  id: string;
  name: string;
  is_active: boolean;
}

export interface Service {
  id: string;
  name: string;
  service_type: ServiceType;
  duration_minutes: number;
  price: string | null;
  is_active: boolean;
}

export interface ServicePoint {
  id: string;
  name: string;
  address: string;
  timezone: string;
  work_start: string; // "09:00:00"
  work_end: string;   // "19:00:00"
  work_days: number[];
  slot_buffer_minutes: number;
}

export interface Appointment {
  id: string;
  client: string;
  client_name: string;
  client_phone: string;
  service: string;
  service_name: string;
  service_type: ServiceType;
  bay: string;
  bay_name: string;
  start_time: string;          // ISO datetime
  estimated_end_time: string;  // ISO datetime, включает буфер
  actual_start: string | null;
  actual_end: string | null;
  status: AppointmentStatus;
  source: Source;
  car_details: string;
  note: string;
  created_at: string;
}

export interface AppointmentCreatePayload {
  client_name: string;
  client_phone?: string;
  service: string;
  bay?: string;
  start_time: string;
  duration_minutes?: number;
  car_details?: string;
  note?: string;
  source: 'manual';
}
