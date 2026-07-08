import React, { useState, useEffect, useRef } from 'react';
import { MINUTE_HEIGHT, generateTimeSlots, timeStrToMinutes } from '../utils';
import { Appointment, Bay } from '../types';
import { AppointmentCard } from './AppointmentCard';
import { useI18n } from '../i18n';

interface Props {
  bays: Bay[];
  appointments: Appointment[];
  workStartMin: number; // минуты от полуночи, из ServicePoint
  workEndMin: number;
  showNowLine: boolean; // красная линия — только при просмотре сегодняшнего дня
  onAppointmentClick: (appointment: Appointment) => void;
  onSlotClick: (bayId: string, timeStr: string) => void;
}

export const TimelineGrid: React.FC<Props> = ({
  bays,
  appointments,
  workStartMin,
  workEndMin,
  showNowLine,
  onAppointmentClick,
  onSlotClick,
}) => {
  const { t } = useI18n();
  const timeSlots = generateTimeSlots(workStartMin, workEndMin);
  const [nowMinutes, setNowMinutes] = useState(() => {
    const now = new Date();
    return now.getHours() * 60 + now.getMinutes();
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const totalHeight = (workEndMin - workStartMin) * MINUTE_HEIGHT;

  useEffect(() => {
    // Автоскролл к «сейчас» при открытии (DESIGN.md, п.7.4)
    if (containerRef.current && showNowLine) {
      containerRef.current.scrollTop = (nowMinutes - workStartMin) * MINUTE_HEIGHT - 100;
    }
    const interval = setInterval(() => {
      const now = new Date();
      setNowMinutes(now.getHours() * 60 + now.getMinutes());
    }, 60_000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showNowLine, workStartMin]);

  const nowOffset = (nowMinutes - workStartMin) * MINUTE_HEIGHT;
  const nowVisible = showNowLine && nowMinutes > workStartMin && nowMinutes < workEndMin;

  return (
    <div className="flex-1 overflow-auto bg-gray-50 flex flex-col" ref={containerRef}>
      <div className="inline-flex min-w-full">
        {/* Ось времени */}
        <div className="w-16 flex-shrink-0 border-r bg-white sticky left-0 z-20">
          <div className="h-12 border-b bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-500 sticky top-0 z-30">
            {t('time')}
          </div>
          <div className="relative" style={{ height: totalHeight }}>
            {timeSlots.map((time) => {
              const top = (timeStrToMinutes(time) - workStartMin) * MINUTE_HEIGHT;
              const isHour = time.endsWith(':00');
              return (
                <div
                  key={time}
                  className={`absolute w-full text-right pr-2 text-xs ${isHour ? 'font-medium text-gray-500' : 'text-gray-400'}`}
                  style={{ top: top - 8 }}
                >
                  {time}
                </div>
              );
            })}
          </div>
        </div>

        {/* Колонки постов */}
        {bays.map((bay) => {
          const bayAppointments = appointments.filter((a) => a.bay === bay.id);

          return (
            <div key={bay.id} className="flex-1 min-w-[250px] border-r bg-white relative">
              <div className="h-12 border-b bg-gray-100 flex items-center justify-center text-sm font-semibold text-gray-800 sticky top-0 z-10 shadow-sm">
                {bay.name}
              </div>

              <div className="relative" style={{ height: totalHeight }}>
                {/* Горизонтальные линии сетки */}
                {timeSlots.map((time) => {
                  const top = (timeStrToMinutes(time) - workStartMin) * MINUTE_HEIGHT;
                  const isHour = time.endsWith(':00');
                  return (
                    <div
                      key={time}
                      className={`absolute w-full border-t ${isHour ? 'border-gray-200' : 'border-gray-100 border-dashed'}`}
                      style={{ top }}
                    />
                  );
                })}

                {/* Кликабельные пустые слоты */}
                {timeSlots.slice(0, -1).map((time) => {
                  const top = (timeStrToMinutes(time) - workStartMin) * MINUTE_HEIGHT;
                  return (
                    <div
                      key={`slot-${time}`}
                      className="absolute w-full hover:bg-blue-50/50 cursor-pointer opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center z-0"
                      style={{ top, height: 30 * MINUTE_HEIGHT }}
                      onClick={() => onSlotClick(bay.id, time)}
                    >
                      <span className="text-blue-600 text-xs font-medium bg-blue-100 px-2 py-1 rounded shadow-sm">
                        {t('add_slot')}
                      </span>
                    </div>
                  );
                })}

                {/* Красная линия текущего времени */}
                {nowVisible && (
                  <div
                    className="absolute w-full border-t-2 border-red-500 z-10 pointer-events-none"
                    style={{ top: nowOffset }}
                  >
                    <div className="absolute w-2 h-2 bg-red-500 rounded-full -left-1 -top-[5px]" />
                  </div>
                )}

                {/* Карточки записей */}
                {bayAppointments.map((app) => (
                  <AppointmentCard
                    key={app.id}
                    appointment={app}
                    timelineStartMin={workStartMin}
                    onClick={() => onAppointmentClick(app)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
