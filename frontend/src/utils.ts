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

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}
