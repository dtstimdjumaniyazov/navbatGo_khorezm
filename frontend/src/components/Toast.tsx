import React, { useEffect } from 'react';
import { WifiOff, X, RefreshCw } from 'lucide-react';

interface Props {
  message: string;
  onClose: () => void;
  onRetry?: () => void;
}

/** Красный тост сверху при ошибке сети (DESIGN.md, п.5). Сам скрывается через 8 с. */
export const Toast: React.FC<Props> = ({ message, onClose, onRetry }) => {
  useEffect(() => {
    const t = setTimeout(onClose, 8000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] max-w-[calc(100vw-2rem)]">
      <div className="bg-red-600 text-white rounded-lg shadow-lg px-4 py-3 flex items-center gap-3">
        <WifiOff className="w-5 h-5 flex-shrink-0" />
        <span className="text-sm font-medium">{message}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1 bg-red-700 hover:bg-red-800 rounded px-2 py-1 text-sm flex-shrink-0"
          >
            <RefreshCw className="w-3 h-3" /> Повторить
          </button>
        )}
        <button onClick={onClose} className="p-1 hover:bg-red-700 rounded flex-shrink-0" aria-label="Закрыть">
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
