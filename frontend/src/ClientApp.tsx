import React, { useCallback, useEffect, useState } from 'react';
import {
  Bell,
  Calendar,
  CalendarDays,
  CalendarX,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Images,
  Info,
  Instagram,
  Loader2,
  LogOut,
  MapPin,
  Phone,
  Play,
  Store,
  Wrench,
  X,
} from 'lucide-react';
import {
  api,
  ApiError,
  ClientInfo,
  PublicPoint,
  PublicService,
} from './api/client';
import { EmptyState } from './components/EmptyState';
import { OnboardingModal } from './components/OnboardingModal';
import { Appointment } from './types';
import { useI18n } from './i18n';

const ONBOARD_KEY = 'navbatgo_client_onboarded';

interface Props {
  me: ClientInfo;
  onLogout: () => void;
}

type Tab = 'catalog' | 'my';

const pad = (n: number) => String(n).padStart(2, '0');

/** Локализованное поле данных: uz-вариант, если выбран uz и он заполнен. */
const locText = (lang: 'ru' | 'uz', ru: string, uz: string) =>
  lang === 'uz' && uz ? uz : ru;

// Короткие имена дней, индекс = weekday бэкенда (0=Пн … 6=Вс)
const WEEKDAYS_SHORT: Record<'ru' | 'uz', string[]> = {
  ru: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
  uz: ['Душ', 'Сеш', 'Чор', 'Пай', 'Жум', 'Шан', 'Якш'],
};

/** Иконка Google Maps: разноцветные «дороги» + булавка (узнаваемая пара с Яндексом). */
const GoogleMapsIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 40 40" className={className} xmlns="http://www.w3.org/2000/svg">
    <rect x="1" y="1" width="38" height="38" rx="9" fill="#fff" stroke="#e5e7eb" />
    <path d="M3 26 L15 14 L21 20 L37 4" stroke="#34A853" strokeWidth="5" fill="none" strokeLinecap="round" />
    <path d="M3 35 L19 19" stroke="#FBBC05" strokeWidth="5" fill="none" strokeLinecap="round" />
    <path d="M26 30 L37 19" stroke="#4285F4" strokeWidth="5" fill="none" strokeLinecap="round" />
    <path
      d="M20 10c-3.3 0-6 2.7-6 6 0 4.5 6 11 6 11s6-6.5 6-11c0-3.3-2.7-6-6-6z"
      fill="#EA4335"
    />
    <circle cx="20" cy="16" r="2.4" fill="#fff" />
  </svg>
);

/** Иконка Яндекс Карт: фирменный красный маркер на белом фоне. */
const YandexMapsIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 40 40" className={className} xmlns="http://www.w3.org/2000/svg">
    <rect x="1" y="1" width="38" height="38" rx="9" fill="#fff" stroke="#e5e7eb" />
    <path
      d="M20 8c-4.4 0-8 3.6-8 8 0 6 8 16 8 16s8-10 8-16c0-4.4-3.6-8-8-8z"
      fill="#FC3F1D"
    />
    <circle cx="20" cy="16" r="3.2" fill="#fff" />
  </svg>
);

/** Сворачиваемая карточка витрины: заголовок с иконкой + шеврон, контент по клику. */
const Section: React.FC<{
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}> = ({ title, icon, defaultOpen, children }) => {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3.5 text-left"
      >
        <span className="font-bold flex items-center gap-2">
          {icon}
          {title}
        </span>
        <ChevronDown
          className={`w-5 h-5 text-gray-400 transition-transform shrink-0 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && <div className="px-4 pb-4 space-y-3">{children}</div>}
    </div>
  );
};

/** Ссылки навигации на точку: по координатам, иначе — по адресу. */
function mapLinks(p: PublicPoint): { google: string; yandex: string } {
  if (p.latitude != null && p.longitude != null) {
    return {
      google: `https://www.google.com/maps/search/?api=1&query=${p.latitude},${p.longitude}`,
      yandex: `https://yandex.ru/maps/?pt=${p.longitude},${p.latitude}&z=16&l=map`,
    };
  }
  const q = encodeURIComponent(p.address);
  return {
    google: `https://www.google.com/maps/search/?api=1&query=${q}`,
    yandex: `https://yandex.ru/maps/?text=${q}`,
  };
}
/** Извлекает id ролика из ссылки на YouTube (youtu.be/, ?v=, /shorts/, /embed/). */
function youtubeId(url: string): string | null {
  const m = url.match(/(?:youtu\.be\/|v=|shorts\/|embed\/)([\w-]{6,})/);
  return m ? m[1] : null;
}

const dateKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const fmtTime = (iso: string) => {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/** Клиентский режим сайта: каталог сервисов → витрина → запись; мои записи. */
export const ClientApp: React.FC<Props> = ({ me, onLogout }) => {
  const { lang, setLang, t } = useI18n();
  const [tab, setTab] = useState<Tab>('catalog');
  const [point, setPoint] = useState<PublicPoint | null>(null);
  const [myKey, setMyKey] = useState(0);
  const [showOnboarding, setShowOnboarding] = useState(
    () => !localStorage.getItem(ONBOARD_KEY),
  );
  const dismissOnboarding = () => {
    localStorage.setItem(ONBOARD_KEY, '1');
    setShowOnboarding(false);
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col font-sans text-gray-900">
      <header className="bg-white border-b px-4 py-2.5 flex items-center justify-between shadow-sm sticky top-0 z-20">
        <button
          onClick={() => {
            setPoint(null);
            setTab('catalog');
          }}
          className="flex items-center gap-2 text-blue-700 font-bold text-lg"
        >
          <Wrench className="w-5 h-5" />
          NavbatGo
        </button>
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-gray-100 rounded-md p-0.5 text-sm font-medium">
            {(['ru', 'uz'] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-2 py-1 rounded ${
                  lang === l ? 'bg-white shadow-sm text-blue-700' : 'text-gray-500'
                }`}
              >
                {l === 'ru' ? 'РУ' : 'ЎЗ'}
              </button>
            ))}
          </div>
          <button
            onClick={onLogout}
            title={t('logout')}
            className="p-2 text-gray-400 hover:text-gray-700 rounded-md"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-2xl w-full mx-auto p-4 pb-24">
        {tab === 'catalog' &&
          (point ? (
            <PointView
              point={point}
              me={me}
              onBack={() => setPoint(null)}
              onBooked={() => {
                setPoint(null);
                setMyKey((k) => k + 1);
                setTab('my');
              }}
            />
          ) : (
            <Catalog onSelect={setPoint} />
          ))}
        {tab === 'my' && <MyBookings key={myKey} />}
      </main>

      <nav className="bg-white border-t flex fixed bottom-0 inset-x-0 z-20 pb-[env(safe-area-inset-bottom)]">
        {(
          [
            { id: 'catalog', label: t('cl_tab_catalog'), icon: <Wrench className="w-5 h-5" /> },
            { id: 'my', label: t('cl_tab_my'), icon: <CalendarDays className="w-5 h-5" /> },
          ] as { id: Tab; label: string; icon: React.ReactNode }[]
        ).map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 py-2 flex flex-col items-center gap-0.5 text-xs font-medium ${
              tab === id ? 'text-blue-600' : 'text-gray-400'
            }`}
          >
            {icon}
            {label}
          </button>
        ))}
      </nav>

      <OnboardingModal
        isOpen={showOnboarding}
        onClose={dismissOnboarding}
        heading={t('cl_onboard_title')}
        ctaLabel={t('cl_onboard_cta')}
        steps={[
          { icon: <Wrench className="w-5 h-5" />, title: t('cl_onboard_step1_title'), text: t('cl_onboard_step1_text') },
          { icon: <Calendar className="w-5 h-5" />, title: t('cl_onboard_step2_title'), text: t('cl_onboard_step2_text') },
          { icon: <Bell className="w-5 h-5" />, title: t('cl_onboard_step3_title'), text: t('cl_onboard_step3_text') },
        ]}
      />
    </div>
  );
};

