import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { jwtDecode } from 'jwt-decode';
import toast from 'react-hot-toast';
import { authAPI } from '../services/api';

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  status: string;
  is_verified: boolean;
  experience_level: string;
  country?: string;
  created_at: string;
  last_login?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface RegisterData {
  email: string;
  password: string;
  confirm_password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  country?: string;
  experience_level?: string;
  terms_accepted: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

interface AuthState {
  // State
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<boolean>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
  checkTokenExpiry: () => boolean;
  getAuthHeader: () => string | null;
}

const TOKEN_REFRESH_THRESHOLD = 5 * 60 * 1000; // 5 minutes in milliseconds

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial State
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Login Action
      login: async (credentials: LoginCredentials) => {
        set({ isLoading: true, error: null });

        try {
          const response = await authAPI.login(credentials);

          const { user, tokens } = response.data;

          set({
            user,
            tokens,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          toast.success(`Welcome back, ${user.first_name}!`);
        } catch (error: any) {
          const errorMessage = error.response?.data?.error?.message || 'Login failed';

          set({
            user: null,
            tokens: null,
            isAuthenticated: false,
            isLoading: false,
            error: errorMessage,
          });

          toast.error(errorMessage);
          throw error;
        }
      },

      // Register Action
      register: async (data: RegisterData) => {
        set({ isLoading: true, error: null });

        try {
          const response = await authAPI.register(data);

          const { user, tokens } = response.data;

          set({
            user,
            tokens,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          toast.success(`Welcome to TradeSense AI, ${user.first_name}!`);
        } catch (error: any) {
          const errorMessage = error.response?.data?.error?.message || 'Registration failed';

          set({
            user: null,
            tokens: null,
            isAuthenticated: false,
            isLoading: false,
            error: errorMessage,
          });

          toast.error(errorMessage);
          throw error;
        }
      },

      // Logout Action
      logout: () => {
        const state = get();

        // Call logout API if authenticated
        if (state.isAuthenticated && state.tokens) {
          authAPI.logout().catch(console.error);
        }

        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });

        toast.success('Logged out successfully');
      },

      // Refresh Token Action
      refreshToken: async (): Promise<boolean> => {
        const state = get();

        if (!state.tokens?.refresh_token) {
          return false;
        }

        try {
          const response = await authAPI.refreshToken(state.tokens.refresh_token);

          const { access_token, expires_in } = response.data;

          set({
            tokens: {
              ...state.tokens,
              access_token,
              expires_in,
            },
            error: null,
          });

          return true;
        } catch (error) {
          console.error('Token refresh failed:', error);

          // If refresh fails, logout user
          get().logout();
          return false;
        }
      },

      // Update Profile Action
      updateProfile: async (data: Partial<User>) => {
        set({ isLoading: true, error: null });

        try {
          const response = await authAPI.updateProfile(data);

          const { user } = response.data;

          set({
            user,
            isLoading: false,
            error: null,
          });

          toast.success('Profile updated successfully');
        } catch (error: any) {
          const errorMessage = error.response?.data?.error?.message || 'Profile update failed';

          set({
            isLoading: false,
            error: errorMessage,
          });

          toast.error(errorMessage);
          throw error;
        }
      },

      // Change Password Action
      changePassword: async (currentPassword: string, newPassword: string) => {
        set({ isLoading: true, error: null });

        try {
          await authAPI.changePassword({
            current_password: currentPassword,
            new_password: newPassword,
            confirm_password: newPassword,
          });

          set({
            isLoading: false,
            error: null,
          });

          toast.success('Password changed successfully');
        } catch (error: any) {
          const errorMessage = error.response?.data?.error?.message || 'Password change failed';

          set({
            isLoading: false,
            error: errorMessage,
          });

          toast.error(errorMessage);
          throw error;
        }
      },

      // Clear Error Action
      clearError: () => {
        set({ error: null });
      },

      // Set Loading Action
      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },

      // Check Token Expiry
      checkTokenExpiry: (): boolean => {
        const state = get();

        if (!state.tokens?.access_token) {
          return false;
        }

        try {
          const decoded: any = jwtDecode(state.tokens.access_token);
          const currentTime = Date.now() / 1000;

          // Check if token will expire within the threshold
          return decoded.exp - currentTime < TOKEN_REFRESH_THRESHOLD / 1000;
        } catch (error) {
          console.error('Failed to decode token:', error);
          return true; // Assume expired if decode fails
        }
      },

      // Get Authorization Header
      getAuthHeader: (): string | null => {
        const state = get();

        if (state.tokens?.access_token) {
          return `Bearer ${state.tokens.access_token}`;
        }

        return null;
      },
    }),
    {
      name: 'tradesense-auth', // Key for localStorage
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Auto refresh token on store initialization
const initializeAuth = () => {
  const state = useAuthStore.getState();

  if (state.isAuthenticated && state.checkTokenExpiry()) {
    state.refreshToken();
  }
};

// Initialize on store creation
initializeAuth();

// Set up automatic token refresh
setInterval(() => {
  const state = useAuthStore.getState();

  if (state.isAuthenticated && state.checkTokenExpiry()) {
    state.refreshToken();
  }
}, 60000); // Check every minute

export default useAuthStore;
