import { createContext } from 'react';
import { ToastContextType } from '../types/toast';

export const ToastContext = createContext<ToastContextType | undefined>(undefined);