const Catalog: React.FC<{ onSelect: (p: PublicPoint) => void }> = ({ onSelect }) => {
  const { t, lang } = useI18n();
  const [points, setPoints] = useState<PublicPoint[] | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    api
      .getPublicPoints()
      .then(setPoints)
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : t('no_connection')),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(load, [load]);

  if (points === null) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-gray-400">
        {error ? (
          <>
            <p className="text-red-600">{error}</p>
            <button onClick={load} className="px-4 py-2 bg-white border rounded-md">
              {t('retry')}
            </button>
          </>
        ) : (
          <Loader2 className="w-6 h-6 animate-spin" />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {points.length === 0 && (
        <EmptyState icon={<Store className="w-5 h-5" />} message={t('cl_no_points')} />
      )}
      {points.map((p) => {
        const photo = p.media.find((m) => m.media_type === 'photo' && m.image);
        return (
          <button
            key={p.id}
            onClick={() => onSelect(p)}
            className="w-full text-left bg-white rounded-2xl border shadow-sm overflow-hidden hover:shadow-md transition-all active:scale-[0.99]"
          >
            {photo?.image && (
              <img src={photo.image} alt="" className="w-full h-40 object-cover" />
            )}
            <div className="p-4 space-y-1">
              <div className="font-bold text-lg">{p.name}</div>
              {p.address && (
                <div className="text-sm text-gray-500 flex items-center gap-1">
                  <MapPin className="w-4 h-4 shrink-0" /> {locText(lang, p.address, p.address_uz)}
                </div>
              )}
              {p.description && (
                <p className="text-sm text-gray-600 line-clamp-2">
                  {locText(lang, p.description, p.description_uz)}
                </p>
              )}
              <div className="text-sm text-blue-600 font-medium">
                {t('cl_services_count').replace('{n}', String(p.services.length))} ·{' '}
                {p.work_start.slice(0, 5)}–{p.work_end.slice(0, 5)}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
};

const PointView: React.FC<{
  point: PublicPoint;
  me: ClientInfo;
  onBack: () => void;
  onBooked: () => void;
}> = ({ point, me, onBack, onBooked }) => {
  const { lang, t } = useI18n();
  // Нерабочие дни сервиса не предлагаем (schedule[weekday].start === null — выходной)
  const allDays = Array.from({ length: 14 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    return d;
  });
  const workDays = allDays
    .filter((d) => {
      const entry = point.schedule?.[(d.getDay() + 6) % 7];
      return entry ? entry.start !== null : true;
    })
    .slice(0, 7);
  const days = workDays.length > 0 ? workDays : allDays.slice(0, 7);
  const todayK = dateKey(new Date());

  const [service, setService] = useState<PublicService | null>(null);
  const [day, setDay] = useState(days[0]);
  const [slots, setSlots] = useState<{ start: string }[] | null>(null);
  const [slot, setSlot] = useState<string | null>(null);
  const [name, setName] = useState(me.name);
  const [phone, setPhone] = useState(me.phone);
  const [car, setCar] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [booked, setBooked] = useState(false);
  const [openVideoId, setOpenVideoId] = useState<string | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!service) return;
    setSlots(null);
    setSlot(null);
    api
      .getSlots(service.id, dateKey(day))
      .then(setSlots)
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : t('no_connection')),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [service, day]);

  const dayLabel = (d: Date) => {
    const key = dateKey(d);
    if (key === todayK) return t('today');
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (key === dateKey(tomorrow)) return t('cl_tomorrow');
    return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}`;
  };

  const svcName = (s: PublicService) => (lang === 'uz' && s.name_uz ? s.name_uz : s.name);

  const book = async () => {
    if (!service || !slot || saving) return;
    setSaving(true);
    setError('');
    try {
      await api.bookMy({
        service: service.id,
        start_time: slot,
        name: name.trim(),
        phone: phone.trim(),
        car_details: car.trim(),
      });
      setBooked(true);
      setTimeout(onBooked, 1200);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 409) {
        setError(e.message);
        setSlot(null);
        api.getSlots(service.id, dateKey(day)).then(setSlots).catch(() => {});
      } else {
        setError(e instanceof ApiError ? e.message : t('no_connection'));
      }
    } finally {
      setSaving(false);
    }
  };

  const photos = point.media.filter((m) => m.media_type === 'photo' && m.image);
  const videos = point.media.filter((m) => m.media_type === 'video' && m.video_url);

  const hasInfo = !!point.description || !!point.instagram || point.managers.length > 0;
  const hasSchedule = !!point.schedule && point.schedule.length === 7;
  const hasAddress = !!point.address || point.latitude != null;

  return (
    <div className="space-y-3">
      <button onClick={onBack} className="text-blue-600 font-medium cursor-pointer">
        {t('cl_back')}
      </button>

      <h1 className="text-2xl font-bold px-1">{point.name}</h1>

      {hasInfo && (
        <Section title={t('cl_info_title')} icon={<Info className="w-5 h-5 text-blue-600" />} defaultOpen>
          {point.description && (
            <p className="text-sm text-gray-600 whitespace-pre-line">
              {locText(lang, point.description, point.description_uz)}
            </p>
          )}
          {point.instagram && (
            <a
              href={point.instagram}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-pink-600 flex items-center gap-1 font-medium"
            >
              <Instagram className="w-4 h-4" /> Instagram
            </a>
          )}
          {point.managers.length > 0 && (
            <div className="space-y-3 pt-1">
              <h3 className="text-sm font-semibold text-gray-500">{t('cl_masters')}</h3>
              {point.managers.map((m) => (
                <div key={m.id} className="flex gap-3 items-start">
                  {m.avatar ? (
                    <img src={m.avatar} alt="" className="w-12 h-12 rounded-full object-cover" />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center text-gray-400">
                      👤
                    </div>
                  )}
                  <div className="min-w-0">
                    <div className="font-semibold">{m.name}</div>
                    {m.experience_years != null && (
                      <div className="text-xs text-gray-500">
                        {t('cl_exp').replace('{n}', String(m.experience_years))}
                      </div>
                    )}
                    {m.bio && (
                      <p className="text-sm text-gray-600">{locText(lang, m.bio, m.bio_uz)}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Section>
      )}

      {(photos.length > 0 || videos.length > 0) && (
        <Section title={t('cl_gallery_title')} icon={<Images className="w-5 h-5 text-blue-600" />}>
          {photos.length > 0 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {photos.map((m, i) => (
                <button key={m.id} onClick={() => setLightboxIndex(i)} className="shrink-0">
                  <img
                    src={m.image!}
                    alt={m.caption}
                    className="h-28 w-40 object-cover rounded-lg hover:opacity-90 transition-opacity"
                  />
                </button>
              ))}
            </div>
          )}
          {videos.map((v) => {
            const id = youtubeId(v.video_url);
            const isOpen = openVideoId === v.id;
            return (
              <div key={v.id} className="rounded-xl overflow-hidden bg-black shadow-sm">
                {isOpen && id ? (
                  <div className="relative aspect-video">
                    {/* fs=0 + без allowFullScreen: плеер не может уйти в системный
                        fullscreen и «спрятать» кнопку закрытия под собой */}
                    <iframe
                      className="w-full h-full"
                      src={`https://www.youtube.com/embed/${id}?autoplay=1&playsinline=1&fs=0`}
                      title={v.caption || t('cl_video')}
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; picture-in-picture"
                    />
                    <button
                      onClick={() => setOpenVideoId(null)}
                      aria-label={t('cl_video_collapse')}
                      className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/70 hover:bg-black text-white flex items-center justify-center"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setOpenVideoId(v.id)}
                    className="relative w-full aspect-video flex items-center justify-center group"
                  >
                    {id ? (
                      <img
                        src={`https://img.youtube.com/vi/${id}/hqdefault.jpg`}
                        alt={v.caption || t('cl_video')}
                        className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity"
                      />
                    ) : (
                      <div className="w-full h-full bg-gray-800" />
                    )}
                    <span className="absolute inset-0 flex items-center justify-center">
                      <span className="w-14 h-14 rounded-full bg-red-600 flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform">
                        <Play className="w-6 h-6 text-white fill-white ml-0.5" />
                      </span>
                    </span>
                    {v.caption && (
                      <span className="absolute bottom-0 inset-x-0 bg-black/60 text-white text-xs text-left px-2 py-1 truncate">
                        {v.caption}
                      </span>
                    )}
                  </button>
                )}
              </div>
            );
          })}
        </Section>
      )}

      {hasSchedule && (
        <Section title={t('cl_hours')} icon={<Clock className="w-5 h-5 text-blue-600" />}>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 max-w-xs">
            {point.schedule.map((e) => (
              <div key={e.weekday} className="flex justify-between gap-2">
                <span className="text-gray-400">{WEEKDAYS_SHORT[lang][e.weekday]}</span>
                <span className={e.start ? 'text-gray-700' : 'text-gray-400'}>
                  {e.start ? `${e.start}–${e.end}` : t('cl_closed')}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {hasAddress && (
        <Section title={t('cl_address_title')} icon={<MapPin className="w-5 h-5 text-blue-600" />}>
          {point.address && (
            <div className="text-sm text-gray-600">
              {locText(lang, point.address, point.address_uz)}
            </div>
          )}
          <div className="flex gap-2">
            <a
              href={mapLinks(point).google}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 pl-1.5 pr-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-sm font-medium transition-all active:scale-[0.97]"
            >
              <GoogleMapsIcon className="w-6 h-6 shrink-0" /> Google Maps
            </a>
            <a
              href={mapLinks(point).yandex}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 pl-1.5 pr-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-sm font-medium transition-all active:scale-[0.97]"
            >
              <YandexMapsIcon className="w-6 h-6 shrink-0" /> Яндекс Карты
            </a>
          </div>
        </Section>
      )}

      <Section title={t('cl_book')} icon={<Calendar className="w-5 h-5 text-blue-600" />} defaultOpen>
        <div className="flex flex-wrap gap-2">
          {point.services.map((s) => (
            <button
              key={s.id}
              onClick={() => setService(s)}
              className={`px-3 py-2 rounded-xl border text-left text-sm transition-all active:scale-[0.97] ${
                service?.id === s.id
                  ? 'bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-600/20'
                  : 'bg-white hover:bg-gray-50'
              }`}
            >
              <div className="font-semibold">{svcName(s)}</div>
              <div className={service?.id === s.id ? 'text-blue-100' : 'text-gray-500'}>
                {s.duration_minutes} {t('min_short')}
                {s.service_type === 'flexible' ? ` · ${t('cl_approx')}` : ''}
                {s.price ? ` · ${Number(s.price).toLocaleString('ru')}` : ''}
              </div>
            </button>
          ))}
        </div>

        {service && (
          <>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {days.map((d) => (
                <button
                  key={dateKey(d)}
                  onClick={() => setDay(d)}
                  className={`px-3 py-1.5 rounded-full border text-sm whitespace-nowrap transition-all active:scale-[0.97] ${
                    dateKey(d) === dateKey(day)
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white'
                  }`}
                >
                  {dayLabel(d)}
                </button>
              ))}
            </div>
            {slots === null && <Loader2 className="w-5 h-5 animate-spin text-blue-600" />}
            {slots !== null && slots.length === 0 && (
              <EmptyState icon={<Clock className="w-5 h-5" />} message={t('cl_no_slots')} />
            )}
            <div className="flex flex-wrap gap-2">
              {(slots ?? []).map((s) => (
                <button
                  key={s.start}
                  onClick={() => setSlot(s.start)}
                  className={`px-3 py-2 rounded-xl border text-sm font-semibold transition-all active:scale-[0.97] ${
                    slot === s.start ? 'bg-blue-600 text-white border-blue-600' : 'bg-white'
                  }`}
                >
                  {fmtTime(s.start)}
                </button>
              ))}
            </div>
          </>
        )}

        {service && slot && (
          <div className="space-y-2 pt-1">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('cl_your_name')}
              maxLength={200}
              className="w-full border border-gray-300 rounded-md p-2"
            />
            <div className="relative">
              <Phone className="w-4 h-4 absolute left-2.5 top-3 text-gray-400" />
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder={t('phone')}
                maxLength={32}
                className="w-full border border-gray-300 rounded-md p-2 pl-8"
              />
            </div>
            <input
              value={car}
              onChange={(e) => setCar(e.target.value)}
              placeholder={t('car')}
              maxLength={120}
              className="w-full border border-gray-300 rounded-md p-2"
            />
            <button
              onClick={book}
              disabled={saving || booked}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-base py-4 rounded-2xl shadow-lg shadow-blue-600/20 hover:shadow-blue-600/30 transition-all active:scale-[0.98] mt-1 flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {saving ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Calendar className="w-5 h-5" />
              )}
              {booked ? t('cl_booked') : t('cl_book_at').replace('{time}', fmtTime(slot))}
            </button>
          </div>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </Section>

      {lightboxIndex !== null && photos.length > 0 && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
          onClick={() => setLightboxIndex(null)}
        >
          <button
            onClick={() => setLightboxIndex(null)}
            className="absolute top-4 right-4 w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center"
          >
            <X className="w-5 h-5" />
          </button>
          {photos.length > 1 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setLightboxIndex((i) => ((i ?? 0) - 1 + photos.length) % photos.length);
              }}
              className="absolute left-2 sm:left-4 w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>
          )}
          <img
            src={photos[lightboxIndex].image!}
            alt={photos[lightboxIndex].caption}
            onClick={(e) => e.stopPropagation()}
            className="max-w-full max-h-full object-contain rounded-lg"
          />
          {photos.length > 1 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setLightboxIndex((i) => ((i ?? 0) + 1) % photos.length);
              }}
              className="absolute right-2 sm:right-4 w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center"
            >
              <ChevronRight className="w-6 h-6" />
            </button>
          )}
        </div>
      )}
    </div>
  );
};

