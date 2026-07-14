import { StatusBar } from 'expo-status-bar';
import { CalendarPlus, CheckCircle2, ClipboardList } from 'lucide-react-native';
import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import AsyncStorage from '@react-native-async-storage/async-storage';
import { api, clearTokens, hasTokens, setOnUnauthorized } from './src/api/client';
import { ClientRoot } from './src/ClientRoot';
import { OnboardingModal } from './src/components/OnboardingModal';
import { Lang, t } from './src/i18n';
import { registerForPushToken } from './src/push';
import { LoginScreen } from './src/screens/LoginScreen';
import { NewBookingScreen } from './src/screens/NewBookingScreen';
import { ProfileScreen } from './src/screens/ProfileScreen';
import { TodayScreen } from './src/screens/TodayScreen';
import { colors } from './src/theme';
import { Me } from './src/types';

type AuthState = 'loading' | 'anon' | 'in';
type Tab = 'today' | 'new' | 'profile';

const MASTER_ONBOARD_KEY = 'navbatgo_master_onboarded';

const TAB_DEFS: { key: Tab; icon: string; labelKey: 'm_tab_today' | 'm_tab_new' | 'm_tab_profile' }[] = [
  { key: 'today', icon: '📋', labelKey: 'm_tab_today' },
  { key: 'new', icon: '➕', labelKey: 'm_tab_new' },
  { key: 'profile', icon: '👤', labelKey: 'm_tab_profile' },
];

export default function App() {
  const [auth, setAuth] = useState<AuthState>('loading');
  const [me, setMe] = useState<Me | null>(null);
  const [tab, setTab] = useState<Tab>('today');
  // Ключ пересоздаёт TodayScreen после новой записи — список сразу свежий
  const [todayKey, setTodayKey] = useState(0);
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(MASTER_ONBOARD_KEY).then((seen) => {
      if (!seen) setShowOnboarding(true);
    });
  }, []);

  const dismissOnboarding = () => {
    AsyncStorage.setItem(MASTER_ONBOARD_KEY, '1').catch(() => {});
    setShowOnboarding(false);
  };

  const loadRole = useCallback(async () => {
    try {
      setMe(await api.getMe());
    } catch {
      setMe(null); // роль не узнали — onUnauthorized разлогинит при 401
    }
  }, []);

  useEffect(() => {
    setOnUnauthorized(() => {
      setMe(null);
      setAuth('anon');
    });
    hasTokens().then((ok) => setAuth(ok ? 'in' : 'anon'));
  }, []);

  useEffect(() => {
    if (auth === 'in') loadRole();
  }, [auth, loadRole]);

  // Канал уже "push" — тихо освежаем токен на случай, если он сменился
  // (переустановка приложения, новое устройство и т.п.)
  useEffect(() => {
    if (me?.manager?.notification_channel === 'push') {
      registerForPushToken().then(({ token }) => {
        if (token) api.registerPushToken(token).catch(() => {});
      });
    }
  }, [me]);

  const logout = async () => {
    await clearTokens();
    setMe(null);
    setAuth('anon');
  };

  const isClient = me !== null && me.manager === null && me.client !== null;
  const masterLang: Lang = me?.manager?.language ?? 'ru';

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
        <StatusBar style="dark" />
        {(auth === 'loading' || (auth === 'in' && me === null)) && (
          <View style={styles.center}>
            <ActivityIndicator color={colors.primary} size="large" />
          </View>
        )}
        {auth === 'anon' && <LoginScreen onLogin={() => setAuth('in')} />}
        {auth === 'in' && me !== null && isClient && (
          <ClientRoot me={me.client} onLogout={logout} />
        )}
        {auth === 'in' && me !== null && !isClient && (
          <View style={styles.app}>
            <View style={styles.body}>
              {tab === 'today' && <TodayScreen key={todayKey} lang={masterLang} />}
              {tab === 'new' && (
                <NewBookingScreen
                  lang={masterLang}
                  onCreated={() => {
                    setTodayKey((k) => k + 1);
                    setTab('today');
                  }}
                />
              )}
              {tab === 'profile' && (
                <ProfileScreen
                  lang={masterLang}
                  onLanguageChange={(l) =>
                    setMe((prev) =>
                      prev?.manager
                        ? { ...prev, manager: { ...prev.manager, language: l } }
                        : prev,
                    )
                  }
                  onLogout={logout}
                />
              )}
            </View>
            <View style={styles.tabBar}>
              {TAB_DEFS.map((tb) => (
                <Pressable key={tb.key} style={styles.tabBtn} onPress={() => setTab(tb.key)}>
                  <Text style={styles.tabIcon}>{tb.icon}</Text>
                  <Text style={[styles.tabLabel, tab === tb.key && styles.tabLabelActive]}>
                    {t(masterLang, tb.labelKey)}
                  </Text>
                </Pressable>
              ))}
            </View>

            <OnboardingModal
              visible={showOnboarding}
              onClose={dismissOnboarding}
              heading={t(masterLang, 'm_onboard_title')}
              ctaLabel={t(masterLang, 'm_onboard_cta')}
              steps={[
                {
                  icon: <ClipboardList size={18} color={colors.primary} />,
                  title: t(masterLang, 'm_onboard_step1_title'),
                  text: t(masterLang, 'm_onboard_step1_text'),
                },
                {
                  icon: <CheckCircle2 size={18} color={colors.primary} />,
                  title: t(masterLang, 'm_onboard_step2_title'),
                  text: t(masterLang, 'm_onboard_step2_text'),
                },
                {
                  icon: <CalendarPlus size={18} color={colors.primary} />,
                  title: t(masterLang, 'm_onboard_step3_title'),
                  text: t(masterLang, 'm_onboard_step3_text'),
                },
              ]}
            />
          </View>
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  app: { flex: 1 },
  body: { flex: 1 },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  tabBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, gap: 2 },
  tabIcon: { fontSize: 20 },
  tabLabel: { fontSize: 11, color: colors.muted, fontWeight: '600' },
  tabLabelActive: { color: colors.primary },
});
