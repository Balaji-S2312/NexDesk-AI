import { createContext } from 'react';

export type ThemePreference = 'light' | 'dark' | 'night' | 'auto';
export type ResolvedTheme = 'light' | 'dark' | 'night';

export interface ThemeContextType {
  theme: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemePreference) => void;
  isAuto: boolean;
}

export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