const MyBookings: React.FC = () => {
  const { t, lang } = useI18n();
  const [appts, setAppts] = useState<Appointment[] | null>(null);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .getMyBookings()
      .then(setAppts)
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : t('no_connection')),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(load, [load]);

  const cancel = async (a: Appointment) => {
    if (!window.confirm(t('cl_cancel_q'))) return;
    setBusyId(a.id);
    try {
      await api.cancelMy(a.id);
      load();
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : t('no_connection'));
    } finally {
      setBusyId(null);
    }
  };

  if (appts === null) {
    return (
      <div className="flex justify-center py-16 text-gray-400">
        {error ? <p className="text-red-600">{error}</p> : <Loader2 className="w-6 h-6 animate-spin" />}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {appts.length === 0 && (
        <EmptyState icon={<CalendarX className="w-5 h-5" />} message={t('cl_no_bookings')} />
      )}
      {appts.map((a) => {
        const d = new Date(a.start_time);
        return (
          <div key={a.id} className="bg-white rounded-xl border shadow-sm p-4 space-y-1">
            <div className="text-lg font-bold">
              {pad(d.getDate())}.{pad(d.getMonth() + 1)} {fmtTime(a.start_time)}
            </div>
            <div className="font-medium">
              {locText(lang, a.service_name, a.service_name_uz)}
              {a.car_details ? ` · ${a.car_details}` : ''}
            </div>
            <div className="text-sm text-gray-600 flex items-center gap-1.5">
              <Wrench className="w-3.5 h-3.5 shrink-0" /> {a.service_point_name} · {a.bay_name}
            </div>
            {!!(a.service_point_address || a.service_point_address_uz) && (
              <div className="text-sm text-gray-500 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 shrink-0" />
                {locText(lang, a.service_point_address, a.service_point_address_uz)}
              </div>
            )}
            <button
              onClick={() => cancel(a)}
              disabled={busyId === a.id}
              className="mt-2 w-full py-2 border border-red-300 text-red-600 rounded-xl font-medium hover:bg-red-50 transition-all active:scale-[0.98] disabled:opacity-50"
            >
              {t('cl_cancel')}
            </button>
          </div>
        );
      })}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
};
