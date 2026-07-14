const pad = (n: number) => String(n).padStart(2, '0');

/** ISO-строка → «14:30» в часовом поясе телефона (совпадает с ТЗ сервиса). */
export function fmtTime(iso: string): string {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Date → «YYYY-MM-DD» для query-параметров API (локальная дата). */
export function dateKey(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Извлекает id ролика из ссылки на YouTube (youtu.be/, ?v=, /shorts/, /embed/). */
export function youtubeId(url: string): string | null {
  const m = url.match(/(?:youtu\.be\/|v=|shorts\/|embed\/)([\w-]{6,})/);
  return m ? m[1] : null;
}

/** Ссылки навигации на точку: по координатам, иначе — по адресу. */
export function mapLinks(
  lat: string | null,
  lon: string | null,
  address: string,
): { google: string; yandex: string } {
  if (lat != null && lon != null) {
    return {
      google: `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`,
      yandex: `https://yandex.ru/maps/?pt=${lon},${lat}&z=16&l=map`,
    };
  }
  const q = encodeURIComponent(address);
  return {
    google: `https://www.google.com/maps/search/?api=1&query=${q}`,
    yandex: `https://yandex.ru/maps/?text=${q}`,
  };
}

const WEEKDAYS = {
  ru: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
  uz: ['Якш', 'Душ', 'Сеш', 'Чор', 'Пай', 'Жум', 'Шан'],
};
const TODAY = { ru: 'Сегодня', uz: 'Бугун' };
const TOMORROW = { ru: 'Завтра', uz: 'Эртага' };

/** Подпись для чипа даты: «Сегодня», «Завтра», «Ср 15.07» (на языке клиента). */
export function dateLabel(d: Date, todayKey: string, lang: 'ru' | 'uz' = 'ru'): string {
  const key = dateKey(d);
  if (key === todayKey) return TODAY[lang];
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  if (key === dateKey(tomorrow)) return TOMORROW[lang];
  return `${WEEKDAYS[lang][d.getDay()]} ${pad(d.getDate())}.${pad(d.getMonth() + 1)}`;
}
