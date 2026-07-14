import { Appointment } from './types';

export const MINUTE_HEIGHT = 2; // 2px на минуту

// Границы оси времени приходят из ServicePoint (work_start/work_end);
// эти значения — запасные, пока настройки не загрузились
export const FALLBACK_START_MIN = 8 * 60;
export const FALLBACK_END_MIN = 20 * 60;

/** "09:00:00" (TimeField из DRF) -> минуты от полуночи */
export function timeStrToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}

/** ISO datetime -> минуты от полуночи в локальном времени браузера */
export function isoToMinutes(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

/** ISO datetime -> "09:30" */
export function formatTime(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** Date -> "YYYY-MM-DD" в локальной таймзоне (не UTC!) */
export function toDateParam(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Метки сетки каждые 30 мин между началом и концом рабочего дня */
export function generateTimeSlots(startMin: number, endMin: number): string[] {
  const slots: string[] = [];
  for (let t = startMin; t <= endMin; t += 30) {
    const h = Math.floor(t / 60);
    const m = t % 60;
    slots.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
  }
  return slots;
}

export interface LaidOutAppointment {
  appointment: Appointment;
  col: number;
  cols: number;
}

/**
 * Раскладка записей одного поста по колонкам, как в календарях: если
 * несколько записей пересекаются по времени (например, отменённая запись
 * осталась на том же слоте, где потом создали новую), они делят ширину
 * колонки пополам вместо того, чтобы полностью перекрывать друг друга —
 * иначе более поздняя в списке визуально скрывала бы актуальную запись.
 */
export function layoutOverlapping(appts: Appointment[]): LaidOutAppointment[] {
  const sorted = [...appts].sort((a, b) => a.start_time.localeCompare(b.start_time));
  const result: LaidOutAppointment[] = [];

  let cluster: { appt: Appointment; col: number }[] = [];
  let colEnds: string[] = []; // colEnds[i] — конец последней записи в колонке i (в рамках кластера)
  let clusterMaxEnd = '';

  const flush = () => {
    if (cluster.length === 0) return;
    const cols = colEnds.length;
    for (const item of cluster) {
      result.push({ appointment: item.appt, col: item.col, cols });
    }
    cluster = [];
    colEnds = [];
    clusterMaxEnd = '';
  };

  for (const appt of sorted) {
    if (cluster.length > 0 && appt.start_time >= clusterMaxEnd) {
      flush();
    }
    let col = colEnds.findIndex((end) => end <= appt.start_time);
    if (col === -1) {
      col = colEnds.length;
      colEnds.push(appt.estimated_end_time);
    } else {
      colEnds[col] = appt.estimated_end_time;
    }
    cluster.push({ appt, col });
    if (appt.estimated_end_time > clusterMaxEnd) clusterMaxEnd = appt.estimated_end_time;
  }
  flush();

  return result;
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}
