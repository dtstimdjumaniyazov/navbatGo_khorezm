import React, { useCallback, useEffect, useState } from 'react';
import { CalendarDays, CheckCircle2, Loader2, LogOut, RefreshCw, UserCircle, Wrench, Zap } from 'lucide-react';
import { api, ApiError, hasToken, MeResponse, setUnauthorizedHandler } from './api/client';
import { Bay, Service, ServicePoint } from './types';
import { useI18n } from './i18n';
import { ClientApp } from './ClientApp';
import { LoginScreen } from './components/LoginScreen';
import { OnboardingModal } from './components/OnboardingModal';
import { Toast } from './components/Toast';
import { HomeScreen } from './screens/HomeScreen';
import { ScheduleScreen } from './screens/ScheduleScreen';
import { ProfileScreen } from './screens/ProfileScreen';

type Tab = 'now' | 'schedule' | 'profile';

const MASTER_ONBOARD_KEY = 'navbatgo_master_onboarded';

export default function App() {
  const { lang, setLang, t } = useI18n();
  const [authed, setAuthed] = useState(hasToken);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [tab, setTab] = useState<Tab>('now');

  // Справочники мастера — один раз после входа
  const [bays, setBays] = useState<Bay[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [servicePoint, setServicePoint] = useState<ServicePoint | null>(null);
  const [refsError, setRefsError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(
    () => !localStorage.getItem(MASTER_ONBOARD_KEY),
  );
  const dismissOnboarding = () => {
    localStorage.setItem(MASTER_ONBOARD_KEY, '1');
    setShowOnboarding(false);
  };

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setMe(null);
      setAuthed(false);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  // Роль (мастер/клиент) — сразу после входа
  useEffect(() => {
    if (!authed) {
      setMe(null);
      return;
    }
    api
      .getMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, [authed]);

  const isClient = me !== null && me.manager === null && me.client !== null;

  const loadRefs = useCallback(() => {
    setRefsError(null);
    Promise.all([api.getBays(), api.getServices(), api.getServicePoint()])
      .then(([baysData, servicesData, sp]) => {
        setBays(baysData);
        setServices(servicesData);
        setServicePoint(sp);
      })
      .catch((e: unknown) => {
        setRefsError(e instanceof ApiError ? e.message : t('loading_error'));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Справочники (/api/bays/ и т.д.) доступны только мастерам
    if (authed && me !== null && !isClient) loadRefs();
  }, [authed, me, isClient, loadRefs]);

  if (!authed) {
    return <LoginScreen onSuccess={() => setAuthed(true)} />;
  }

  if (me === null) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-100 text-blue-600">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  if (isClient) {
    return (
      <ClientApp
        me={me.client!}
        onLogout={() => {
          api.logout();
          setMe(null);
          setAuthed(false);
        }}
      />
    );
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'now', label: t('tab_now'), icon: <Zap className="w-5 h-5" /> },
    { id: 'schedule', label: t('tab_schedule'), icon: <CalendarDays className="w-5 h-5" /> },
    { id: 'profile', label: t('tab_profile'), icon: <UserCircle className="w-5 h-5" /> },
  ];

  return (
    <div className="h-screen flex flex-col bg-gray-100 overflow-hidden font-sans text-gray-900">
      {/* Верхняя панель */}
      <header className="bg-white border-b px-4 py-2.5 flex items-center justify-between shrink-0 shadow-sm z-20 gap-2">
        <button
          onClick={() => setTab('now')}
          className="flex items-center gap-2 text-blue-700 font-bold text-lg min-w-0"
        >
          <Wrench className="w-5 h-5 shrink-0" />
          <span className="truncate">{servicePoint?.name ?? t('panel_title')}</span>
        </button>
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center bg-gray-100 rounded-md p-0.5 text-sm font-medium">
            {(['ru', 'uz'] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-2 py-1 rounded ${
                  lang === l ? 'bg-white shadow-sm text-blue-700' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {l === 'ru' ? 'РУ' : 'ЎЗ'}
              </button>
            ))}
          </div>
          <button
            onClick={() => {
              api.logout();
              setAuthed(false);
            }}
            title={t('logout')}
            aria-label={t('logout')}
            className="p-2 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-md"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Содержимое вкладки */}
      <main className="flex-1 overflow-hidden flex flex-col">
        {refsError ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-gray-600">
            <p className="text-red-600 font-medium">{refsError}</p>
            <button
              onClick={loadRefs}
              className="flex items-center gap-2 px-4 py-2 bg-white border rounded-md hover:bg-gray-50"
            >
              <RefreshCw className="w-4 h-4" /> {t('retry')}
            </button>
          </div>
        ) : (
          <>
            {tab === 'now' && <HomeScreen onError={setToast} />}
            {tab === 'schedule' && (
              <ScheduleScreen
                bays={bays}
                services={services}
                servicePoint={servicePoint}
                onError={setToast}
              />
            )}
            {tab === 'profile' && (
              <ProfileScreen
                onError={setToast}
                servicePoint={servicePoint}
                onServicePointSaved={(patch) =>
                  setServicePoint((sp) => (sp ? { ...sp, ...patch } : sp))
                }
              />
            )}
          </>
        )}
      </main>

      {/* Нижние вкладки */}
      <nav className="bg-white border-t flex shrink-0 z-20 pb-[env(safe-area-inset-bottom)]">
        {tabs.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 py-2 flex flex-col items-center gap-0.5 text-xs font-medium ${
              tab === id ? 'text-blue-600' : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            {icon}
            {label}
          </button>
        ))}
      </nav>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}

      <OnboardingModal
        isOpen={showOnboarding}
        onClose={dismissOnboarding}
        heading={t('master_onboard_title')}
        ctaLabel={t('master_onboard_cta')}
        steps={[
          { icon: <Zap className="w-5 h-5" />, title: t('master_onboard_step1_title'), text: t('master_onboard_step1_text') },
          { icon: <CheckCircle2 className="w-5 h-5" />, title: t('master_onboard_step2_title'), text: t('master_onboard_step2_text') },
          { icon: <CalendarDays className="w-5 h-5" />, title: t('master_onboard_step3_title'), text: t('master_onboard_step3_text') },
        ]}
      />
    </div>
  );
}
