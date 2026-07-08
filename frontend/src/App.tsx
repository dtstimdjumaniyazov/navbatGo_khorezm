import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, Plus, Wrench, RefreshCw } from 'lucide-react';
import { api, ApiError } from './api/client';
import { Appointment, AppointmentStatus, Bay, Service, ServicePoint } from './types';
import {
  FALLBACK_END_MIN,
  FALLBACK_START_MIN,
  isSameDay,
  timeStrToMinutes,
  toDateParam,
} from './utils';
import { useMediaQuery } from './hooks/useMediaQuery';
import { useI18n } from './i18n';
import { TimelineGrid } from './components/TimelineGrid';
import { SkeletonGrid } from './components/SkeletonGrid';
import { Toast } from './components/Toast';
import { SideDrawer } from './components/SideDrawer';
import { NewAppointmentModal, NewAppointmentForm } from './components/NewAppointmentModal';

export default function App() {
  const { lang, setLang, t, formatDate } = useI18n();
  // Справочники: грузятся один раз
  const [bays, setBays] = useState<Bay[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [servicePoint, setServicePoint] = useState<ServicePoint | null>(null);
  const [refsError, setRefsError] = useState<string | null>(null);

  // Записи выбранного дня
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [currentDate, setCurrentDate] = useState(() => new Date());
  const [isLoading, setIsLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);

  const [selectedApp, setSelectedApp] = useState<Appointment | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalPrefill, setModalPrefill] = useState<{ bayId?: string; time?: string }>({});

  // Мобильный вид: посты табами, а не колонками (DESIGN.md, п.6)
  const isMobile = useMediaQuery('(max-width: 767px)');
  const [activeBayId, setActiveBayId] = useState<string | null>(null);

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

  useEffect(loadRefs, [loadRefs]);

  // Записи дня: при ошибке сети показываем тост, но не стираем уже загруженное
  const loadAppointments = useCallback(async (date: Date) => {
    setIsLoading(true);
    try {
      setAppointments(await api.getAppointments(toDateParam(date)));
      setToast(null);
    } catch (e: unknown) {
      setToast(e instanceof ApiError ? e.message : t('no_connection'));
    } finally {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadAppointments(currentDate);
  }, [currentDate, loadAppointments]);

  const shiftDate = (days: number) => {
    setCurrentDate((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() + days);
      return next;
    });
  };

  const isToday = isSameDay(currentDate, new Date());
  const workStartMin = servicePoint ? timeStrToMinutes(servicePoint.work_start) : FALLBACK_START_MIN;
  const workEndMin = servicePoint ? timeStrToMinutes(servicePoint.work_end) : FALLBACK_END_MIN;

  const inProgressCount = useMemo(
    () => appointments.filter((a) => a.status === 'in_progress').length,
    [appointments],
  );

  // На мобильном показываем один выбранный пост
  const selectedBayId = activeBayId ?? bays[0]?.id ?? null;
  const visibleBays = isMobile ? bays.filter((b) => b.id === selectedBayId) : bays;

  const handleSlotClick = (bayId: string, time: string) => {
    setModalPrefill({ bayId, time });
    setIsModalOpen(true);
  };

  // POST /appointments/: ошибки (409 «пост занят» и пр.) пробрасываются
  // в модалку — она покажет их и останется открытой
  const handleCreateAppointment = async (form: NewAppointmentForm) => {
    const [h, m] = form.startTime.split(':').map(Number);
    const start = new Date(currentDate);
    start.setHours(h, m, 0, 0);
    const service = services.find((s) => s.id === form.serviceId);
    await api.createAppointment({
      client_name: form.clientName,
      client_phone: form.phone,
      service: form.serviceId,
      bay: form.bayId,
      start_time: start.toISOString(),
      // Шлём длительность, только если мастер изменил стандартную
      ...(service && form.durationMinutes !== service.duration_minutes
        ? { duration_minutes: form.durationMinutes }
        : {}),
      car_details: form.carDetails,
      source: 'manual',
    });
    await loadAppointments(currentDate);
  };

  // PATCH статуса: сервер применяет переход через сервисный слой
  // (no_show инкрементирует счётчик неявок, in_progress/done ставят actual_*)
  const handleUpdateStatus = async (id: string, newStatus: AppointmentStatus) => {
    const updated = await api.updateAppointmentStatus(id, newStatus);
    setAppointments((prev) => prev.map((a) => (a.id === id ? updated : a)));
    setSelectedApp(updated);
  };

  const dateLabel = formatDate(currentDate, isToday);

  return (
    <div className="h-screen flex flex-col bg-gray-100 overflow-hidden font-sans text-gray-900">
      {/* Header */}
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between shrink-0 shadow-sm z-20 gap-2">
        <div className="flex items-center gap-3 md:gap-6 min-w-0">
          <div className="hidden md:flex items-center gap-2 text-blue-700 font-bold text-xl whitespace-nowrap">
            <Wrench className="w-6 h-6" />
            <span>{servicePoint?.name ?? t('panel_title')}</span>
          </div>

          <div className="flex items-center bg-gray-100 rounded-md p-1">
            <button
              onClick={() => shiftDate(-1)}
              className="p-1 hover:bg-white rounded hover:shadow-sm transition-all text-gray-600"
              aria-label="Предыдущий день"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="px-2 md:px-4 font-medium flex items-center gap-2 min-w-[130px] md:min-w-[160px] justify-center text-sm md:text-base">
              <CalendarIcon className="w-4 h-4 text-gray-500 hidden sm:block" />
              {dateLabel}
            </div>
            <button
              onClick={() => shiftDate(1)}
              className="p-1 hover:bg-white rounded hover:shadow-sm transition-all text-gray-600"
              aria-label="Следующий день"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          {!isToday && (
            <button
              onClick={() => setCurrentDate(new Date())}
              className="text-sm text-blue-600 font-medium hover:underline whitespace-nowrap"
            >
              {t('today')}
            </button>
          )}
        </div>

        <div className="flex items-center gap-4">
          {/* Переключатель языка панели */}
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

          <div className="hidden md:block text-sm font-medium whitespace-nowrap">
            <span className="text-gray-500 mr-2">{t('in_progress_count')}</span>
            <span className="bg-yellow-100 text-yellow-800 px-2 py-1 rounded-full">
              {inProgressCount}
            </span>
          </div>

          {/* На мобильном вместо этой кнопки — FAB внизу */}
          <button
            onClick={() => {
              setModalPrefill({});
              setIsModalOpen(true);
            }}
            className="hidden md:flex bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium items-center gap-2 transition-colors shadow-sm whitespace-nowrap"
          >
            <Plus className="w-5 h-5" /> {t('new_appointment')}
          </button>
        </div>
      </header>

      {/* Мобильные табы постов */}
      {isMobile && bays.length > 0 && (
        <div className="bg-white border-b flex overflow-x-auto shrink-0">
          {bays.map((bay) => {
            const busy = appointments.some(
              (a) => a.bay === bay.id && a.status === 'in_progress',
            );
            const active = bay.id === selectedBayId;
            return (
              <button
                key={bay.id}
                onClick={() => setActiveBayId(bay.id)}
                className={`flex-1 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 flex items-center justify-center gap-1.5 ${
                  active
                    ? 'border-blue-600 text-blue-700 bg-blue-50/50'
                    : 'border-transparent text-gray-600'
                }`}
              >
                {/* Красная точка — на посту сейчас идёт работа (DESIGN.md, п.6) */}
                {busy && <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />}
                {bay.name}
              </button>
            );
          })}
        </div>
      )}

      {/* Main Workspace */}
      <main className="flex-1 overflow-hidden relative flex">
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
        ) : isLoading || bays.length === 0 ? (
          <SkeletonGrid columns={isMobile ? 1 : bays.length || 2} />
        ) : (
          <TimelineGrid
            bays={visibleBays}
            appointments={appointments}
            workStartMin={workStartMin}
            workEndMin={workEndMin}
            showNowLine={isToday}
            onAppointmentClick={(app) => {
              setSelectedApp(app);
              setIsDrawerOpen(true);
            }}
            onSlotClick={handleSlotClick}
          />
        )}
      </main>

      {/* FAB на мобильном (DESIGN.md, п.6) */}
      {isMobile && !refsError && (
        <button
          onClick={() => {
            setModalPrefill({ bayId: selectedBayId ?? undefined });
            setIsModalOpen(true);
          }}
          className="fixed bottom-5 right-5 z-30 w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center"
          aria-label="Новая запись"
        >
          <Plus className="w-7 h-7" />
        </button>
      )}

      {toast && (
        <Toast
          message={toast}
          onClose={() => setToast(null)}
          onRetry={() => loadAppointments(currentDate)}
        />
      )}

      <SideDrawer
        isOpen={isDrawerOpen}
        appointment={selectedApp}
        onClose={() => setIsDrawerOpen(false)}
        onUpdateStatus={handleUpdateStatus}
      />

      <NewAppointmentModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        bays={bays}
        services={services}
        prefilledBayId={modalPrefill.bayId}
        prefilledTime={modalPrefill.time}
        onSave={handleCreateAppointment}
      />
    </div>
  );
}
