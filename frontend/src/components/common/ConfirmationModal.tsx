import { useEffect, useRef, useCallback, useState } from 'react';

export interface ConfirmationModalProps {
  isOpen: boolean;
  title: string;
  description: string;
  icon?: string;
  primaryAction: string;
  secondaryAction?: string;
  onConfirm: () => void;
  onCancel: () => void;
  /** Override primary button color class. Defaults to amber/orange gradient. */
  primaryClassName?: string;
}

export default function ConfirmationModal({
  isOpen,
  title,
  description,
  icon,
  primaryAction,
  secondaryAction,
  onConfirm,
  onCancel,
  primaryClassName,
}: ConfirmationModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const primaryBtnRef = useRef<HTMLButtonElement>(null);
  const secondaryBtnRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Track mount state for enter/exit animation
  const [visible, setVisible] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);

  // --- Animation lifecycle ---
  useEffect(() => {
    if (isOpen) {
      // Save the element that had focus before modal opened
      previousFocusRef.current = document.activeElement as HTMLElement;
      setShouldRender(true);
      // Force a layout read before enabling animation
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setVisible(true);
        });
      });
    } else {
      setVisible(false);
    }
  }, [isOpen]);

  // After exit animation completes, unmount
  const handleTransitionEnd = useCallback(() => {
    if (!visible) {
      setShouldRender(false);
      // Restore focus to the triggering element
      previousFocusRef.current?.focus();
    }
  }, [visible]);

  // --- Focus trap ---
  useEffect(() => {
    if (!visible || !shouldRender) return;

    // Focus the primary button when the modal opens
    const timer = setTimeout(() => {
      primaryBtnRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
        return;
      }

      if (e.key === 'Tab') {
        const focusableElements = modalRef.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (!focusableElements || focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }

      // Enter activates primary action
      if (e.key === 'Enter' && document.activeElement !== secondaryBtnRef.current) {
        e.preventDefault();
        onConfirm();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [visible, shouldRender, onCancel, onConfirm]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (shouldRender) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [shouldRender]);

  // Click outside to close
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) {
      onCancel();
    }
  };

  if (!shouldRender) return null;

  const defaultPrimaryClass =
    'bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-white shadow-lg shadow-amber-500/25 hover:shadow-amber-500/40';

  const primaryBtnClass = primaryClassName || defaultPrimaryClass;

  return (
    <div
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby="modal-description"
      onClick={handleOverlayClick}
      onTransitionEnd={handleTransitionEnd}
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-[220ms] ease-out ${
        visible ? 'bg-black/60 backdrop-blur-sm' : 'bg-black/0'
      }`}
    >
      <div
        ref={modalRef}
        className={`relative w-full max-w-[460px] rounded-2xl border border-slate-700/50 bg-[#1E293B] p-8 shadow-2xl shadow-black/40 transition-all duration-[220ms] ease-out ${
          visible
            ? 'scale-100 opacity-100 translate-y-0'
            : 'scale-95 opacity-0 translate-y-2'
        }`}
        style={{
          boxShadow: visible
            ? '0 0 60px 0 rgba(59, 130, 246, 0.06), 0 25px 50px -12px rgba(0, 0, 0, 0.5)'
            : undefined,
        }}
      >
        {/* Subtle glow border effect */}
        <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-white/5" />

        {/* Icon */}
        {icon && (
          <div className="mb-5 flex justify-center">
            <span className="text-5xl leading-none select-none" role="img" aria-hidden="true">
              {icon}
            </span>
          </div>
        )}

        {/* Title */}
        <h2
          id="modal-title"
          className="mb-3 text-center text-xl font-bold tracking-tight text-white"
        >
          {title}
        </h2>

        {/* Description */}
        <div
          id="modal-description"
          className="mb-8 space-y-2 text-center text-sm leading-relaxed text-slate-400"
        >
          {description.split('\n').map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>

        {/* Buttons */}
        <div
          className={`flex gap-3 ${
            secondaryAction ? 'flex-row-reverse' : 'justify-center'
          }`}
        >
          {/* Primary */}
          <button
            ref={primaryBtnRef}
            type="button"
            onClick={onConfirm}
            className={`flex-1 rounded-xl px-5 py-3 text-sm font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#1E293B] focus:ring-amber-400 active:scale-[0.97] ${primaryBtnClass}`}
          >
            {primaryAction}
          </button>

          {/* Secondary */}
          {secondaryAction && (
            <button
              ref={secondaryBtnRef}
              type="button"
              onClick={onCancel}
              className="flex-1 rounded-xl border border-slate-600 bg-slate-800 px-5 py-3 text-sm font-semibold text-slate-300 transition-all duration-200 hover:border-slate-500 hover:bg-slate-700 hover:text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#1E293B] focus:ring-slate-400 active:scale-[0.97]"
            >
              {secondaryAction}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
