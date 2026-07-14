import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { api, ApiError, legalUrls, partnerContactUrl, saveTokens } from '../api/client';
import { PressableScale } from '../components/PressableScale';
import { t } from '../i18n';
import { colors, radius } from '../theme';

interface Props {
  onLogin: () => void;
}

/**
 * Вход через Telegram: кнопка → открывается бот с одноразовым кодом →
 * мастер жмёт Start → приложение опрашивает сервер и получает JWT.
 */
export const LoginScreen: React.FC<Props> = ({ onLogin }) => {
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState('');
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = (message = '') => {
    if (pollTimer.current) clearInterval(pollTimer.current);
    pollTimer.current = null;
    setWaiting(false);
    setError(message);
  };

  useEffect(() => () => stopPolling(), []);

  const startLogin = async () => {
    setError('');
    try {
      const { code, deep_link, expires_in } = await api.tgLoginStart();
      if (!deep_link) {
        setError('Сервер не настроен: не задан BOT_USERNAME.');
        return;
      }
      await Linking.openURL(deep_link);
      setWaiting(true);
      const deadline = Date.now() + expires_in * 1000;
      pollTimer.current = setInterval(async () => {
        if (Date.now() > deadline) {
          stopPolling('Код входа истёк — попробуйте ещё раз.');
          return;
        }
        try {
          const res = await api.tgLoginPoll(code);
          if (res.status === 'ok' && res.access && res.refresh) {
            stopPolling();
            await saveTokens(res.access, res.refresh);
            onLogin();
          }
          // pending — просто ждём следующего опроса
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) {
            stopPolling('Код недействителен или истёк — попробуйте ещё раз.');
          }
          // сетевые ошибки не прерывают ожидание
        }
      }, 2500);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Нет соединения с сервером');
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.logo}>
        <Text style={styles.logoText}>N</Text>
      </View>
      <Text style={styles.title}>NavbatGo</Text>
      <Text style={styles.subtitle}>Приложение для сервисов</Text>

      {waiting ? (
        <View style={styles.waitBox}>
          <ActivityIndicator color={colors.primary} size="large" />
          <Text style={styles.waitText}>
            Подтвердите вход: нажмите Start в открывшемся Telegram-боте
          </Text>
          <Pressable onPress={() => stopPolling()} style={styles.cancelBtn}>
            <Text style={styles.cancelText}>Отмена</Text>
          </Pressable>
        </View>
      ) : (
        <PressableScale onPress={startLogin} style={styles.tgBtn}>
          <Text style={styles.tgBtnText}>Войти через Telegram</Text>
        </PressableScale>
      )}

      {!!error && <Text style={styles.error}>{error}</Text>}
      {!waiting && (
        <Text style={styles.hint}>
          Откроется Telegram — нажмите Start, и вы войдёте автоматически.
          Мастера попадают в панель сервиса, клиенты — к записи.
        </Text>
      )}

      <Text style={styles.legal}>
        Продолжая, вы соглашаетесь с{' '}
        <Text style={styles.legalLink} onPress={() => Linking.openURL(legalUrls('ru').oferta)}>
          офертой
        </Text>{' '}
        и{' '}
        <Text style={styles.legalLink} onPress={() => Linking.openURL(legalUrls('ru').privacy)}>
          политикой конфиденциальности
        </Text>
      </Text>

      {!!partnerContactUrl('ru') && (
        <Pressable onPress={() => Linking.openURL(partnerContactUrl('ru')!)} style={styles.partnerLink}>
          <Text style={styles.partnerLinkText}>{t('ru', 'become_partner')}</Text>
        </Pressable>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  logo: {
    width: 88,
    height: 88,
    borderRadius: 22,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  logoText: { color: '#fff', fontSize: 48, fontWeight: '800' },
  title: { fontSize: 28, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 15, color: colors.muted, marginTop: 4, marginBottom: 40 },
  tgBtn: {
    backgroundColor: '#229ED9', // фирменный цвет Telegram
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 16,
    width: '100%',
    alignItems: 'center',
    shadowColor: '#229ED9',
    shadowOpacity: 0.35,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  tgBtnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
  waitBox: { alignItems: 'center', gap: 16, width: '100%' },
  waitText: { textAlign: 'center', color: colors.text, fontSize: 15, lineHeight: 22 },
  cancelBtn: { padding: 12 },
  cancelText: { color: colors.muted, fontSize: 15 },
  error: { color: colors.danger, marginTop: 16, textAlign: 'center' },
  hint: { color: colors.muted, fontSize: 13, textAlign: 'center', marginTop: 24, lineHeight: 19 },
  legal: { color: colors.muted, fontSize: 12, textAlign: 'center', marginTop: 16, lineHeight: 17 },
  legalLink: { textDecorationLine: 'underline' },
  partnerLink: { marginTop: 20 },
  partnerLinkText: { color: colors.muted, fontSize: 13, textDecorationLine: 'underline' },
});
