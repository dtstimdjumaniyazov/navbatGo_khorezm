import { Clock } from 'lucide-react-native';
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { api, ApiError } from '../api/client';
import { EmptyState } from '../components/EmptyState';
import { PressableScale } from '../components/PressableScale';
import { Lang, t } from '../i18n';
import { colors, radius } from '../theme';
import { Service, Slot } from '../types';
import { dateKey, dateLabel, fmtTime } from '../utils';

interface Props {
  lang: Lang;
  onCreated: () => void;
}

/** Запись клиента «с улицы»: услуга → дата и время → имя/телефон. */
export const NewBookingScreen: React.FC<Props> = ({ lang, onCreated }) => {
  const [services, setServices] = useState<Service[] | null>(null);
  const [service, setService] = useState<Service | null>(null);

  const days = nextDays(7);
  const todayK = dateKey(new Date());
  const [day, setDay] = useState(days[0]);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [car, setCar] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .getServices()
      .then(setServices)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : t(lang, 'no_connection')),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!service) return;
    setSlots(null);
    setSlot(null);
    api
      .getSlots(service.id, dateKey(day))
      .then(setSlots)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : t(lang, 'no_connection')),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [service, day]);

  const create = async () => {
    if (!service || !slot || saving) return;
    if (!name.trim() && !phone.trim()) {
      setError(t(lang, 'm_need_contact'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api.createAppointment({
        client_name: name.trim(),
        client_phone: phone.trim(),
        service: service.id,
        start_time: slot.start,
        car_details: car.trim(),
      });
      Alert.alert(
        t(lang, 'm_booked'),
        `${dateLabel(day, todayK, lang)}, ${fmtTime(slot.start)} · ${service.name}`,
      );
      setService(null);
      setSlot(null);
      setName('');
      setPhone('');
      setCar('');
      onCreated();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError(e.message);
        setSlot(null);
        // слот увели — перезагружаем свободное время
        api.getSlots(service.id, dateKey(day)).then(setSlots).catch(() => {});
      } else {
        setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Шаг 1: услуга */}
      <Text style={styles.step}>{t(lang, 'm_step_service')}</Text>
      {services === null && <ActivityIndicator color={colors.primary} />}
      <View style={styles.wrapRow}>
        {(services ?? []).map((s) => (
          <Pressable
            key={s.id}
            style={[styles.option, service?.id === s.id && styles.optionActive]}
            onPress={() => setService(s)}
          >
            <Text
              style={[styles.optionText, service?.id === s.id && styles.optionTextActive]}
            >
              {s.name}
            </Text>
            <Text
              style={[styles.optionSub, service?.id === s.id && styles.optionTextActive]}
            >
              {s.duration_minutes} {t(lang, 'min')}
              {s.service_type === 'flexible' ? ` · ${t(lang, 'approx')}` : ''}
              {s.price ? ` · ${Number(s.price).toLocaleString('ru')} ${t(lang, 'sum')}` : ''}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* Шаг 2: дата и время */}
      {service && (
        <>
          <Text style={styles.step}>{t(lang, 'm_step_when')}</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <View style={styles.row}>
              {days.map((d) => {
                const active = dateKey(d) === dateKey(day);
                return (
                  <Pressable
                    key={dateKey(d)}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() => setDay(d)}
                  >
                    <Text style={[styles.chipText, active && styles.chipTextActive]}>
                      {dateLabel(d, todayK, lang)}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </ScrollView>
          {slots === null && <ActivityIndicator color={colors.primary} />}
          {slots !== null && slots.length === 0 && (
            <EmptyState icon={<Clock size={18} color={colors.primary} />} message={t(lang, 'no_slots')} />
          )}
          <View style={styles.wrapRow}>
            {(slots ?? []).map((s) => {
              const active = slot?.start === s.start;
              return (
                <Pressable
                  key={s.start}
                  style={[styles.timeBtn, active && styles.chipActive]}
                  onPress={() => setSlot(s)}
                >
                  <Text style={[styles.timeText, active && styles.chipTextActive]}>
                    {fmtTime(s.start)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </>
      )}

      {/* Шаг 3: клиент */}
      {service && slot && (
        <>
          <Text style={styles.step}>{t(lang, 'm_step_client')}</Text>
          <TextInput
            style={styles.input}
            placeholder={t(lang, 'm_name')}
            placeholderTextColor={colors.muted}
            value={name}
            onChangeText={setName}
            maxLength={200}
          />
          <TextInput
            style={styles.input}
            placeholder={t(lang, 'm_phone_hint')}
            placeholderTextColor={colors.muted}
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            maxLength={32}
          />
          <TextInput
            style={styles.input}
            placeholder={t(lang, 'car')}
            placeholderTextColor={colors.muted}
            value={car}
            onChangeText={setCar}
            maxLength={120}
          />
          <PressableScale
            style={[styles.saveBtn, saving && styles.saveBusy]}
            onPress={create}
          >
            <Text style={styles.saveText}>
              {saving
                ? t(lang, 'm_booking')
                : t(lang, 'm_book_at', { time: fmtTime(slot.start) })}
            </Text>
          </PressableScale>
        </>
      )}

      {!!error && <Text style={styles.error}>{error}</Text>}
    </ScrollView>
  );
};

function nextDays(count: number): Date[] {
  const result: Date[] = [];
  for (let i = 0; i < count; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    result.push(d);
  }
  return result;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40, gap: 10 },
  step: { fontSize: 17, fontWeight: '800', color: colors.text, marginTop: 10 },
  wrapRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  row: { flexDirection: 'row', gap: 8, paddingVertical: 2 },
  option: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius,
    paddingVertical: 10,
    paddingHorizontal: 14,
    minWidth: '47%',
  },
  optionActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  optionText: { fontWeight: '700', color: colors.text, fontSize: 15 },
  optionSub: { color: colors.muted, fontSize: 12, marginTop: 2 },
  optionTextActive: { color: '#fff' },
  chip: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.text, fontWeight: '600', fontSize: 14 },
  chipTextActive: { color: '#fff' },
  timeBtn: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingVertical: 10,
    width: '22.7%',
    alignItems: 'center',
  },
  timeText: { fontWeight: '700', color: colors.text, fontSize: 15 },
  input: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    fontSize: 16,
    color: colors.text,
  },
  saveBtn: {
    backgroundColor: colors.success,
    borderRadius: 16,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 6,
    shadowColor: colors.success,
    shadowOpacity: 0.3,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
  },
  saveBusy: { opacity: 0.6 },
  saveText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  error: { color: colors.danger, fontSize: 14, marginTop: 6 },
});
