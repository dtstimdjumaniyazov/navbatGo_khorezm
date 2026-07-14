import { AlertTriangle, CalendarClock, Wrench } from 'lucide-react-native';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { api, ApiError } from '../api/client';
import { CancelReasonModal } from '../components/CancelReasonModal';
import { EmptyState } from '../components/EmptyState';
import { PressableScale } from '../components/PressableScale';
import { Lang, locText, t } from '../i18n';
import { cardShadow, colors, radius } from '../theme';
import { Appointment } from '../types';
import { dateKey, fmtTime } from '../utils';

interface Props {
  lang: Lang;
}

/**
 * Главный экран — «что мне делать сейчас»: машины на постах сверху,
 * очередь ниже. Простой список, никакой сетки.
 */
export const TodayScreen: React.FC<Props> = ({ lang }) => {
  const [appts, setAppts] = useState<Appointment[] | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);

  const load = useCallback(async (silent = false) => {
    try {
      const list = await api.getAppointments(dateKey(new Date()));
      setAppts(list);
      setError('');
    } catch (e) {
      if (!silent) setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => load(true), 60_000);
    return () => clearInterval(timer);
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const groups = useMemo(() => {
    const list = appts ?? [];
    return {
      inProgress: list.filter((a) => a.status === 'in_progress'),
      upcoming: list.filter((a) => a.status === 'scheduled' || a.status === 'confirmed'),
      finished: list.filter((a) =>
        ['done', 'no_show', 'cancelled'].includes(a.status),
      ),
    };
  }, [appts]);

  const run = async (id: string, fn: () => Promise<unknown>) => {
    if (busyId) return;
    setBusyId(id);
    try {
      await fn();
      await load(true);
    } catch (e) {
      Alert.alert(
        t(lang, 'fail_title'),
        e instanceof ApiError ? e.message : t(lang, 'no_connection'),
      );
    } finally {
      setBusyId(null);
    }
  };

  const doAction = (a: Appointment, action: 'start' | 'finish' | 'no_show' | 'cancel') =>
    run(a.id, () => api.appointmentAction(a.id, action));

  const confirmNoShow = (a: Appointment) =>
    Alert.alert(
      t(lang, 'm_noshow_q'),
      t(lang, 'm_noshow_msg', { name: a.client_name || t(lang, 'm_no_name') }),
      [
        { text: t(lang, 'm_no'), style: 'cancel' },
        { text: t(lang, 'm_noshow'), style: 'destructive', onPress: () => doAction(a, 'no_show') },
      ],
    );

  const confirmCancel = (a: Appointment) => setCancelTarget(a);

  const submitCancel = async (reason: string) => {
    if (!cancelTarget) return;
    await api.appointmentAction(cancelTarget.id, 'cancel', reason);
    setCancelTarget(null);
    await load(true);
  };

  const extend = (a: Appointment, minutes: number) =>
    run(a.id, async () => {
      try {
        await api.extend(a.id, minutes);
      } catch (e) {
        if (e instanceof ApiError && (e.body as any)?.needs_shift) {
          const conflicts = (e.body as any).conflicts as number;
          Alert.alert(
            t(lang, 'm_shift_title'),
            t(lang, 'm_shift_q', { n: conflicts, min: minutes }),
            [
              { text: t(lang, 'm_no'), style: 'cancel' },
              {
                text: t(lang, 'm_shift_do'),
                onPress: () =>
                  run(a.id, async () => {
                    const res = await api.shiftQueue(a.id, minutes);
                    await api.extend(a.id, minutes);
                    Alert.alert(
                      t(lang, 'm_done_title'),
                      t(lang, 'm_shift_done', { n: res.shifted_count, sent: res.notified }),
                    );
                  }),
              },
            ],
          );
          return; // ошибку не пробрасываем — решение за мастером
        }
        throw e;
      }
    });

  const callClient = (phone: string) => Linking.openURL(`tel:${phone}`);

  if (error && appts === null) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <Pressable style={styles.retryBtn} onPress={() => load()}>
          <Text style={styles.retryText}>{t(lang, 'retry')}</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.sectionTitle}>{t(lang, 'm_now_progress')}</Text>
      {groups.inProgress.length === 0 && (
        <EmptyState
          icon={<Wrench size={18} color={colors.primary} />}
          message={t(lang, 'm_empty_progress')}
        />
      )}
      {groups.inProgress.map((a) => (
        <View key={a.id} style={[styles.card, styles.cardActive]}>
          <CardHeader a={a} lang={lang} onCall={callClient} />
          <Text style={styles.until}>
            {t(lang, 'm_until', { time: fmtTime(a.estimated_end_time) })}
            {a.actual_start
              ? t(lang, 'm_started_at', { time: fmtTime(a.actual_start) })
              : ''}
          </Text>
          <PressableScale
            style={[styles.bigBtn, styles.successBtn, busyId === a.id && styles.btnBusy]}
            onPress={() => doAction(a, 'finish')}
          >
            <Text style={styles.bigBtnText}>{t(lang, 'm_finish')}</Text>
          </PressableScale>
          <View style={styles.row}>
            <Text style={styles.extendLabel}>{t(lang, 'm_delay')}</Text>
            {[15, 30, 60].map((m) => (
              <PressableScale
                key={m}
                style={[styles.chip, busyId === a.id && styles.btnBusy]}
                onPress={() => extend(a, m)}
              >
                <Text style={styles.chipText}>+{m} {t(lang, 'min')}</Text>
              </PressableScale>
            ))}
          </View>
        </View>
      ))}

      <Text style={styles.sectionTitle}>{t(lang, 'm_now_next')}</Text>
      {groups.upcoming.length === 0 && (
        <EmptyState
          icon={<CalendarClock size={18} color={colors.primary} />}
          message={t(lang, 'm_empty_next')}
        />
      )}
      {groups.upcoming.map((a) => (
        <View key={a.id} style={[styles.card, styles.cardUpcoming]}>
          <CardHeader a={a} lang={lang} onCall={callClient} />
          <PressableScale
            style={[styles.bigBtn, styles.primaryBtn, busyId === a.id && styles.btnBusy]}
            onPress={() => doAction(a, 'start')}
          >
            <Text style={styles.bigBtnText}>{t(lang, 'm_start')}</Text>
          </PressableScale>
          <View style={styles.row}>
            <Pressable style={styles.linkBtn} onPress={() => confirmNoShow(a)}>
              <Text style={styles.linkDanger}>{t(lang, 'm_noshow')}</Text>
            </Pressable>
            <Pressable style={styles.linkBtn} onPress={() => confirmCancel(a)}>
              <Text style={styles.linkMuted}>{t(lang, 'm_cancel_word')}</Text>
            </Pressable>
          </View>
        </View>
      ))}

      {groups.finished.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>{t(lang, 'm_finished')}</Text>
          {groups.finished.map((a) => (
            <View key={a.id} style={[styles.card, styles.cardMuted]}>
              <Text style={styles.mutedLine}>
                {fmtTime(a.start_time)} · {a.client_name || t(lang, 'm_no_name')} ·{' '}
                {locText(lang, a.service_name, a.service_name_uz)} ·{' '}
                {statusLabel(lang, a.status)}
              </Text>
            </View>
          ))}
        </>
      )}

      <CancelReasonModal
        visible={!!cancelTarget}
        lang={lang}
        onClose={() => setCancelTarget(null)}
        onConfirm={submitCancel}
      />
    </ScrollView>
  );
};

