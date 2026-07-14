import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { api, ApiError } from '../../api/client';
import { Lang, t } from '../../i18n';
import { registerForPushToken } from '../../push';
import { cardShadow, colors, radius } from '../../theme';
import { NotificationChannel } from '../../types';

interface Props {
  lang: Lang;
}

/** Настройки клиента: канал уведомлений (Telegram/push) — меняется в любой момент. */
export const SettingsScreen: React.FC<Props> = ({ lang }) => {
  const [channel, setChannel] = useState<NotificationChannel | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .getMySettings()
      .then((s) => setChannel(s.notification_channel))
      .catch((e) => setError(e instanceof ApiError ? e.message : t(lang, 'no_connection')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchChannel = async (c: NotificationChannel) => {
    if (c === channel || busy) return;
    setBusy(true);
    setError('');
    try {
      if (c === 'push') {
        const { token, error: pushError } = await registerForPushToken();
        if (!token) {
          setError(pushError || t(lang, 'push_failed'));
          return;
        }
        await api.registerPushToken(token);
      }
      await api.patchMySettings(c);
      setChannel(c);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
    } finally {
      setBusy(false);
    }
  };

  if (channel === null) {
    return (
      <View style={styles.center}>
        {error ? (
          <Text style={styles.error}>{error}</Text>
        ) : (
          <ActivityIndicator color={colors.primary} size="large" />
        )}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t(lang, 'settings_title')}</Text>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t(lang, 'notif_title')}</Text>
        <View style={styles.row}>
          {(['telegram', 'push'] as const).map((c) => (
            <Pressable
              key={c}
              onPress={() => switchChannel(c)}
              disabled={busy}
              style={[styles.btn, channel === c && styles.btnActive]}
            >
              <Text style={[styles.btnText, channel === c && styles.btnTextActive]}>
                {busy && c !== channel ? '…' : t(lang, c === 'telegram' ? 'notif_telegram' : 'notif_push')}
              </Text>
            </Pressable>
          ))}
        </View>
        {!!error && <Text style={styles.error}>{error}</Text>}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: 16, gap: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 8,
    ...cardShadow,
  },
  cardTitle: { fontSize: 15, fontWeight: '800', color: colors.text },
  row: { flexDirection: 'row', gap: 8 },
  btn: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 14,
    backgroundColor: '#fff',
  },
  btnActive: { borderColor: colors.primary, backgroundColor: '#eff6ff' },
  btnText: { color: colors.muted, fontWeight: '600', fontSize: 14 },
  btnTextActive: { color: colors.primary },
  error: { color: colors.danger, fontSize: 13 },
});
