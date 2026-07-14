import React, { useEffect, useRef, useState } from 'react';
import { Wrench, Loader2, Send } from 'lucide-react';
import { api, ApiError, legalUrls, partnerContactUrl } from '../api/client';
import { useI18n } from '../i18n';

interface Props {
  onSuccess: () => void;
}

export const LoginScreen: React.FC<Props> = ({ onSuccess }) => {
  const { t, lang } = useI18n();
  const legal = legalUrls(lang);
  const partnerUrl = partnerContactUrl(lang);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tgWaiting, setTgWaiting] = useState(false);
  const pollTimer = useRef<number | null>(null);

  const stopPolling = (message: string | null = null) => {
    if (pollTimer.current !== null) window.clearInterval(pollTimer.current);
    pollTimer.current = null;
    setTgWaiting(false);
    setError(message);
  };

  useEffect(() => () => stopPolling(), []);

  const tgLogin = async () => {
    setError(null);
    try {
      const { code, deep_link, expires_in } = await api.tgLoginStart();
      if (!deep_link) {
        setError('BOT_USERNAME не задан на сервере');
        return;
      }
      window.open(deep_link, '_blank', 'noopener');
      setTgWaiting(true);
      const deadline = Date.now() + expires_in * 1000;
      pollTimer.current = window.setInterval(async () => {
        if (Date.now() > deadline) {
          stopPolling(t('tg_login_failed'));
          return;
        }
        try {
          const res = await api.tgLoginPoll(code);
          if (res.status === 'ok') {
            stopPolling();
            onSuccess();
          }
          // pending — ждём следующего опроса
        } catch (err: unknown) {
          if (err instanceof ApiError && err.status === 404) {
            stopPolling(t('tg_login_failed'));
          }
          // сетевые сбои не прерывают ожидание
        }
      }, 2500);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('no_connection'));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await api.login(username.trim(), password);
      onSuccess();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) setError(t('login_error'));
      else setError(err instanceof Error ? err.message : t('no_connection'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="h-screen flex flex-col items-center justify-center bg-gray-100 p-4 gap-4">
      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-xl shadow-lg p-8 w-full max-w-sm space-y-4"
      >
        <div className="flex items-center justify-center gap-2 text-blue-700 font-bold text-xl mb-2">
          <Wrench className="w-6 h-6" />
          <span>navbatGo</span>
        </div>
        <h1 className="text-center text-gray-700 font-medium">{t('login_title')}</h1>

        {tgWaiting ? (
          <div className="space-y-3 text-center">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600 mx-auto" />
            <p className="text-sm text-gray-600">{t('tg_login_waiting')}</p>
            <button
              type="button"
              onClick={() => stopPolling()}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              {t('tg_login_cancel')}
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={tgLogin}
            className="w-full py-3 bg-[#229ED9] hover:bg-[#1e8dc2] text-white rounded-2xl font-bold shadow-lg shadow-[#229ED9]/25 hover:shadow-[#229ED9]/35 transition-all active:scale-[0.98] flex items-center justify-center gap-2"
          >
            <Send className="w-4 h-4" />
            {t('tg_login_btn')}
          </button>
        )}

        <div className="flex items-center gap-3 text-xs text-gray-400">
          <div className="flex-1 border-t border-gray-200" />
          {t('or_divider')}
          <div className="flex-1 border-t border-gray-200" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('login_username')}
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
            autoComplete="username"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('login_password')}
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
            autoComplete="current-password"
            required
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md p-3">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium shadow-sm transition-all active:scale-[0.98] disabled:opacity-60 flex items-center justify-center gap-2"
        >
          {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
          {t('login_btn')}
        </button>

        <p className="text-center text-xs text-gray-400">
          {t('legal_agreement')}{' '}
          <a href={legal.oferta} target="_blank" rel="noopener noreferrer" className="underline hover:text-gray-600">
            {t('legal_oferta')}
          </a>{' '}
          {t('legal_and')}{' '}
          <a href={legal.privacy} target="_blank" rel="noopener noreferrer" className="underline hover:text-gray-600">
            {t('legal_privacy')}
          </a>
          {t('legal_suffix') ? ` ${t('legal_suffix')}` : ''}
        </p>
      </form>

      {partnerUrl && (
        <a
          href={partnerUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-gray-500 hover:text-blue-600 underline"
        >
          {t('cl_become_partner')}
        </a>
      )}
    </div>
  );
};
