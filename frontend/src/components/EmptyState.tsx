import React from 'react';

interface Props {
  icon: React.ReactNode;
  message: string;
  className?: string;
}

/** Единый стиль пустых состояний: мягкая тень и голубой акцент вместо плоской серой рамки. */
export const EmptyState: React.FC<Props> = ({ icon, message, className = '' }) => (
  <div
    className={`flex flex-col items-center justify-center gap-2 text-center bg-blue-50/60 rounded-2xl shadow-sm ring-1 ring-blue-100 py-8 px-4 ${className}`}
  >
    <div className="w-10 h-10 rounded-full bg-white shadow-sm flex items-center justify-center text-blue-400">
      {icon}
    </div>
    <p className="text-gray-500 text-sm">{message}</p>
  </div>
);
