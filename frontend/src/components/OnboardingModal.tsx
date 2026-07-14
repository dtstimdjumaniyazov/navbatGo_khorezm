import React from 'react';
import { X } from 'lucide-react';

interface Step {
  icon: React.ReactNode;
  title: string;
  text: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  heading: string;
  steps: Step[];
  ctaLabel: string;
}

/** Короткая инструкция «как это работает» — один раз при первом входе. */
export const OnboardingModal: React.FC<Props> = ({ isOpen, onClose, heading, steps, ctaLabel }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-5 border-b flex justify-between items-center bg-gradient-to-r from-blue-50 to-white">
          <h2 className="text-lg font-bold text-gray-900">{heading}</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded-full text-gray-500">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {steps.map((s, i) => (
            <div key={i} className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
                {s.icon}
              </div>
              <div>
                <div className="font-semibold text-gray-900 text-sm">{s.title}</div>
                <div className="text-sm text-gray-600">{s.text}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="p-4 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold shadow-sm"
          >
            {ctaLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
