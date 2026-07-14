import AsyncStorage from '@react-native-async-storage/async-storage';
import { Bell, Calendar, CalendarDays, Settings, Wrench } from 'lucide-react-native';
import React, { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { api } from './api/client';
import { OnboardingModal } from './components/OnboardingModal';
import { Lang, LANG_STORAGE_KEY, t } from './i18n';
import { registerForPushToken } from './push';
import { CatalogScreen } from './screens/client/CatalogScreen';
import { MyBookingsScreen } from './screens/client/MyBookingsScreen';
import { PointScreen } from './screens/client/PointScreen';
import { SettingsScreen } from './screens/client/SettingsScreen';
import { colors } from './theme';
import { ClientInfo, PublicPoint } from './types';

const ONBOARD_KEY = 'navbatgo_client_onboarded';

interface Props {
  me: ClientInfo | null;
  onLogout: () => void;
}

type Tab = 'catalog' | 'my' | 'settings';

/** Клиентский режим: каталог сервисов (с витриной и записью) + мои записи. */
export const ClientRoot: React.FC<Props> = ({ me, onLogout }) => {
  const [tab, setTab] = useState<Tab>('catalog');
  const [point, setPoint] = useState<PublicPoint | null>(null);
  // Язык: локальный выбор в приложении > язык из бота > русский
  const [lang, setLangState] = useState<Lang>(me?.language ?? 'ru');
  // Пересоздаёт «Мои записи» после новой брони — список сразу свежий
  const [myKey, setMyKey] = useState(0);
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(LANG_STORAGE_KEY).then((saved) => {
      if (saved === 'ru' || saved === 'uz') setLangState(saved);
    });
    AsyncStorage.getItem(ONBOARD_KEY).then((seen) => {
      if (!seen) setShowOnboarding(true);
    });
  }, []);

  const dismissOnboarding = () => {
    AsyncStorage.setItem(ONBOARD_KEY, '1').catch(() => {});
    setShowOnboarding(false);
  };

  // Канал уже "push" — тихо освежаем токен на случай, если он сменился
  // (переустановка приложения, новое устройство и т.п.)
  useEffect(() => {
    if (me?.notification_channel === 'push') {
      registerForPushToken().then(({ token }) => {
        if (token) api.registerPushToken(token).catch(() => {});
      });
    }
  }, [me]);

  const setLang = (l: Lang) => {
    setLangState(l);
    AsyncStorage.setItem(LANG_STORAGE_KEY, l).catch(() => {});
  };

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Pressable
          style={styles.brandRow}
          onPress={() => {
            setPoint(null);
            setTab('catalog');
          }}
          hitSlop={8}
        >
          <Wrench size={18} color={colors.primary} />
          <Text style={styles.brand}>NavbatGo</Text>
        </Pressable>
        <View style={styles.headerRight}>
          <View style={styles.langBox}>
            {(['ru', 'uz'] as const).map((l) => (
              <Pressable
                key={l}
                onPress={() => setLang(l)}
                style={[styles.langBtn, lang === l && styles.langBtnActive]}
              >
                <Text style={[styles.langText, lang === l && styles.langTextActive]}>
                  {l === 'ru' ? 'РУ' : 'ЎЗ'}
                </Text>
              </Pressable>
            ))}
          </View>
          <Pressable onPress={onLogout} hitSlop={8}>
            <Text style={styles.logout}>{t(lang, 'logout')}</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.body}>
        {tab === 'catalog' &&
          (point ? (
            <PointScreen
              point={point}
              me={me}
              lang={lang}
              onBack={() => setPoint(null)}
              onBooked={() => {
                setPoint(null);
                setMyKey((k) => k + 1);
                setTab('my');
              }}
            />
          ) : (
            <CatalogScreen lang={lang} onSelect={setPoint} />
          ))}
        {tab === 'my' && <MyBookingsScreen key={myKey} lang={lang} />}
        {tab === 'settings' && <SettingsScreen lang={lang} />}
      </View>

      <View style={styles.tabBar}>
        <Pressable style={styles.tabBtn} onPress={() => setTab('catalog')}>
          <Wrench size={20} color={tab === 'catalog' ? colors.primary : colors.muted} />
          <Text style={[styles.tabLabel, tab === 'catalog' && styles.tabLabelActive]}>
            {t(lang, 'tab_catalog')}
          </Text>
        </Pressable>
        <Pressable style={styles.tabBtn} onPress={() => setTab('my')}>
          <CalendarDays size={20} color={tab === 'my' ? colors.primary : colors.muted} />
          <Text style={[styles.tabLabel, tab === 'my' && styles.tabLabelActive]}>
            {t(lang, 'tab_my')}
          </Text>
        </Pressable>
        <Pressable style={styles.tabBtn} onPress={() => setTab('settings')}>
          <Settings size={20} color={tab === 'settings' ? colors.primary : colors.muted} />
          <Text style={[styles.tabLabel, tab === 'settings' && styles.tabLabelActive]}>
            {t(lang, 'tab_settings')}
          </Text>
        </Pressable>
      </View>

      <OnboardingModal
        visible={showOnboarding}
        onClose={dismissOnboarding}
        heading={t(lang, 'onboard_title')}
        ctaLabel={t(lang, 'onboard_cta')}
        steps={[
          {
            icon: <Wrench size={18} color={colors.primary} />,
            title: t(lang, 'onboard_step1_title'),
            text: t(lang, 'onboard_step1_text'),
          },
          {
            icon: <Calendar size={18} color={colors.primary} />,
            title: t(lang, 'onboard_step2_title'),
            text: t(lang, 'onboard_step2_text'),
          },
          {
            icon: <Bell size={18} color={colors.primary} />,
            title: t(lang, 'onboard_step3_title'),
            text: t(lang, 'onboard_step3_text'),
          },
        ]}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  root: { flex: 1 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: colors.card,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  brand: { fontWeight: '800', fontSize: 17, color: colors.primary },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  langBox: {
    flexDirection: 'row',
    backgroundColor: colors.bg,
    borderRadius: 8,
    padding: 2,
  },
  langBtn: { paddingVertical: 4, paddingHorizontal: 8, borderRadius: 6 },
  langBtnActive: { backgroundColor: colors.card },
  langText: { fontSize: 13, fontWeight: '600', color: colors.muted },
  langTextActive: { color: colors.primary },
  logout: { color: colors.muted, fontSize: 14 },
  body: { flex: 1 },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  tabBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, gap: 2 },
  tabLabel: { fontSize: 11, color: colors.muted, fontWeight: '600' },
  tabLabelActive: { color: colors.primary },
});
