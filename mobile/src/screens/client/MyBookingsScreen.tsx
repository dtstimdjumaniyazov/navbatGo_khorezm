import { CalendarX, MapPin, Wrench } from 'lucide-react-native';
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { api, ApiError } from '../../api/client';
import { EmptyState } from '../../components/EmptyState';
import { PressableScale } from '../../components/PressableScale';
import { Lang, locText, t } from '../../i18n';
import { cardShadow, colors, radius } from '../../theme';
import { Appointment } from '../../types';
import { fmtTime } from '../../utils';

interface Props {
  lang: Lang;
}

/** Мои записи клиента: список активных с отменой. */
export const MyBookingsScreen: React.FC<Props> = ({ lang }) => {
  const [appts, setAppts] = useState<Appointment[] | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setAppts(await api.getMyBookings());
      setError('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const cancel = (a: Appointment) =>
    Alert.alert(
      t(lang, 'cancel_q'),
      `${fmtDate(a.start_time)} · ${locText(lang, a.service_name, a.service_name_uz)}`,
      [
        { text: t(lang, 'no'), style: 'cancel' },
        {
          text: t(lang, 'cancel_booking'),
          style: 'destructive',
          onPress: async () => {
            setBusyId(a.id);
            try {
              await api.cancelMy(a.id);
              await load();
            } catch (e) {
              Alert.alert(
                t(lang, 'fail_title'),
                e instanceof ApiError ? e.message : t(lang, 'no_connection'),
              );
            } finally {
              setBusyId(null);
            }
          },
        },
      ],
    );

  if (appts === null) {
    return (
      <View style={styles.center}>
        {error ? <Text style={styles.error}>{error}</Text> : <ActivityIndicator color={colors.primary} size="large" />}
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={async () => {
            setRefreshing(true);
            await load();
            setRefreshing(false);
          }}
        />
      }
    >
      <Text style={styles.title}>{t(lang, 'my_title')}</Text>
      {appts.length === 0 && (
        <EmptyState icon={<CalendarX size={18} color={colors.primary} />} message={t(lang, 'my_empty')} />
      )}
      {appts.map((a) => (
        <View key={a.id} style={styles.card}>
          <Text style={styles.time}>{fmtDate(a.start_time)}</Text>
          <Text style={styles.service}>
            {locText(lang, a.service_name, a.service_name_uz)}
            {a.car_details ? ` · ${a.car_details}` : ''}
          </Text>
          <View style={styles.metaRow}>
            <Wrench size={13} color={colors.muted} />
            <Text style={styles.meta}>{a.service_point_name} · {a.bay_name}</Text>
          </View>
          {!!(a.service_point_address || a.service_point_address_uz) && (
            <View style={styles.metaRow}>
              <MapPin size={13} color={colors.muted} />
              <Text style={styles.meta}>
                {locText(lang, a.service_point_address, a.service_point_address_uz)}
              </Text>
            </View>
          )}
          <PressableScale
            style={[styles.cancelBtn, busyId === a.id && styles.busy]}
            onPress={() => cancel(a)}
          >
            <Text style={styles.cancelText}>{t(lang, 'cancel_booking')}</Text>
          </PressableScale>
        </View>
      ))}
    </ScrollView>
  );
};

function fmtDate(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)} ${fmtTime(iso)}`;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, gap: 10, paddingBottom: 32 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  error: { color: colors.danger, textAlign: 'center' },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 4,
    ...cardShadow,
  },
  time: { fontSize: 20, fontWeight: '800', color: colors.text },
  service: { fontSize: 15, color: colors.text, fontWeight: '600' },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  meta: { color: colors.muted, fontSize: 13 },
  cancelBtn: {
    marginTop: 8,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
  },
  busy: { opacity: 0.5 },
  cancelText: { color: colors.danger, fontWeight: '700' },
});
