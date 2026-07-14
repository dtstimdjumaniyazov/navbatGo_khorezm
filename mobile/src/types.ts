export type AppointmentStatus =
  | 'scheduled'
  | 'confirmed'
  | 'in_progress'
  | 'done'
  | 'no_show'
  | 'cancelled'
  | 'rescheduled';

export interface Appointment {
  id: string;
  client: string;
  client_name: string;
  client_phone: string;
  client_no_show_count: number;
  service: string;
  service_name: string;
  service_name_uz: string;
  service_type: 'fixed' | 'flexible';
  bay: string;
  bay_name: string;
  service_point_name: string;
  service_point_address: string;
  service_point_address_uz: string;
  start_time: string;
  duration_minutes: number | null;
  estimated_end_time: string;
  actual_start: string | null;
  actual_end: string | null;
  status: AppointmentStatus;
  source: 'telegram' | 'manual';
  car_details: string;
  note: string;
  created_at: string;
}

export interface Service {
  id: string;
  service_point: string;
  name: string;
  service_type: 'fixed' | 'flexible';
  duration_minutes: number;
  price: string | null;
  is_active: boolean;
}

export interface Slot {
  start: string;
  end: string;
  bay_ids: string[];
}

export type NotificationChannel = 'telegram' | 'push';

export interface ManagerInfo {
  name: string;
  role: string;
  language: 'ru' | 'uz';
  service_point: string;
  service_point_name: string;
  notification_channel: NotificationChannel;
}

export interface ClientInfo {
  id: string;
  name: string;
  phone: string;
  language: 'ru' | 'uz';
  notification_channel: NotificationChannel;
}

export interface Me {
  username: string;
  manager: ManagerInfo | null;
  client: ClientInfo | null;
}

// Публичная витрина (каталог клиента)
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

export interface ManagerProfile {
  id: string;
  name: string;
  bio: string;
  bio_uz: string;
  experience_years: number | null;
  avatar: string | null;
  language: 'ru' | 'uz';
  role: string;
  service_point: string;
  service_point_name: string;
  media: unknown[];
  notification_channel: NotificationChannel;
}

// weekday: 0=Пн … 6=Вс. work_start/work_end пустые при is_closed.
export interface WorkingHoursOverride {
  weekday: number;
  is_closed: boolean;
  work_start: string | null;
  work_end: string | null;
}

export interface ServicePoint {
  id: string;
  name: string;
  description: string;
  description_uz: string;
  address: string;
  address_uz: string;
  latitude: string | null;
  longitude: string | null;
  timezone: string;
  work_start: string;
  work_end: string;
  work_days: number[];
  slot_buffer_minutes: number;
  reminder_hours_before: number;
  min_lead_minutes: number;
  working_hours: WorkingHoursOverride[];
  instagram: string;
  is_active: boolean;
}
