import React from 'react';

/** Скелетный экран при загрузке дня (DESIGN.md, п.5): серые мерцающие
 *  блоки на местах карточек, чтобы вёрстка не прыгала. */
export const SkeletonGrid: React.FC<{ columns: number }> = ({ columns }) => {
  const cols = Math.max(columns, 2);
  return (
    <div className="flex-1 overflow-hidden bg-gray-50 flex">
      {/* Ось времени */}
      <div className="w-16 flex-shrink-0 border-r bg-white">
        <div className="h-12 border-b bg-gray-100" />
        <div className="p-2 space-y-14">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-3 bg-gray-200 rounded animate-pulse" />
          ))}
        </div>
      </div>
      {/* Колонки постов */}
      {Array.from({ length: cols }).map((_, col) => (
        <div key={col} className="flex-1 min-w-[200px] border-r bg-white">
          <div className="h-12 border-b bg-gray-100 flex items-center justify-center">
            <div className="h-4 w-24 bg-gray-200 rounded animate-pulse" />
          </div>
          <div className="p-2 space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="bg-gray-100 rounded-md animate-pulse"
                style={{ height: 60 + ((col + i) % 3) * 30, animationDelay: `${(col + i) * 120}ms` }}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
