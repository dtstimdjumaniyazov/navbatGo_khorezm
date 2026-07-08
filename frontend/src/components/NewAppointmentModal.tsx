import React, { useState, useEffect } from 'react';
import { X, Calendar, Loader2 } from 'lucide-react';
import { Bay, Service } from '../types';
import { useI18n } from '../i18n';

export interface NewAppointmentForm {
  bayId: string;
  startTime: string; // "HH:MM"
  serviceId: string;
  durationMinutes: number;
  clientName: string;
  phone: string;
  carDetails: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  bays: Bay[];
  services: Service[];
  prefilledBayId?: string;
  prefilledTime?: string;
  /** POST на API; при ошибке должен кинуть исключение — модалка покажет его и останется открытой */
  onSave: (form: NewAppointmentForm) => Promise<void>;
}

export const NewAppointmentModal: React.FC<Props> = ({
  isOpen,
  onClose,
  bays,
  services,
  prefilledBayId,
  prefilledTime,
  onSave,
}) => {
  const { t } = useI18n();
  const [bayId, setBayId] = useState('');
  const [startTime, setStartTime] = useState('09:00');
  const [serviceId, setServiceId] = useState('');
  const [duration, setDuration] = useState('');
  const [clientName, setClientName] = useState('');
  const [phone, setPhone] = useState('+998');
  const [carDetails, setCarDetails] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setBayId(prefilledBayId ?? bays[0]?.id ?? '');
      if (prefilledTime) setStartTime(prefilledTime);
      setError(null);
    }
  }, [isOpen, prefilledBayId, prefilledTime, bays]);

  if (!isOpen) return null;

  const selectedService = services.find((s) => s.id === serviceId);

  // Услуга выбирается из списка; длительность подставляется из неё,
  // но мастер может переопределить (для flexible это норма)
  const handleServiceChange = (id: string) => {
    setServiceId(id);
    const svc = services.find((s) => s.id === id);
    if (svc) setDuration(String(svc.duration_minutes));
  };

  const resetForm = () => {
    setServiceId('');
    setDuration('');
    setClientName('');
    setPhone('+998');
    setCarDetails('');
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!serviceId || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await onSave({
        bayId,
        startTime,
        serviceId,
        durationMinutes: parseInt(duration, 10),
        clientName: clientName.trim(),
        phone: phone.trim() === '+998' ? '' : phone.trim(),
        carDetails: carDetails.trim(),
      });
      resetForm();
      onClose();
    } catch (err: unknown) {
      // 409 (пост занят) и прочие ошибки сервера — показываем в форме
      setError(err instanceof Error ? err.message : t('create_error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b flex justify-between items-center bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-blue-600" />
            {t('new_appointment')}
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded-full text-gray-500">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto">
          <form id="new-appointment-form" onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('bay')}</label>
                <select
                  value={bayId}
                  onChange={(e) => setBayId(e.target.value)}
                  className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                >
                  {bays.map((bay) => (
                    <option key={bay.id} value={bay.id}>
                      {bay.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('start_time')}</label>
                <input
                  type="time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('service')}</label>
              <select
                value={serviceId}
                onChange={(e) => handleServiceChange(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                required
              >
                <option value="" disabled>
                  {t('choose_service')}
                </option>
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.duration_minutes} {t('min_short')}
                    {s.service_type === 'flexible' ? `, ${t('flexible_mark')}` : ''})
                  </option>
                ))}
              </select>
              {selectedService?.service_type === 'flexible' && (
                <p className="text-xs text-amber-600 mt-1">{t('flexible_note')}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('duration_min')}
              </label>
              <input
                type="number"
                step="5"
                min="5"
                max="600"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder={t('duration_placeholder')}
                required
              />
            </div>

            <div className="pt-2 border-t mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('client_name')}</label>
              <input
                type="text"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Азиз"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('phone')}</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="+998 90 123 45 67"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('car')}</label>
                <input
                  type="text"
                  value={carDetails}
                  onChange={(e) => setCarDetails(e.target.value)}
                  className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Chevrolet Cobalt"
                  maxLength={120}
                />
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md p-3">
                {error}
              </div>
            )}
          </form>
        </div>

        <div className="p-4 border-t bg-gray-50 flex justify-end gap-3 mt-auto">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 font-medium hover:bg-gray-100"
          >
            {t('cancel')}
          </button>
          <button
            type="submit"
            form="new-appointment-form"
            disabled={isSubmitting}
            className="px-4 py-2 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 shadow-sm disabled:opacity-60 flex items-center gap-2"
          >
            {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
            {t('save')}
          </button>
        </div>
      </div>
    </div>
  );
};
