import React, { useState } from 'react';
import { X, Phone, Clock, Car, ChevronRight, Send, User, Loader2, AlertTriangle } from 'lucide-react';
import { Appointment, AppointmentStatus } from '../types';
import { formatTime } from '../utils';
import { useI18n } from '../i18n';

interface Props {
  appointment: Appointment | null;
  isOpen: boolean;
  onClose: () => void;
  /** PATCH статуса на API; при ошибке кидает исключение — покажем его в панели */
  onUpdateStatus: (id: string, newStatus: AppointmentStatus) => Promise<void>;
  /** Отмена требует причины — открывает модалку у родителя, а не PATCH напрямую */
  onCancelRequest: (appointment: Appointment) => void;
}

export const SideDrawer: React.FC<Props> = ({
  appointment,
  isOpen,
  onClose,
  onUpdateStatus,
  onCancelRequest,
}) => {
  const { t, statuses } = useI18n();
  const [pendingStatus, setPendingStatus] = useState<AppointmentStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !appointment) return null;

  const update = async (status: AppointmentStatus) => {
    if (pendingStatus) return;
    if (status === 'cancelled') {
      onCancelRequest(appointment);
      return;
    }
    setPendingStatus(status);
    setError(null);
    try {
      await onUpdateStatus(appointment.id, status);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t('status_error'));
    } finally {
      setPendingStatus(null);
    }
  };

  const spinner = (status: AppointmentStatus) =>
    pendingStatus === status ? <Loader2 className="w-4 h-4 animate-spin" /> : null;

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40 transition-opacity" onClick={onClose} />

      <div className="fixed right-0 top-0 bottom-0 w-full sm:w-96 bg-white shadow-2xl z-50 flex flex-col">
        <div className="p-4 border-b flex justify-between items-center bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-800">{t('details')}</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded-full text-gray-500">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 flex-1 overflow-y-auto">
          <div className="mb-6">
            <h3 className="text-2xl font-bold text-gray-900 mb-1 flex items-center gap-2 flex-wrap">
              {appointment.client_name || t('no_name')}
              {appointment.source === 'telegram' ? (
                <Send className="w-4 h-4 text-gray-400" />
              ) : (
                <User className="w-4 h-4 text-gray-400" />
              )}
            </h3>
            {appointment.client_no_show_count > 0 && (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5 mb-1">
                <AlertTriangle className="w-3 h-3" />
                {t('no_show_badge').replace('{n}', String(appointment.client_no_show_count))}
              </span>
            )}
            {appointment.car_details && (
              <p className="text-gray-600 flex items-center gap-2">
                <Car className="w-4 h-4" /> {appointment.car_details}
              </p>
            )}
            {appointment.client_phone && (
              <p className="text-gray-600 flex items-center gap-2 mt-1">
                <Phone className="w-4 h-4" />
                <a href={`tel:${appointment.client_phone}`} className="text-blue-600 hover:underline">
                  {appointment.client_phone}
                </a>
              </p>
            )}
          </div>

          <div className="space-y-6">
            <div className="bg-gray-50 p-4 rounded-lg border border-gray-100">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-gray-500 mb-1">{t('service')}</p>
                  <p className="font-medium text-gray-900">{appointment.service_name}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    {t('type')}: {appointment.service_type === 'fixed' ? t('type_fixed') : t('type_flexible')}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">{t('bay')}: {appointment.bay_name}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-gray-500 mb-1">{t('time')}</p>
                  <p className="font-medium text-gray-900 flex items-center gap-1 justify-end">
                    <Clock className="w-4 h-4" />
                    {formatTime(appointment.start_time)} - {formatTime(appointment.estimated_end_time)}
                  </p>
                </div>
              </div>
              {appointment.note && (
                <p className="text-sm text-gray-600 mt-3 border-t pt-2">{appointment.note}</p>
              )}
            </div>

            <div>
              <p className="text-sm font-medium text-gray-900 mb-3">
                {t('current_status')}
                <span className="px-2 py-1 bg-gray-100 rounded-md ml-2">
                  {statuses[appointment.status]}
                </span>
              </p>

              <div className="flex flex-col gap-2">
                {appointment.status === 'scheduled' && (
                  <button
                    onClick={() => update('confirmed')}
                    className="w-full py-2 bg-blue-50 text-blue-700 font-medium rounded-md hover:bg-blue-100 border border-blue-200 flex justify-center items-center gap-2"
                  >
                    {spinner('confirmed')} {t('mark_confirmed')}
                  </button>
                )}

                {(appointment.status === 'scheduled' || appointment.status === 'confirmed') && (
                  <>
                    <button
                      onClick={() => update('in_progress')}
                      className="w-full py-3 bg-yellow-400 text-yellow-900 font-bold rounded-md hover:bg-yellow-500 shadow-sm flex justify-center items-center gap-2"
                    >
                      {spinner('in_progress')} {t('start_work')} <ChevronRight className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => update('no_show')}
                      className="w-full py-2 bg-red-50 text-red-700 font-medium rounded-md hover:bg-red-100 border border-red-200 flex justify-center items-center gap-2"
                    >
                      {spinner('no_show')} {t('no_show')}
                    </button>
                  </>
                )}

                {appointment.status === 'in_progress' && (
                  <>
                    <button
                      onClick={() => update('done')}
                      className="w-full py-3 bg-green-500 text-white font-bold rounded-md hover:bg-green-600 shadow-sm flex justify-center items-center gap-2"
                    >
                      {spinner('done')} {t('finish')} <ChevronRight className="w-4 h-4" />
                    </button>
                    {/* «Продлить время» (overrun) — этап 3 бэкенда */}
                  </>
                )}

                {(appointment.status === 'scheduled' || appointment.status === 'confirmed') && (
                  <button
                    onClick={() => update('cancelled')}
                    className="w-full py-2 mt-4 text-gray-500 font-medium hover:text-gray-700 hover:bg-gray-50 rounded-md flex justify-center items-center gap-2"
                  >
                    {spinner('cancelled')} {t('cancel_appt')}
                  </button>
                )}

                {error && (
                  <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md p-3 mt-2">
                    {error}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
