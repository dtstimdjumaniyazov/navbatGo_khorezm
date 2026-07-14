/** Единые цвета/отступы приложения (совпадают с фирменным синим PWA). */
export const colors = {
  primary: '#2563eb',
  primaryDark: '#1d4ed8',
  bg: '#f3f4f6',
  card: '#ffffff',
  // Раньше плоский серый (#e5e7eb) — мягкий голубой акцент вместо плоской
  // рамки, тот же приём, что и в вебе (см. frontend/src/index.css)
  border: '#dbeafe',
  text: '#111827',
  muted: '#6b7280',
  success: '#16a34a',
  danger: '#dc2626',
  warn: '#d97706',
  inProgressBg: '#eff6ff',
};

export const radius = 12;

/** Мягкая голубая тень для карточек — добавляется рядом с borderColor: colors.border. */
export const cardShadow = {
  shadowColor: '#1d4ed8',
  shadowOpacity: 0.08,
  shadowRadius: 8,
  shadowOffset: { width: 0, height: 2 },
  elevation: 2,
} as const;