function statusLabel(lang: Lang, status: string): string {
  if (status === 'done') return t(lang, 'st_done');
  if (status === 'no_show') return t(lang, 'st_no_show');
  if (status === 'cancelled') return t(lang, 'st_cancelled');
  return status;
}

const CardHeader: React.FC<{
  a: Appointment;
  lang: Lang;
  onCall: (phone: string) => void;
}> = ({ a, lang, onCall }) => (
  <View>
    <View style={styles.headerRow}>
      <Text style={styles.time}>{fmtTime(a.start_time)}</Text>
      <Text style={styles.bay}>{a.bay_name}</Text>
    </View>
    <Text style={styles.client}>{a.client_name || t(lang, 'm_no_name')}</Text>
    {a.client_no_show_count > 0 && (
      <View style={styles.noShowBadge}>
        <AlertTriangle size={12} color={colors.danger} />
        <Text style={styles.noShowBadgeText}>
          {t(lang, 'm_no_show_badge', { n: a.client_no_show_count })}
        </Text>
      </View>
    )}
    <Text style={styles.service}>
      {locText(lang, a.service_name, a.service_name_uz)}
      {a.car_details ? ` · ${a.car_details}` : ''}
    </Text>
    {!!a.client_phone && (
      <Pressable onPress={() => onCall(a.client_phone)}>
        <Text style={styles.phone}>📞 {a.client_phone}</Text>
      </Pressable>
    )}
  </View>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 32, gap: 10 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 },
  errorText: { color: colors.danger, textAlign: 'center', fontSize: 15 },
  retryBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: 28,
    borderRadius: radius,
  },
  retryText: { color: '#fff', fontWeight: '700' },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.text,
    marginTop: 12,
    marginBottom: 2,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 10,
    ...cardShadow,
  },
  cardActive: { backgroundColor: colors.inProgressBg, borderColor: colors.primary },
  // Активная (ещё не начатая) запись — синий акцент слева, как на веб-графике
  cardUpcoming: { borderLeftWidth: 4, borderLeftColor: colors.primary },
  cardMuted: { paddingVertical: 10 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  time: { fontSize: 22, fontWeight: '800', color: colors.text },
  bay: { color: colors.muted, fontSize: 13 },
  client: { fontSize: 16, fontWeight: '700', color: colors.text, marginTop: 2 },
  noShowBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    backgroundColor: '#fef2f2',
    borderWidth: 1,
    borderColor: '#fecaca',
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginTop: 4,
  },
  noShowBadgeText: { color: colors.danger, fontSize: 12, fontWeight: '700' },
  service: { color: colors.muted, fontSize: 14, marginTop: 1 },
  phone: { color: colors.primary, fontSize: 15, marginTop: 4, fontWeight: '600' },
  until: { color: colors.text, fontSize: 14 },
  bigBtn: {
    borderRadius: 16,
    paddingVertical: 14,
    alignItems: 'center',
    shadowOpacity: 0.25,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 4,
  },
  primaryBtn: { backgroundColor: colors.primary, shadowColor: colors.primary },
  successBtn: { backgroundColor: colors.success, shadowColor: colors.success },
  btnBusy: { opacity: 0.5 },
  bigBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  extendLabel: { color: colors.muted, fontSize: 13 },
  chip: {
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 14,
  },
  chipText: { color: colors.primary, fontWeight: '700', fontSize: 14 },
  linkBtn: { paddingVertical: 8, paddingHorizontal: 4, flex: 1, alignItems: 'center' },
  linkDanger: { color: colors.danger, fontSize: 14, fontWeight: '600' },
  linkMuted: { color: colors.muted, fontSize: 14, fontWeight: '600' },
  mutedLine: { color: colors.muted, fontSize: 13 },
});
