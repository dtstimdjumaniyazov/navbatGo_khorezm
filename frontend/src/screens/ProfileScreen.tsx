import React, { useEffect, useRef, useState } from 'react';
import { Camera, Loader2, Trash2, User } from 'lucide-react';
import { api, ApiError, legalUrls, ManagerProfile } from '../api/client';
import { ServicePoint, WorkingHours } from '../types';
import { useI18n } from '../i18n';

interface Props {
  onError: (msg: string) => void;
  servicePoint: ServicePoint | null;
  onServicePointSaved: (patch: Partial<ServicePoint>) => void;
}

function youtubeThumb(url: string): string | null {
  const m = url.match(/(?:youtu\.be\/|v=|shorts\/|embed\/)([\w-]{6,})/);
  return m ? `https://img.youtube.com/vi/${m[1]}/mqdefault.jpg` : null;
}

// weekday бэкенда: 0=Пн … 6=Вс (не путать с JS Date.getDay(), там 0=Вс)
const WEEKDAY_LABELS: Record<'ru' | 'uz', string[]> = {
  ru: ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
  uz: ['Душанба', 'Сешанба', 'Чоршанба', 'Пайшанба', 'Жума', 'Шанба', 'Якшанба'],
};

/** Часы по дням недели: из существующих переопределений или из базового графика точки. */
function buildWeekHours(sp: ServicePoint): WorkingHours[] {
  return Array.from({ length: 7 }, (_, weekday) => {
    const override = sp.working_hours?.find((h) => h.weekday === weekday);
    if (override) return override;
    return {
      weekday,
      is_closed: !sp.work_days.includes(weekday),
      work_start: sp.work_start,
      work_end: sp.work_end,
    };
  });
}

