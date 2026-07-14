import React, { useCallback, useEffect, useState } from 'react';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { Appointment, AppointmentStatus, Bay, Service, ServicePoint } from '../types';
import {
  FALLBACK_END_MIN,
  FALLBACK_START_MIN,
  isSameDay,
  timeStrToMinutes,
  toDateParam,
} from '../utils';
import { useMediaQuery } from '../hooks/useMediaQuery';
import { useI18n } from '../i18n';
import { TimelineGrid } from '../components/TimelineGrid';
import { SkeletonGrid } from '../components/SkeletonGrid';
import { SideDrawer } from '../components/SideDrawer';
import { CancelReasonModal } from '../components/CancelReasonModal';
import { NewAppointmentModal, NewAppointmentForm } from '../components/NewAppointmentModal';

interface Props {
  bays: Bay[];
  services: Service[];
  servicePoint: ServicePoint | null;
  onError: (msg: string) => void;
}

/** Вторая вкладка: обзор дня по постам (таймлайн), ручная запись. */
export const ScheduleScreen: React.FC<Props> = ({ bays, services, servicePoint, onError }) => {
  const { t, formatDate } = useI18n();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [currentDate, setCurrentDate] = useState(() => new Date());
  const [isLoading, setIsLoading] = useState(true);

  const [selectedApp, setSelectedApp] = useState<Appointment | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalPrefill, setModalPrefill] = useState<{ bayId?: string; time?: string }>({});
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);

  const isMobile = useMediaQuery('(max-width: 767px)');
  const [activeBayId, setActiveBayId] = useState<string | null>(null);

  const loadAppointments = useCallback(
    async (date: Date) => {
      setIsLoading(true);
      try {
        setAppointments(await api.getAppointments(toDateParam(date)));
      } catch (e: unknown) {
        onError(e instanceof ApiError ? e.message : t('no_connection'));
      } finally {
        setIsLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

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

  const selectedBayId = activeBayId ?? bays[0]?.id ?? null;
  const visibleBays = isMobile ? bays.filter((b) => b.id === selectedBayId) : bays;

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
      ...(service && form.durationMinutes !== service.duration_minutes
        ? { duration_minutes: form.durationMinutes }
        : {}),
      car_details: form.carDetails,
      source: 'manual',
    });
    await loadAppointments(currentDate);
  };

  const handleUpdateStatus = async (id: string, newStatus: AppointmentStatus) => {
    const updated = await api.updateAppointmentStatus(id, newStatus);
    setAppointments((prev) => prev.map((a) => (a.id === id ? updated : a)));
    setSelectedApp(updated);
  };

  const handleCancelConfirm = async (reason: string) => {
    if (!cancelTarget) return;
    const updated = await api.updateAppointmentStatus(cancelTarget.id, 'cancelled', reason);
    setAppointments((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    setCancelTarget(null);
    setIsDrawerOpen(false);
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Навигация по датам */}
      <div className="bg-white border-b px-4 py-2 flex items-center gap-3 shrink-0">
        <div className="flex items-center bg-gray-100 rounded-md p-1">
          <button
            onClick={() => shiftDate(-1)}
            className="p-1 hover:bg-white rounded transition-all text-gray-600"
            aria-label="prev"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <div className="px-3 font-medium flex items-center gap-2 min-w-[140px] justify-center text-sm">
            <CalendarIcon className="w-4 h-4 text-gray-500" />
            {formatDate(currentDate, isToday)}
          </div>
          <button
            onClick={() => shiftDate(1)}
            className="p-1 hover:bg-white rounded transition-all text-gray-600"
            aria-label="next"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
        {!isToday && (
          <button
            onClick={() => setCurrentDate(new Date())}
            className="text-sm text-blue-600 font-medium hover:underline"
          >
            {t('today')}
          </button>
        )}
      </div>

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
                {busy && <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />}
                {bay.name}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex-1 overflow-hidden relative flex">
        {isLoading || bays.length === 0 ? (
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
            onSlotClick={(bayId, time) => {
              setModalPrefill({ bayId, time });
              setIsModalOpen(true);
            }}
          />
        )}
      </div>

      {/* FAB новой записи */}
      <button
        onClick={() => {
          setModalPrefill(isMobile ? { bayId: selectedBayId ?? undefined } : {});
          setIsModalOpen(true);
        }}
        className="fixed bottom-20 right-5 z-30 w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center"
        aria-label={t('new_appointment')}
      >
        <Plus className="w-7 h-7" />
      </button>

      <SideDrawer
        isOpen={isDrawerOpen}
        appointment={selectedApp}
        onClose={() => setIsDrawerOpen(false)}
        onUpdateStatus={handleUpdateStatus}
        onCancelRequest={setCancelTarget}
      />

      <CancelReasonModal
        isOpen={!!cancelTarget}
        onClose={() => setCancelTarget(null)}
        onConfirm={handleCancelConfirm}
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
};
