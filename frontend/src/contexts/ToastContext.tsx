import { useState, useCallback, ReactNode } from 'react';
import { ToastItem } from '../types/toast';
import { ToastContext } from './toastContextInstance';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    ({ type, title, message, duration = 4000 }: Omit<ToastItem, 'id'>) => {
      const id = `${Date.now()}-${Math.random()}`;
      setToasts((prev) => [...prev, { id, type, title, message, duration }]);

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ toasts, showToast, removeToast }}>
      {children}
      {/* Toast Notification Container */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col space-y-2 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => {
          const getToastStyles = () => {
            switch (toast.type) {
              case 'success':
                return {
                  border: 'border-emerald-200',
                  bg: 'bg-white',
                  icon: <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />,
                  title: 'text-emerald-900',
                };
              case 'error':
                return {
                  border: 'border-rose-200',
                  bg: 'bg-white',
                  icon: <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />,
                  title: 'text-rose-900',
                };
              case 'warning':
                return {
                  border: 'border-amber-200',
                  bg: 'bg-white',
                  icon: <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />,
                  title: 'text-amber-900',
                };
              case 'info':
              default:
                return {
                  border: 'border-blue-200',
                  bg: 'bg-white',
                  icon: <Info className="w-5 h-5 text-blue-600 shrink-0" />,
                  title: 'text-blue-900',
                };
            }
          };

          const styles = getToastStyles();

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto p-4 rounded-xl border ${styles.border} ${styles.bg} shadow-lg flex items-start space-x-3 transition-all animate-in fade-in slide-in-from-bottom-2 duration-200`}
            >
              {styles.icon}
              <div className="flex-1 min-w-0">
                <h4 className={`text-xs font-bold ${styles.title}`}>{toast.title}</h4>
                {toast.message && (
                  <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{toast.message}</p>
                )}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-slate-400 hover:text-slate-600 p-0.5 rounded transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};