/** Третья вкладка: публичный профиль мастера — «о себе», фото, галерея. */
export const ProfileScreen: React.FC<Props> = ({
  onError,
  servicePoint,
  onServicePointSaved,
}) => {
  const { t, lang } = useI18n();
  const legal = legalUrls(lang);
  const [profile, setProfile] = useState<ManagerProfile | null>(null);
  const [notManager, setNotManager] = useState(false);
  const [name, setName] = useState('');
  const [bio, setBio] = useState('');
  const [bioUz, setBioUz] = useState('');
  const [exp, setExp] = useState('');
  const [spAbout, setSpAbout] = useState(servicePoint?.description ?? '');
  const [spAboutUz, setSpAboutUz] = useState(servicePoint?.description_uz ?? '');
  const [remindHours, setRemindHours] = useState(
    String(servicePoint?.reminder_hours_before ?? ''),
  );
  const [leadMinutes, setLeadMinutes] = useState(
    String(servicePoint?.min_lead_minutes ?? ''),
  );
  const [weekHours, setWeekHours] = useState<WorkingHours[]>(
    servicePoint ? buildWeekHours(servicePoint) : [],
  );
  const [isSaving, setIsSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const avatarInput = useRef<HTMLInputElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .getProfile()
      .then((p) => {
        setProfile(p);
        setName(p.name);
        setBio(p.bio);
        setBioUz(p.bio_uz);
        setExp(p.experience_years != null ? String(p.experience_years) : '');
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) setNotManager(true);
        else onError(e instanceof ApiError ? e.message : t('no_connection'));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setSpAbout(servicePoint?.description ?? '');
    setSpAboutUz(servicePoint?.description_uz ?? '');
    setRemindHours(String(servicePoint?.reminder_hours_before ?? ''));
    setLeadMinutes(String(servicePoint?.min_lead_minutes ?? ''));
    setWeekHours(servicePoint ? buildWeekHours(servicePoint) : []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [servicePoint?.id]);

  const updateDay = (weekday: number, patch: Partial<WorkingHours>) => {
    setWeekHours((prev) => prev.map((h) => (h.weekday === weekday ? { ...h, ...patch } : h)));
  };

  const flashSaved = () => {
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 2500);
  };

  const save = async () => {
    if (!profile || isSaving) return;
    const hours = parseInt(remindHours, 10);
    if (Number.isNaN(hours) || hours < 1 || hours > 48) {
      onError(t('p_remind_err'));
      return;
    }
    const lead = parseInt(leadMinutes, 10);
    if (Number.isNaN(lead) || lead < 0 || lead > 1440) {
      onError(t('p_lead_err'));
      return;
    }
    for (const h of weekHours) {
      if (!h.is_closed && !(h.work_start && h.work_end)) {
        onError(t('p_hours_err'));
        return;
      }
      if (!h.is_closed && h.work_start && h.work_end && h.work_start >= h.work_end) {
        onError(t('p_hours_order_err'));
        return;
      }
    }
    setIsSaving(true);
    try {
      const updated = await api.patchProfile({
        name,
        bio,
        bio_uz: bioUz,
        experience_years: exp === '' ? null : parseInt(exp, 10),
      });
      setProfile(updated);
      const patch: Partial<ServicePoint> = {
        description: spAbout,
        description_uz: spAboutUz,
        reminder_hours_before: hours,
        min_lead_minutes: lead,
        working_hours: weekHours,
      };
      await api.patchServicePoint(profile.service_point, patch);
      onServicePointSaved(patch);
      flashSaved();
    } catch (e: unknown) {
      onError(e instanceof ApiError ? e.message : t('no_connection'));
    } finally {
      setIsSaving(false);
    }
  };

  const uploadAvatar = async (file: File) => {
    const fd = new FormData();
    fd.append('avatar', file);
    try {
      setProfile(await api.patchProfile(fd));
      flashSaved();
    } catch (e: unknown) {
      onError(e instanceof ApiError ? e.message : t('no_connection'));
    }
  };

  const addPhoto = async (file: File) => {
    const fd = new FormData();
    fd.append('image', file);
    try {
      await api.addMedia(fd);
      setProfile(await api.getProfile());
    } catch (e: unknown) {
      onError(e instanceof ApiError ? e.message : t('no_connection'));
    }
  };

  const addVideo = async () => {
    const url = window.prompt(t('video_url_prompt'));
    if (!url) return;
    const fd = new FormData();
    fd.append('video_url', url.trim());
    try {
      await api.addMedia(fd);
      setProfile(await api.getProfile());
    } catch (e: unknown) {
      onError(e instanceof ApiError ? e.message : t('no_connection'));
    }
  };

  const removeMedia = async (id: string) => {
    if (!window.confirm(t('delete_confirm'))) return;
    try {
      await api.deleteMedia(id);
      setProfile(await api.getProfile());
    } catch (e: unknown) {
      onError(e instanceof ApiError ? e.message : t('no_connection'));
    }
  };

  if (notManager) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 p-6 text-center">
        {t('profile_title')}: —
      </div>
    );
  }
  if (!profile) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  const photos = profile.media.filter((m) => m.media_type === 'photo');
  const videos = profile.media.filter((m) => m.media_type === 'video');

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-5 max-w-2xl mx-auto w-full">
      {/* Шапка профиля */}
      <div className="bg-white rounded-xl border shadow-sm p-4 flex items-center gap-4">
        <button
          onClick={() => avatarInput.current?.click()}
          className="relative w-20 h-20 rounded-full bg-gray-100 overflow-hidden flex items-center justify-center text-gray-400 shrink-0"
          aria-label={t('add_photo')}
        >
          {profile.avatar ? (
            <img src={profile.avatar} alt="" className="w-full h-full object-cover" />
          ) : (
            <User className="w-8 h-8" />
          )}
          <span className="absolute bottom-0 inset-x-0 bg-black/40 text-white flex justify-center py-0.5">
            <Camera className="w-3.5 h-3.5" />
          </span>
        </button>
        <input
          ref={avatarInput}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && uploadAvatar(e.target.files[0])}
        />
        <div className="min-w-0">
          <div className="font-bold text-lg text-gray-900 truncate">
            {profile.name || t('no_name')}
          </div>
          <div className="text-sm text-gray-500 truncate">{profile.service_point_name}</div>
        </div>
      </div>

      {/* Поля профиля */}
      <div className="bg-white rounded-xl border shadow-sm p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('profile_name')}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-gray-300 rounded-md p-2"
            maxLength={200}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('profile_about')}
          </label>
          <textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            rows={4}
            className="w-full border border-gray-300 rounded-md p-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('profile_about_uz')}
          </label>
          <textarea
            value={bioUz}
            onChange={(e) => setBioUz(e.target.value)}
            rows={4}
            className="w-full border border-gray-300 rounded-md p-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('profile_exp')}
          </label>
          <input
            type="number"
            min="0"
            max="60"
            value={exp}
            onChange={(e) => setExp(e.target.value)}
            className="w-32 border border-gray-300 rounded-md p-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t('sp_about')}</label>
          <textarea
            value={spAbout}
            onChange={(e) => setSpAbout(e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded-md p-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">{t('sp_about_uz')}</label>
          <textarea
            value={spAboutUz}
            onChange={(e) => setSpAboutUz(e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded-md p-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('p_remind')}
          </label>
          <input
            type="number"
            min="1"
            max="48"
            value={remindHours}
            onChange={(e) => setRemindHours(e.target.value)}
            className="w-32 border border-gray-300 rounded-md p-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('p_lead')}
          </label>
          <input
            type="number"
            min="0"
            max="1440"
            value={leadMinutes}
            onChange={(e) => setLeadMinutes(e.target.value)}
            className="w-32 border border-gray-300 rounded-md p-2"
          />
        </div>
      </div>

      {/* График работы по дням недели — переопределяет базовые часы точки */}
      <div className="bg-white rounded-xl border shadow-sm p-4 space-y-3">
        <h2 className="font-bold text-gray-900">{t('p_hours_title')}</h2>
        <div className="space-y-2">
          {weekHours.map((h) => (
            <div key={h.weekday} className="flex items-center gap-3 flex-wrap">
              <span className="w-28 shrink-0 text-sm text-gray-700">
                {WEEKDAY_LABELS[lang][h.weekday]}
              </span>
              <label className="flex items-center gap-1.5 text-sm text-gray-600 shrink-0">
                <input
                  type="checkbox"
                  checked={h.is_closed}
                  onChange={(e) => updateDay(h.weekday, { is_closed: e.target.checked })}
                />
                {t('p_hours_closed')}
              </label>
              {!h.is_closed && (
                <>
                  <input
                    type="time"
                    value={h.work_start?.slice(0, 5) ?? ''}
                    onChange={(e) => updateDay(h.weekday, { work_start: e.target.value })}
                    className="border border-gray-300 rounded-md p-1.5 text-sm"
                  />
                  <span className="text-gray-400">–</span>
                  <input
                    type="time"
                    value={h.work_end?.slice(0, 5) ?? ''}
                    onChange={(e) => updateDay(h.weekday, { work_end: e.target.value })}
                    className="border border-gray-300 rounded-md p-1.5 text-sm"
                  />
                </>
              )}
            </div>
          ))}
        </div>
        <button
          onClick={save}
          disabled={isSaving}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-60 flex justify-center items-center gap-2"
        >
          {isSaving && <Loader2 className="w-4 h-4 animate-spin" />}
          {savedFlash ? t('saved') : t('save_profile')}
        </button>
      </div>

      {/* Галерея: фото и видео показаны и редактируются раздельно */}
      <div className="bg-white rounded-xl border shadow-sm p-4 space-y-4">
        <h2 className="font-bold text-gray-900">{t('gallery')}</h2>

        {/* Фото */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-500">{t('gallery_photos')}</h3>
            <button
              onClick={() => photoInput.current?.click()}
              className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium"
            >
              {t('add_photo')}
            </button>
            <input
              ref={photoInput}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && addPhoto(e.target.files[0])}
            />
          </div>
          {photos.length === 0 ? (
            <p className="text-gray-400 text-sm">—</p>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              {photos.map((m) => (
                <div
                  key={m.id}
                  className="relative aspect-square rounded-lg overflow-hidden bg-gray-100 group"
                >
                  <img src={m.image!} alt={m.caption} className="w-full h-full object-cover" />
                  <button
                    onClick={() => removeMedia(m.id)}
                    className="absolute top-1 right-1 bg-black/50 hover:bg-red-600 text-white rounded p-1"
                    aria-label={t('delete_item')}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Видео: не более одного — кнопка добавления скрыта, пока текущее не удалено */}
        <div className="space-y-2 pt-3 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-500">{t('gallery_video')}</h3>
            {videos.length === 0 && (
              <button
                onClick={addVideo}
                className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium"
              >
                {t('add_video')}
              </button>
            )}
          </div>
          {videos.length === 0 ? (
            <p className="text-gray-400 text-sm">{t('gallery_no_video')}</p>
          ) : (
            videos.map((m) => {
              const thumb = youtubeThumb(m.video_url);
              return (
                <div
                  key={m.id}
                  className="relative aspect-video max-w-xs rounded-lg overflow-hidden bg-gray-100 group"
                >
                  <a
                    href={m.video_url}
                    target="_blank"
                    rel="noreferrer"
                    className="w-full h-full flex items-center justify-center"
                  >
                    {thumb ? (
                      <img src={thumb} alt={m.caption} className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-xs text-gray-500 p-2 break-all">{m.video_url}</span>
                    )}
                    <span className="absolute inset-0 flex items-center justify-center text-white text-3xl drop-shadow">
                      ▶
                    </span>
                  </a>
                  <button
                    onClick={() => removeMedia(m.id)}
                    className="absolute top-1 right-1 bg-black/50 hover:bg-red-600 text-white rounded p-1"
                    aria-label={t('delete_item')}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      <p className="text-center text-xs text-gray-400 pb-2">
        <a href={legal.oferta} target="_blank" rel="noopener noreferrer" className="underline hover:text-gray-600">
          {t('legal_oferta')}
        </a>{' '}
        {t('legal_and')}{' '}
        <a href={legal.privacy} target="_blank" rel="noopener noreferrer" className="underline hover:text-gray-600">
          {t('legal_privacy')}
        </a>
      </p>
    </div>
  );
};
