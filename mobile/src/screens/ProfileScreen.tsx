import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { api, ApiError, clearTokens, legalUrls } from '../api/client';
import { Lang, t } from '../i18n';
import { registerForPushToken } from '../push';
import { cardShadow, colors, radius } from '../theme';
import { ManagerProfile, NotificationChannel, ServicePoint } from '../types';

interface Props {
  lang: Lang;
  onLanguageChange: (l: Lang) => void;
  onLogout: () => void;
}

/** Профиль мастера + настройки сервиса (Instagram, напоминания, язык). */
export const ProfileScreen: React.FC<Props> = ({ lang, onLanguageChange, onLogout }) => {
  const [profile, setProfile] = useState<ManagerProfile | null>(null);
  const [sp, setSp] = useState<ServicePoint | null>(null);
  const [error, setError] = useState('');

  const [name, setName] = useState('');
  const [bio, setBio] = useState('');
  const [bioUz, setBioUz] = useState('');
  const [exp, setExp] = useState('');
  const [about, setAbout] = useState('');
  const [aboutUz, setAboutUz] = useState('');
  const [instagram, setInstagram] = useState('');
  const [remindHours, setRemindHours] = useState('');
  const [leadMinutes, setLeadMinutes] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [channel, setChannel] = useState<NotificationChannel>('telegram');
  const [channelBusy, setChannelBusy] = useState(false);
  const [channelError, setChannelError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const p = await api.getProfile();
        setProfile(p);
        setName(p.name);
        setBio(p.bio);
        setBioUz(p.bio_uz);
        setChannel(p.notification_channel);
        setExp(p.experience_years != null ? String(p.experience_years) : '');
        const point = await api.getServicePoint(p.service_point);
        setSp(point);
        setAbout(point.description);
        setAboutUz(point.description_uz);
        setInstagram(point.instagram);
        setRemindHours(String(point.reminder_hours_before));
        setLeadMinutes(String(point.min_lead_minutes));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    if (!profile || !sp || saving) return;
    const hours = parseInt(remindHours, 10);
    if (Number.isNaN(hours) || hours < 1 || hours > 48) {
      setError(t(lang, 'p_remind_err'));
      return;
    }
    const lead = parseInt(leadMinutes, 10);
    if (Number.isNaN(lead) || lead < 0 || lead > 1440) {
      setError(t(lang, 'p_lead_err'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api.patchProfile({
        name,
        bio,
        bio_uz: bioUz,
        experience_years: exp === '' ? null : parseInt(exp, 10),
      });
      await api.patchServicePoint(sp.id, {
        description: about,
        description_uz: aboutUz,
        instagram: instagram.trim(),
        reminder_hours_before: hours,
        min_lead_minutes: lead,
      });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2500);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
    } finally {
      setSaving(false);
    }
  };

  const switchLanguage = async (l: Lang) => {
    if (l === lang) return;
    try {
      await api.patchProfile({ language: l });
      onLanguageChange(l); // бот и приложение теперь на одном языке
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
    }
  };

  const switchChannel = async (c: NotificationChannel) => {
    if (c === channel || channelBusy) return;
    setChannelBusy(true);
    setChannelError('');
    try {
      if (c === 'push') {
        const { token, error: pushError } = await registerForPushToken();
        if (!token) {
          setChannelError(pushError || t(lang, 'p_push_failed'));
          return;
        }
        await api.registerPushToken(token);
      }
      await api.patchProfile({ notification_channel: c });
      setChannel(c);
    } catch (e) {
      setChannelError(e instanceof ApiError ? e.message : t(lang, 'no_connection'));
    } finally {
      setChannelBusy(false);
    }
  };

  const logout = () =>
    Alert.alert(t(lang, 'p_logout_q'), '', [
      { text: t(lang, 'm_no'), style: 'cancel' },
      {
        text: t(lang, 'logout'),
        style: 'destructive',
        onPress: async () => {
          await clearTokens();
          onLogout();
        },
      },
    ]);

  if (!profile || !sp) {
    return (
      <View style={styles.center}>
        {error ? <Text style={styles.error}>{error}</Text> : <ActivityIndicator color={colors.primary} size="large" />}
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.card}>
        <Text style={styles.spName}>{profile.service_point_name}</Text>
        <Text style={styles.roleLine}>
          {profile.role === 'owner' ? t(lang, 'p_owner') : t(lang, 'p_staff')}
        </Text>
        <Text style={styles.label}>{t(lang, 'p_lang')}</Text>
        <View style={styles.langRow}>
          {(['ru', 'uz'] as const).map((l) => (
            <Pressable
              key={l}
              onPress={() => switchLanguage(l)}
              style={[styles.langBtn, lang === l && styles.langBtnActive]}
            >
              <Text style={[styles.langText, lang === l && styles.langTextActive]}>
                {l === 'ru' ? '🇷🇺 Русский' : '🇺🇿 Ўзбекча'}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t(lang, 'p_notif_title')}</Text>
        <View style={styles.langRow}>
          {(['telegram', 'push'] as const).map((c) => (
            <Pressable
              key={c}
              onPress={() => switchChannel(c)}
              disabled={channelBusy}
              style={[styles.langBtn, channel === c && styles.langBtnActive]}
            >
              <Text style={[styles.langText, channel === c && styles.langTextActive]}>
                {channelBusy && c !== channel ? '…' : t(lang, c === 'telegram' ? 'p_notif_telegram' : 'p_notif_push')}
              </Text>
            </Pressable>
          ))}
        </View>
        {!!channelError && <Text style={styles.error}>{channelError}</Text>}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t(lang, 'p_about_me')}</Text>
        <Field label={t(lang, 'm_name')} value={name} onChange={setName} maxLength={200} />
        <Field label={t(lang, 'p_bio')} value={bio} onChange={setBio} multiline />
        <Field label={t(lang, 'p_bio_uz')} value={bioUz} onChange={setBioUz} multiline />
        <Field
          label={t(lang, 'p_exp')}
          value={exp}
          onChange={setExp}
          keyboardType="number-pad"
          maxLength={2}
          narrow
        />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t(lang, 'p_sp')}</Text>
        <Field label={t(lang, 'p_desc')} value={about} onChange={setAbout} multiline />
        <Field
          label={t(lang, 'p_desc_uz')}
          value={aboutUz}
          onChange={setAboutUz}
          multiline
        />
        <Field
          label={t(lang, 'p_instagram')}
          value={instagram}
          onChange={setInstagram}
          placeholder="https://instagram.com/…"
          keyboardType="url"
        />
        <Field
          label={t(lang, 'p_remind')}
          value={remindHours}
          onChange={setRemindHours}
          keyboardType="number-pad"
          maxLength={2}
          narrow
        />
        <Field
          label={t(lang, 'p_lead')}
          value={leadMinutes}
          onChange={setLeadMinutes}
          keyboardType="number-pad"
          maxLength={4}
          narrow
        />
      </View>

      {!!error && <Text style={styles.error}>{error}</Text>}

      <Pressable style={[styles.saveBtn, saving && styles.busy]} onPress={save}>
        <Text style={styles.saveText}>
          {savedFlash ? t(lang, 'p_saved') : saving ? t(lang, 'p_saving') : t(lang, 'p_save')}
        </Text>
      </Pressable>

      <Text style={styles.note}>{t(lang, 'p_gallery_note')}</Text>

      <Pressable style={styles.logoutBtn} onPress={logout}>
        <Text style={styles.logoutText}>{t(lang, 'logout')}</Text>
      </Pressable>

      <Text style={styles.legal}>
        <Text style={styles.legalLink} onPress={() => Linking.openURL(legalUrls(lang).oferta)}>
          {t(lang, 'p_oferta')}
        </Text>{' '}
        {t(lang, 'p_legal_and')}{' '}
        <Text style={styles.legalLink} onPress={() => Linking.openURL(legalUrls(lang).privacy)}>
          {t(lang, 'p_privacy')}
        </Text>
      </Text>
    </ScrollView>
  );
};

const Field: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
  narrow?: boolean;
  maxLength?: number;
  placeholder?: string;
  keyboardType?: 'default' | 'number-pad' | 'phone-pad' | 'url';
}> = ({ label, value, onChange, multiline, narrow, maxLength, placeholder, keyboardType }) => (
  <View style={styles.field}>
    <Text style={styles.label}>{label}</Text>
    <TextInput
      style={[styles.input, multiline && styles.inputMultiline, narrow && styles.inputNarrow]}
      value={value}
      onChangeText={onChange}
      multiline={multiline}
      maxLength={maxLength}
      placeholder={placeholder}
      placeholderTextColor={colors.muted}
      keyboardType={keyboardType ?? 'default'}
      autoCapitalize={keyboardType === 'url' ? 'none' : 'sentences'}
    />
  </View>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40, gap: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 8,
    ...cardShadow,
  },
  spName: { fontSize: 18, fontWeight: '800', color: colors.text },
  roleLine: { color: colors.muted, fontSize: 13 },
  cardTitle: { fontSize: 15, fontWeight: '800', color: colors.text, marginBottom: 2 },
  field: { gap: 4 },
  label: { color: colors.muted, fontSize: 13 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 10,
    fontSize: 15,
    color: colors.text,
    backgroundColor: '#fff',
  },
  inputMultiline: { minHeight: 80, textAlignVertical: 'top' },
  inputNarrow: { width: 100 },
  saveBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius,
    paddingVertical: 15,
    alignItems: 'center',
  },
  busy: { opacity: 0.6 },
  saveText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  note: { color: colors.muted, fontSize: 12, textAlign: 'center', lineHeight: 17 },
  logoutBtn: { alignItems: 'center', paddingVertical: 12 },
  logoutText: { color: colors.danger, fontSize: 15, fontWeight: '600' },
  legal: { color: colors.muted, fontSize: 12, textAlign: 'center', marginTop: 4 },
  legalLink: { textDecorationLine: 'underline' },
  error: { color: colors.danger, fontSize: 14, textAlign: 'center' },
  langRow: { flexDirection: 'row', gap: 8, marginTop: 2 },
  langBtn: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 14,
    backgroundColor: '#fff',
  },
  langBtnActive: { borderColor: colors.primary, backgroundColor: '#eff6ff' },
  langText: { color: colors.muted, fontWeight: '600', fontSize: 14 },
  langTextActive: { color: colors.primary },
});
