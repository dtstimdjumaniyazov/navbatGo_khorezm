import React, { createContext, useCallback, useContext, useState } from 'react';
import { AppointmentStatus } from './types';

export type Lang = 'ru' | 'uz';

const translations = {
  ru: {
    panel_title: 'Панель мастера',
    today: 'Сегодня',
    in_progress_count: 'Машин в работе:',
    new_appointment: 'Новая запись',
    time: 'Время',
    add_slot: '+ Добавить',
    retry: 'Повторить',
    loading_error: 'Не удалось загрузить данные сервиса',
    no_connection: 'Нет подключения к серверу',
    // Drawer
    details: 'Детали записи',
    no_name: 'Без имени',
    service: 'Услуга',
    type: 'Тип',
    type_fixed: 'Фиксированная',
    type_flexible: 'Гибкая (оценочная)',
    bay: 'Пост',
    current_status: 'Текущий статус:',
    mark_confirmed: 'Отметить как «Подтвердил»',
    start_work: 'Начать работу',
    finish: 'Завершить',
    no_show: 'Не приехал',
    cancel_appt: 'Отменить запись',
    cancel_confirm: 'Отменить эту запись?',
    status_error: 'Не удалось изменить статус',
    // Modal
    start_time: 'Время начала',
    choose_service: 'Выберите услугу…',
    duration_min: 'Длительность (мин)',
    duration_placeholder: 'Из услуги',
    flexible_note: 'Гибкая услуга: длительность оценочная, можно скорректировать.',
    flexible_mark: '~гибкая',
    min_short: 'мин',
    client_name: 'Имя клиента',
    phone: 'Телефон',
    car: 'Автомобиль',
    cancel: 'Отмена',
    save: 'Записать',
    create_error: 'Не удалось создать запись',
    weekdays: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'],
    months: ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
  },
  uz: {
    panel_title: 'Уста панели',
    today: 'Бугун',
    in_progress_count: 'Ишдаги машиналар:',
    new_appointment: 'Янги ёзув',
    time: 'Вақт',
    add_slot: '+ Қўшиш',
    retry: 'Такрорлаш',
    loading_error: 'Сервис маълумотлари юкланмади',
    no_connection: 'Сервер билан алоқа йўқ',
    details: 'Ёзув тафсилотлари',
    no_name: 'Исмсиз',
    service: 'Хизмат',
    type: 'Тури',
    type_fixed: 'Белгиланган',
    type_flexible: 'Мослашувчан (тахминий)',
    bay: 'Пост',
    current_status: 'Жорий ҳолат:',
    mark_confirmed: '«Тасдиқлади» деб белгилаш',
    start_work: 'Ишни бошлаш',
    finish: 'Якунлаш',
    no_show: 'Келмади',
    cancel_appt: 'Ёзувни бекор қилиш',
    cancel_confirm: 'Бу ёзув бекор қилинсинми?',
    status_error: 'Ҳолатни ўзгартириб бўлмади',
    start_time: 'Бошланиш вақти',
    choose_service: 'Хизматни танланг…',
    duration_min: 'Давомийлик (дақ.)',
    duration_placeholder: 'Хизматдан',
    flexible_note: 'Мослашувчан хизмат: давомийлик тахминий, ўзгартириш мумкин.',
    flexible_mark: '~мослашувчан',
    min_short: 'дақ.',
    client_name: 'Мижоз исми',
    phone: 'Телефон',
    car: 'Автомобиль',
    cancel: 'Бекор қилиш',
    save: 'Ёзиш',
    create_error: 'Ёзув яратилмади',
    weekdays: ['Якш', 'Душ', 'Сеш', 'Чор', 'Пай', 'Жум', 'Шан'],
    months: ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
  },
} as const;

export const statusLabels: Record<Lang, Record<AppointmentStatus, string>> = {
  ru: {
    scheduled: 'Записан',
    confirmed: 'Подтвердил',
    in_progress: 'В работе',
    done: 'Готово',
    no_show: 'Не приехал',
    cancelled: 'Отменён',
    rescheduled: 'Перенесён',
  },
  uz: {
    scheduled: 'Ёзилган',
    confirmed: 'Тасдиқлади',
    in_progress: 'Ишда',
    done: 'Тайёр',
    no_show: 'Келмади',
    cancelled: 'Бекор қилинган',
    rescheduled: 'Кўчирилган',
  },
};

type StringKey = {
  [K in keyof typeof translations.ru]: (typeof translations.ru)[K] extends string ? K : never;
}[keyof typeof translations.ru];

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: StringKey) => string;
  /** «Сегодня, 8 июл» / «Бугун, 8 июл» / «ср, 9 июл» */
  formatDate: (d: Date, isToday: boolean) => string;
  statuses: Record<AppointmentStatus, string>;
}

const I18nContext = createContext<I18n | null>(null);

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() =>
    localStorage.getItem('navbatgo_lang') === 'uz' ? 'uz' : 'ru',
  );

  const setLang = useCallback((l: Lang) => {
    localStorage.setItem('navbatgo_lang', l);
    setLangState(l);
  }, []);

  const t = useCallback((key: StringKey) => translations[lang][key] as string, [lang]);

  const formatDate = useCallback(
    (d: Date, isToday: boolean) => {
      const dict = translations[lang];
      const dayMonth = `${d.getDate()} ${dict.months[d.getMonth()]}`;
      return isToday
        ? `${dict.today}, ${dayMonth}`
        : `${dict.weekdays[d.getDay()]}, ${dayMonth}`;
    },
    [lang],
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, t, formatDate, statuses: statusLabels[lang] }}>
      {children}
    </I18nContext.Provider>
  );
};

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside I18nProvider');
  return ctx;
}
