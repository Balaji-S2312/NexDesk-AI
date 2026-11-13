export type UserRole = 'employee' | 'admin';

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  email_verified?: boolean;
  email_verified_at?: string | null;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  name: string;
  email: string;
  password: string;
}

export interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<User>;
  logout: () => void;
  refreshUser?: () => Promise<void>;
  error: string | null;
  clearError: () => void;
}
