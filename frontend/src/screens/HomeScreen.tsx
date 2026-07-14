import React, { useCallback, useEffect, useState } from 'react';
import { Phone, Car, CalendarClock, MapPin, Loader2, Send, User, Wrench, AlertTriangle } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { CancelReasonModal } from '../components/CancelReasonModal';
import { EmptyState } from '../components/EmptyState';
import { Appointment, AppointmentStatus } from '../types';
import { formatTime, toDateParam } from '../utils';
import { useI18n } from '../i18n';

interface Props {
  onError: (msg: string) => void;
}

/**
 * Task-first главный экран: что на постах сейчас и кто дальше.
 * Крупные кнопки действий, никаких календарных сеток.
 */
export const HomeScreen: React.FC<Props> = ({ onError }) => {
  const { t, statuses } = useI18n();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);

  const load = useCallback(async () => {
    try {
      setAppointments(await api.getAppointments(toDateParam(new Date())));
    } catch (e: unknown) {
      onError(e instanceof ApiError ? e.message : t('no_connection'));
    } finally {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 60_000); // день живёт — обновляемся раз в минуту
    return () => clearInterval(timer);
  }, [load]);

  const inProgress = appointments.filter((a) => a.status === 'in_progress');
  const upcoming = appointments
    .filter((a) => a.status === 'scheduled' || a.status === 'confirmed')
    .sort((a, b) => a.start_time.localeCompare(b.start_time));

  const act = async (fn: () => Promise<unknown>, id: string) => {
    if (busyId) return;
    setBusyId(id);
    try {
      await fn();
      await load();
    } catch (e: unknown) {
      onError(e instanceof ApiError ? e.message : t('no_connection'));
    } finally {
      setBusyId(null);
    }
  };

  const updateStatus = (a: Appointment, status: AppointmentStatus) => {
    if (status === 'no_show' && !window.confirm(t('confirm_noshow_q'))) return;
    if (status === 'cancelled') {
      setCancelTarget(a);
      return;
    }
    act(() => api.updateAppointmentStatus(a.id, status), a.id);
  };

  const confirmCancel = async (reason: string) => {
    if (!cancelTarget) return;
    await api.updateAppointmentStatus(cancelTarget.id, 'cancelled', reason);
    setCancelTarget(null);
    await load();
  };

  const extend = (a: Appointment, minutes: number) =>
    act(async () => {
      try {
        await api.extendAppointment(a.id, minutes);
      } catch (e: unknown) {
        // Наезд на следующие записи → предлагаем сдвиг очереди
        if (e instanceof ApiError && e.status === 409 && e.body?.needs_shift) {
          const n = Number(e.body.conflicts ?? 1);
          const q = t('confirm_shift_q').replace('{n}', String(n)).replace('{min}', String(minutes));
          if (!window.confirm(q)) return;
          const res = await api.shiftQueue(a.id, minutes);
          await api.extendAppointment(a.id, minutes);
          setFlash(
            t('shift_done_msg')
              .replace('{n}', String(res.shifted_count))
              .replace('{sent}', String(res.notified)),
          );
          setTimeout(() => setFlash(null), 6000);
          return;
        }
        throw e;
      }
    }, a.id);

  const clientLine = (a: Appointment) => (
    <div className="flex items-center gap-2 flex-wrap text-sm text-gray-600">
      <span className="font-semibold text-gray-900 text-base">
        {a.client_name || t('no_name')}
      </span>
      {a.source === 'telegram' ? (
        <Send className="w-3.5 h-3.5 text-gray-400" />
      ) : (
        <User className="w-3.5 h-3.5 text-gray-400" />
      )}
      {a.client_no_show_count > 0 && (
        <span className="flex items-center gap-1 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5">
          <AlertTriangle className="w-3 h-3" />
          {t('no_show_badge').replace('{n}', String(a.client_no_show_count))}
        </span>
      )}
      {a.client_phone && (
        <a href={`tel:${a.client_phone}`} className="text-blue-600 flex items-center gap-1">
          <Phone className="w-3.5 h-3.5" /> {a.client_phone}
        </a>
      )}
      {a.car_details && (
        <span className="flex items-center gap-1">
          <Car className="w-3.5 h-3.5" /> {a.car_details}
        </span>
      )}
    </div>
  );

  const spin = (id: string) =>
    busyId === id ? <Loader2 className="w-4 h-4 animate-spin" /> : null;

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-6 max-w-2xl mx-auto w-full">
      {flash && (
        <div className="bg-green-50 border border-green-200 text-green-800 text-sm rounded-lg p-3">
          {flash}
        </div>
      )}

      {/* На постах сейчас */}
      <section>
        <h2 className="font-bold text-gray-900 mb-3">{t('now_in_progress')}</h2>
        {inProgress.length === 0 ? (
          <EmptyState icon={<Wrench className="w-5 h-5" />} message={t('now_empty_progress')} />
        ) : (
          <div className="space-y-3">
            {inProgress.map((a) => (
              <div
                key={a.id}
                className="bg-white rounded-xl border-l-4 border-l-yellow-400 border border-yellow-200 shadow-sm p-4 space-y-3"
              >
                {clientLine(a)}
                <div className="text-sm text-gray-600 flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-800">{a.service_name}</span>
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5" /> {a.bay_name}
                  </span>
                  <span>
                    {a.actual_start &&
                      t('started_at').replace('{time}', formatTime(a.actual_start))}
                    {' · '}
                    {t('until_time').replace('{time}', formatTime(a.estimated_end_time))}
                  </span>
                </div>
                <button
                  onClick={() => updateStatus(a, 'done')}
                  className="w-full py-3 bg-green-500 hover:bg-green-600 text-white font-bold rounded-lg shadow-sm flex justify-center items-center gap-2"
                >
                  {spin(a.id)} {t('act_finish')}
                </button>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">{t('extend_label')}</span>
                  {[15, 30, 60].map((m) => (
                    <button
                      key={m}
                      onClick={() => extend(a, m)}
                      className="flex-1 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium rounded-lg text-sm"
                    >
                      +{m}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Дальше сегодня */}
      <section>
        <h2 className="font-bold text-gray-900 mb-3">{t('now_next')}</h2>
        {upcoming.length === 0 ? (
          <EmptyState icon={<CalendarClock className="w-5 h-5" />} message={t('now_empty_next')} />
        ) : (
          <div className="space-y-3">
            {upcoming.map((a, idx) => (
              <div
                key={a.id}
                className={`bg-white rounded-xl border shadow-sm p-4 space-y-3 ${
                  idx === 0 ? 'border-blue-300' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1.5">
                    {clientLine(a)}
                    <div className="text-sm text-gray-600 flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-gray-800">{a.service_name}</span>
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5" /> {a.bay_name}
                      </span>
                      <span className="text-xs bg-gray-100 rounded px-1.5 py-0.5">
                        {statuses[a.status]}
                      </span>
                    </div>
                  </div>
                  <div className="text-xl font-bold text-gray-900 whitespace-nowrap">
                    {formatTime(a.start_time)}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => updateStatus(a, 'in_progress')}
                    className="flex-1 py-2.5 bg-yellow-400 hover:bg-yellow-500 text-yellow-900 font-bold rounded-lg flex justify-center items-center gap-2"
                  >
                    {spin(a.id)} {t('act_start')}
                  </button>
                  <button
                    onClick={() => updateStatus(a, 'no_show')}
                    className="py-2.5 px-3 bg-red-50 hover:bg-red-100 text-red-700 font-medium rounded-lg text-sm border border-red-200"
                  >
                    {t('act_noshow')}
                  </button>
                  <button
                    onClick={() => updateStatus(a, 'cancelled')}
                    className="py-2.5 px-3 text-gray-400 hover:text-gray-600 text-sm"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <CancelReasonModal
        isOpen={!!cancelTarget}
        onClose={() => setCancelTarget(null)}
        onConfirm={confirmCancel}
      />
    </div>
  );
};
