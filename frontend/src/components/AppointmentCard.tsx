import React from 'react';
import { Clock, Send, User, AlertTriangle } from 'lucide-react';
import { Appointment, AppointmentStatus } from '../types';
import { MINUTE_HEIGHT, formatTime, isoToMinutes } from '../utils';
import { useI18n } from '../i18n';

interface Props {
  appointment: Appointment;
  timelineStartMin: number;
  onClick: () => void;
  /** Колонка/кол-во колонок при пересечении с другими записями поста (см. layoutOverlapping) */
  col?: number;
  cols?: number;
}

// Активные статусы (scheduled/confirmed/in_progress) — синим, чтобы явно
// читались как «живая» запись рядом с отменёнными/завершёнными на том же слоте
const statusColors: Record<AppointmentStatus, string> = {
  scheduled: 'bg-blue-50 text-blue-800 border-l-4 border-l-blue-500 border-blue-200',
  confirmed: 'bg-blue-50 text-blue-800 border-l-4 border-l-blue-500 border-blue-200',
  in_progress: 'bg-yellow-50 text-yellow-800 border-l-4 border-l-yellow-500 border-yellow-200',
  done: 'bg-green-50 text-green-800 border-green-200 opacity-70',
  no_show: 'bg-red-50 text-red-800 border-red-200',
  cancelled: 'bg-transparent text-gray-400 border-dashed border-gray-300 line-through',
  rescheduled: 'bg-purple-50 text-purple-800 border-purple-200',
};

export const AppointmentCard: React.FC<Props> = ({
  appointment,
  timelineStartMin,
  onClick,
  col = 0,
  cols = 1,
}) => {
  const { t } = useI18n();
  const startMin = isoToMinutes(appointment.start_time);
  const endMin = isoToMinutes(appointment.estimated_end_time);
  const top = (startMin - timelineStartMin) * MINUTE_HEIGHT;
  const height = Math.max((endMin - startMin) * MINUTE_HEIGHT, 30);

  const isFlexible = appointment.service_type === 'flexible';
  // Пересекающиеся записи (например, отменённая осталась на слоте активной)
  // делят ширину колонки, а не полностью перекрывают друг друга
  const widthPct = 100 / cols;

  return (
    <div
      onClick={onClick}
      className={`absolute rounded-md border p-2 cursor-pointer shadow-sm hover:shadow-md transition-shadow overflow-hidden flex flex-col ${statusColors[appointment.status]}`}
      style={{
        top: `${top}px`,
        height: `${height}px`,
        left: `calc(${col * widthPct}% + ${col === 0 ? 4 : 2}px)`,
        width: `calc(${widthPct}% - ${cols === 1 ? 8 : col === cols - 1 ? 6 : 4}px)`,
        // «Рваный» низ у flexible-услуг: окончание ориентировочное (DESIGN.md, п.3)
        borderBottomStyle: isFlexible ? 'dashed' : 'solid',
        borderBottomWidth: isFlexible ? '2px' : '1px',
      }}
    >
      <div className="flex justify-between items-start mb-1">
        <div className="font-semibold text-sm leading-tight truncate pr-1">
          {appointment.client_name || t('no_name')}
          {appointment.car_details && (
            <span className="font-normal text-xs ml-1">({appointment.car_details})</span>
          )}
        </div>
        <div className="flex-shrink-0 flex items-center gap-1">
          {appointment.status === 'no_show' && <AlertTriangle className="w-3 h-3 text-red-500" />}
          {appointment.source === 'telegram' ? (
            <Send className="w-3 h-3 opacity-60" />
          ) : (
            <User className="w-3 h-3 opacity-60" />
          )}
        </div>
      </div>

      <div className="text-xs font-medium truncate mb-1">{appointment.service_name}</div>

      <div className="mt-auto flex items-center text-xs opacity-80 gap-1">
        {isFlexible && <Clock className="w-3 h-3" />}
        <span>
          {formatTime(appointment.start_time)} - {isFlexible ? '~' : ''}
          {formatTime(appointment.estimated_end_time)}
        </span>
      </div>
    </div>
  );
};
