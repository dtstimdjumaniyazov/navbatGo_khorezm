import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Calendar, Clock, Images, Info, MapPin } from 'lucide-react-native';
import YoutubePlayer from 'react-native-youtube-iframe';

import { api, ApiError } from '../../api/client';
import { EmptyState } from '../../components/EmptyState';
import { PressableScale } from '../../components/PressableScale';
import { Section } from '../../components/Section';
import { Lang, locText, t } from '../../i18n';
import { cardShadow, colors, radius } from '../../theme';
import { ClientInfo, PublicPoint, PublicService, Slot } from '../../types';
import { dateKey, dateLabel, fmtTime, mapLinks, youtubeId } from '../../utils';

interface Props {
  point: PublicPoint;
  me: ClientInfo | null;
  lang: Lang;
  onBack: () => void;
  onBooked: () => void;
}

/** Витрина сервиса + запись: услуга → день/время → подтверждение. */
// Короткие имена дней, индекс = weekday бэкенда (0=Пн … 6=Вс)
const WEEKDAYS_SHORT: Record<'ru' | 'uz', string[]> = {
  ru: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
  uz: ['Душ', 'Сеш', 'Чор', 'Пай', 'Жум', 'Шан', 'Якш'],
};

export const PointScreen: React.FC<Props> = ({ point, me, lang, onBack, onBooked }) => {
  const days = nextDays(14, point.schedule);
  const todayK = dateKey(new Date());

  const [service, setService] = useState<PublicService | null>(null);
  const [day, setDay] = useState(days[0]);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [name, setName] = useState(me?.name ?? '');
  const [phone, setPhone] = useState(me?.phone ?? '');
  const [car, setCar] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [openVideoId, setOpenVideoId] = useState<string | null>(null);
  const [videoWidth, setVideoWidth] = useState(0);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

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

  const book = async () => {
    if (!service || !slot || saving) return;
    setSaving(true);
    setError('');
    try {
      await api.bookMy({
        service: service.id,
        start_time: slot.start,
        name: name.trim(),
        phone: phone.trim(),
        car_details: car.trim(),
      });
      Alert.alert(
        t(lang, 'booked_title'),
        `${point.name}\n${dateLabel(day, todayK, lang)}, ${fmtTime(slot.start)} · ${locText(lang, service.name, service.name_uz)}`,
      );
      onBooked();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError(e.message);
        setSlot(null);
        api.getSlots(service.id, dateKey(day)).then(setSlots).catch(() => {});
      } else {
        setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
      }
    } finally {
      setSaving(false);
    }
  };

  const photos = point.media.filter((m) => m.media_type === 'photo' && m.image);
  const videos = point.media.filter((m) => m.media_type === 'video' && m.video_url);
  const hasInfo = !!point.description || !!point.instagram || point.managers.length > 0;
  const hasSchedule = point.schedule?.length === 7;
  const hasAddress = !!point.address || point.latitude != null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Pressable onPress={onBack} style={styles.backBtn}>
        <Text style={styles.backText}>{t(lang, 'back_all')}</Text>
      </Pressable>

      <Text style={styles.name}>{point.name}</Text>

      {hasInfo && (
        <Section
          title={t(lang, 'info_title')}
          icon={<Info size={20} color={colors.primary} />}
          defaultOpen
        >
          {!!point.description && (
            <Text style={styles.desc}>
              {locText(lang, point.description, point.description_uz)}
            </Text>
          )}
          {!!point.instagram && (
            <Pressable onPress={() => Linking.openURL(point.instagram)}>
              <Text style={styles.link}>📸 Instagram</Text>
            </Pressable>
          )}
          {point.managers.length > 0 && (
            <View style={styles.mastersBox}>
              <Text style={styles.subheading}>{t(lang, 'masters')}</Text>
              {point.managers.map((m) => (
                <View key={m.id} style={styles.masterCard}>
                  {m.avatar ? (
                    <Image source={{ uri: m.avatar }} style={styles.avatar} />
                  ) : (
                    <View style={[styles.avatar, styles.avatarStub]}>
                      <Text>👤</Text>
                    </View>
                  )}
                  <View style={styles.masterBody}>
                    <Text style={styles.masterName}>{m.name || t(lang, 'master')}</Text>
                    {m.experience_years != null && (
                      <Text style={styles.masterMeta}>
                        {t(lang, 'exp', { n: m.experience_years })}
                      </Text>
                    )}
                    {!!m.bio && (
                      <Text style={styles.masterBio}>{locText(lang, m.bio, m.bio_uz)}</Text>
                    )}
                  </View>
                </View>
              ))}
            </View>
          )}
        </Section>
      )}

      {(photos.length > 0 || videos.length > 0) && (
        <Section
          title={t(lang, 'gallery_title')}
          icon={<Images size={20} color={colors.primary} />}
        >
          {photos.length > 0 && (
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.gallery}>
                {photos.map((m, i) => (
                  <Pressable key={m.id} onPress={() => setLightboxIndex(i)}>
                    <Image source={{ uri: m.image! }} style={styles.galleryImg} />
                  </Pressable>
                ))}
              </View>
            </ScrollView>
          )}
          {videos.map((v) => {
            const id = youtubeId(v.video_url);
            const isOpen = openVideoId === v.id;
            return (
              <View key={v.id} style={styles.videoBox}>
                {isOpen && id ? (
                  <View
                    style={styles.videoPlayer}
                    onLayout={(e) => setVideoWidth(e.nativeEvent.layout.width)}
                  >
                    {/* react-native-youtube-iframe правильно реализует официальный
                        YouTube IFrame Player API внутри WebView — ручная сборка
                        embed-страницы ловила Error 153/152 (проблемы Origin/Referer) */}
                    {videoWidth > 0 && (
                      <YoutubePlayer
                        height={Math.round((videoWidth * 9) / 16)}
                        width={videoWidth}
                        play
                        videoId={id}
                        webViewProps={{
                          allowsInlineMediaPlayback: true,
                          mediaPlaybackRequiresUserAction: false,
                        }}
                      />
                    )}
                    <Pressable
                      onPress={() => setOpenVideoId(null)}
                      style={styles.videoCloseBtn}
                      accessibilityLabel={t(lang, 'video_collapse')}
                    >
                      <Text style={styles.videoCloseText}>✕</Text>
                    </Pressable>
                  </View>
                ) : (
                  <Pressable onPress={() => setOpenVideoId(v.id)} style={styles.videoThumbWrap}>
                    {id ? (
                      <Image
                        source={{ uri: `https://img.youtube.com/vi/${id}/hqdefault.jpg` }}
                        style={styles.videoThumb}
                      />
                    ) : (
                      <View style={[styles.videoThumb, { backgroundColor: '#1f2937' }]} />
                    )}
                    <View style={styles.videoPlayOverlay}>
                      <View style={styles.videoPlayBtn}>
                        <Text style={styles.videoPlayIcon}>▶</Text>
                      </View>
                    </View>
                    {!!v.caption && (
                      <View style={styles.videoCaptionBar}>
                        <Text style={styles.videoCaptionText} numberOfLines={1}>
                          {v.caption}
                        </Text>
                      </View>
                    )}
                  </Pressable>
                )}
              </View>
            );
          })}
        </Section>
      )}

      {hasSchedule && (
        <Section title={t(lang, 'hours')} icon={<Clock size={20} color={colors.primary} />}>
          {point.schedule.map((e) => (
            <View key={e.weekday} style={styles.hoursRow}>
              <Text style={styles.hoursDay}>{WEEKDAYS_SHORT[lang][e.weekday]}</Text>
              <Text style={e.start ? styles.hoursTime : styles.hoursClosed}>
                {e.start ? `${e.start}–${e.end}` : t(lang, 'closed')}
              </Text>
            </View>
          ))}
        </Section>
      )}

      {hasAddress && (
        <Section
          title={t(lang, 'address_title')}
          icon={<MapPin size={20} color={colors.primary} />}
        >
          {!!point.address && (
            <Text style={styles.address}>
              {locText(lang, point.address, point.address_uz)}
            </Text>
          )}
          <View style={styles.mapRow}>
            <PressableScale
              style={styles.mapBtn}
              onPress={() =>
                Linking.openURL(
                  mapLinks(point.latitude, point.longitude, point.address).google,
                )
              }
            >
              <Text style={styles.mapBtnText}>🗺 Google Maps</Text>
            </PressableScale>
            <PressableScale
              style={styles.mapBtn}
              onPress={() =>
                Linking.openURL(
                  mapLinks(point.latitude, point.longitude, point.address).yandex,
                )
              }
            >
              <Text style={styles.mapBtnText}>📍 Яндекс Карты</Text>
            </PressableScale>
          </View>
        </Section>
      )}

      <Section
        title={t(lang, 'book')}
        icon={<Calendar size={20} color={colors.primary} />}
        defaultOpen
      >
        <View style={styles.wrapRow}>
          {point.services.map((s) => {
            const active = service?.id === s.id;
            return (
              <Pressable
                key={s.id}
                style={[styles.option, active && styles.optionActive]}
                onPress={() => setService(s)}
              >
                <Text style={[styles.optionText, active && styles.optionTextActive]}>
                  {locText(lang, s.name, s.name_uz)}
                </Text>
                <Text style={[styles.optionSub, active && styles.optionTextActive]}>
                  {s.duration_minutes} {t(lang, 'min')}
                  {s.service_type === 'flexible' ? ` · ${t(lang, 'approx')}` : ''}
                  {s.price
                    ? ` · ${Number(s.price).toLocaleString('ru')} ${t(lang, 'sum')}`
                    : ''}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {service && (
          <>
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

        {service && slot && (
          <>
            <TextInput
              style={styles.input}
              placeholder={t(lang, 'your_name')}
              placeholderTextColor={colors.muted}
              value={name}
              onChangeText={setName}
              maxLength={200}
            />
            <TextInput
              style={styles.input}
              placeholder={t(lang, 'phone')}
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
            <PressableScale style={[styles.saveBtn, saving && styles.busy]} onPress={book}>
              <Text style={styles.saveText}>
                {saving
                  ? t(lang, 'booking')
                  : t(lang, 'book_at', { time: fmtTime(slot.start) })}
              </Text>
            </PressableScale>
          </>
        )}

        {!!error && <Text style={styles.error}>{error}</Text>}
      </Section>

      <Modal
        visible={lightboxIndex !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setLightboxIndex(null)}
      >
        <Pressable style={styles.lightboxBackdrop} onPress={() => setLightboxIndex(null)}>
          {lightboxIndex !== null && (
            <Image
              source={{ uri: photos[lightboxIndex].image! }}
              style={styles.lightboxImage}
              resizeMode="contain"
            />
          )}
          <Pressable onPress={() => setLightboxIndex(null)} style={styles.lightboxClose}>
            <Text style={styles.lightboxCloseText}>✕</Text>
          </Pressable>
          {photos.length > 1 && (
            <>
              <Pressable
                onPress={() =>
                  setLightboxIndex((i) => ((i ?? 0) - 1 + photos.length) % photos.length)
                }
                style={[styles.lightboxNav, styles.lightboxNavLeft]}
              >
                <Text style={styles.lightboxNavText}>‹</Text>
              </Pressable>
              <Pressable
                onPress={() => setLightboxIndex((i) => ((i ?? 0) + 1) % photos.length)}
                style={[styles.lightboxNav, styles.lightboxNavRight]}
              >
                <Text style={styles.lightboxNavText}>›</Text>
              </Pressable>
            </>
          )}
        </Pressable>
      </Modal>
    </ScrollView>
  );
};

/** Ближайшие рабочие дни по графику (schedule[weekday].start === null — выходной). */
function nextDays(horizon: number, schedule: PublicPoint['schedule']): Date[] {
  const result: Date[] = [];
  for (let i = 0; i < horizon && result.length < 7; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    const entry = schedule?.[(d.getDay() + 6) % 7];
    if (!entry || entry.start !== null) {
      result.push(d);
    }
  }
  return result.length > 0 ? result : [new Date()]; // некорректный график — не падаем
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40, gap: 10 },
  backBtn: { paddingVertical: 4 },
  backText: { color: colors.primary, fontSize: 15, fontWeight: '600' },
  name: { fontSize: 22, fontWeight: '800', color: colors.text },
  desc: { color: colors.text, fontSize: 14, lineHeight: 20 },
  address: { color: colors.muted, fontSize: 14 },
  link: { color: colors.primary, fontSize: 15, fontWeight: '600' },
  gallery: { flexDirection: 'row', gap: 8 },
  galleryImg: { width: 140, height: 105, borderRadius: 10 },
  videoBox: { borderRadius: radius, overflow: 'hidden', backgroundColor: '#000' },
  videoThumbWrap: { width: '100%', aspectRatio: 16 / 9 },
  videoThumb: { width: '100%', height: '100%' },
  videoPlayOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  videoPlayBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#dc2626',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 4,
  },
  videoPlayIcon: { color: '#fff', fontSize: 22, marginLeft: 3 },
  videoCaptionBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  videoCaptionText: { color: '#fff', fontSize: 12 },
  videoPlayer: { width: '100%', aspectRatio: 16 / 9, position: 'relative' },
  videoCloseBtn: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(0,0,0,0.7)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  videoCloseText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  subheading: { fontSize: 13, fontWeight: '800', color: colors.muted },
  mastersBox: { gap: 10 },
  masterCard: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: colors.card,
    borderRadius: radius,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    ...cardShadow,
  },
  avatar: { width: 56, height: 56, borderRadius: 28 },
  avatarStub: {
    backgroundColor: '#e5e7eb',
    alignItems: 'center',
    justifyContent: 'center',
  },
  masterBody: { flex: 1, gap: 2 },
  masterName: { fontWeight: '700', color: colors.text, fontSize: 15 },
  masterMeta: { color: colors.muted, fontSize: 13 },
  masterBio: { color: colors.text, fontSize: 13, lineHeight: 18 },
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
    backgroundColor: colors.primary,
    borderRadius: 16,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 6,
    shadowColor: colors.primary,
    shadowOpacity: 0.3,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
  },
  busy: { opacity: 0.6 },
  saveText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  error: { color: colors.danger, fontSize: 14 },
  hoursRow: { flexDirection: 'row', justifyContent: 'space-between', maxWidth: 220 },
  hoursDay: { color: colors.muted, fontSize: 13 },
  hoursTime: { color: colors.text, fontSize: 13, fontWeight: '600' },
  hoursClosed: { color: colors.muted, fontSize: 13 },
  mapRow: { flexDirection: 'row', gap: 8 },
  mapBtn: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  mapBtnText: { color: colors.text, fontWeight: '600', fontSize: 13 },
  lightboxBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.92)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  lightboxImage: { width: '100%', height: '80%' },
  lightboxClose: {
    position: 'absolute',
    top: 48,
    right: 16,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  lightboxCloseText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  lightboxNav: {
    position: 'absolute',
    top: '50%',
    marginTop: -22,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  lightboxNavLeft: { left: 12 },
  lightboxNavRight: { right: 12 },
  lightboxNavText: { color: '#fff', fontSize: 26, fontWeight: '700' },
});
