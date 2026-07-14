import React, { useEffect, useState } from 'react';
import { X, Ban } from 'lucide-react';
import { useI18n } from '../i18n';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** Отправка отмены; при ошибке должен кинуть исключение — модалка покажет его и останется открытой */
  onConfirm: (reason: string) => Promise<void>;
}

/** Причина обязательна — уходит клиенту в Telegram-уведомлении об отмене. */
export const CancelReasonModal: React.FC<Props> = ({ isOpen, onClose, onConfirm }) => {
  const { t } = useI18n();
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setReason('');
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setError(t('cancel_reason_required'));
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : t('create_error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b flex justify-between items-center bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Ban className="w-5 h-5 text-red-600" />
            {t('cancel_reason_title')}
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded-full text-gray-500">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={submit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('cancel_reason_label')}
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              autoFocus
              placeholder={t('cancel_reason_placeholder')}
              className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-2 justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-gray-700 hover:bg-gray-100 font-medium"
            >
              {t('cancel_reason_back')}
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold disabled:opacity-60"
            >
              {isSubmitting ? t('cancel_reason_sending') : t('cancel_reason_confirm')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
