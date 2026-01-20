import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from "axios";
import toast from "react-hot-toast";

// Base API configuration
const API_BASE_URL =
  process.env.REACT_APP_API_URL || "http://localhost:5000/api/v1";
const API_TIMEOUT = 30000; // 30 seconds

// Create axios instance with default configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config: any) => {
    // Get token from localStorage
    const authData = localStorage.getItem("tradesense-auth");
    if (authData) {
      try {
        const { state } = JSON.parse(authData);
        if (state?.tokens?.access_token) {
          config.headers.Authorization = `Bearer ${state.tokens.access_token}`;
        }
      } catch (error) {
        console.error("Failed to parse auth data:", error);
      }
    }

    // Add request timestamp
    config.metadata = { startTime: Date.now() };

    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Log response time in development
    if (process.env.NODE_ENV === "development") {
      const duration = Date.now() - response.config.metadata?.startTime;
      console.log(
        `API Response: ${response.config.method?.toUpperCase()} ${response.config.url} - ${response.status} (${duration}ms)`,
      );
    }

    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // Handle network errors
    if (!error.response) {
      toast.error("Network error. Please check your connection.");
      return Promise.reject(error);
    }

    const { status, data } = error.response;

    // Handle token expiration
    if (status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Try to refresh token
        const authData = localStorage.getItem("tradesense-auth");
        if (authData) {
          const { state } = JSON.parse(authData);
          if (state?.tokens?.refresh_token) {
            const refreshResponse = await axios.post(
              `${API_BASE_URL}/auth/refresh`,
              {},
              {
                headers: {
                  Authorization: `Bearer ${state.tokens.refresh_token}`,
                },
              },
            );

            // Update stored tokens
            const newTokens = {
              ...state.tokens,
              access_token: refreshResponse.data.access_token,
            };

            const updatedAuthData = {
              ...JSON.parse(authData),
              state: {
                ...state,
                tokens: newTokens,
              },
            };

            localStorage.setItem(
              "tradesense-auth",
              JSON.stringify(updatedAuthData),
            );

            // Retry original request with new token
            originalRequest.headers.Authorization = `Bearer ${refreshResponse.data.access_token}`;
            return apiClient(originalRequest);
          }
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem("tradesense-auth");
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }

    // Handle other HTTP errors
    switch (status) {
      case 400:
        toast.error(data?.error?.message || "Bad request");
        break;
      case 403:
        toast.error("Access denied");
        break;
      case 404:
        toast.error("Resource not found");
        break;
      case 429:
        toast.error("Too many requests. Please try again later.");
        break;
      case 500:
        toast.error("Server error. Please try again later.");
        break;
      default:
        toast.error(data?.error?.message || "An error occurred");
    }

    return Promise.reject(error);
  },
);

// Generic API methods
export const api = {
  get: <T = any>(
    url: string,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> => apiClient.get(url, config),

  post: <T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> => apiClient.post(url, data, config),

  put: <T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> => apiClient.put(url, data, config),

  patch: <T = any>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> => apiClient.patch(url, data, config),

  delete: <T = any>(
    url: string,
    config?: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> => apiClient.delete(url, config),
};

// Authentication API
export const authAPI = {
  login: (credentials: {
    email: string;
    password: string;
    remember_me?: boolean;
  }) => api.post("/auth/login", credentials),

  register: (userData: {
    email: string;
    password: string;
    confirm_password: string;
    first_name: string;
    last_name: string;
    phone?: string;
    country?: string;
    experience_level?: string;
    terms_accepted: boolean;
  }) => api.post("/auth/register", userData),

  logout: () => api.post("/auth/logout"),

  refreshToken: (refreshToken: string) =>
    api.post(
      "/auth/refresh",
      {},
      {
        headers: { Authorization: `Bearer ${refreshToken}` },
      },
    ),

  getCurrentUser: () => api.get("/auth/me"),

  updateProfile: (data: any) => api.put("/auth/me", data),

  changePassword: (data: {
    current_password: string;
    new_password: string;
    confirm_password: string;
  }) => api.post("/auth/change-password", data),

  forgotPassword: (email: string) =>
    api.post("/auth/forgot-password", { email }),

  resetPassword: (data: {
    token: string;
    password: string;
    confirm_password: string;
  }) => api.post("/auth/reset-password", data),

  verifyEmail: () => api.post("/auth/verify-email"),
};

// Trading API
export const tradingAPI = {
  getTrades: (params?: {
    page?: number;
    limit?: number;
    status?: string;
    symbol?: string;
  }) => api.get("/trades", { params }),

  createTrade: (tradeData: {
    symbol: string;
    side: "buy" | "sell";
    quantity: number;
    order_type: "market" | "limit";
    price?: number;
    stop_loss?: number;
    take_profit?: number;
  }) => api.post("/trades", tradeData),

  getTrade: (tradeId: string) => api.get(`/trades/${tradeId}`),

  cancelTrade: (tradeId: string) => api.delete(`/trades/${tradeId}`),

  getTradeHistory: (params?: {
    page?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
  }) => api.get("/trades/history", { params }),
};

// Portfolio API
export const portfolioAPI = {
  getPortfolios: () => api.get("/portfolios"),

  getPortfolio: (portfolioId: string) => api.get(`/portfolios/${portfolioId}`),

  createPortfolio: (portfolioData: {
    name: string;
    description?: string;
    initial_balance: number;
  }) => api.post("/portfolios", portfolioData),

  updatePortfolio: (portfolioId: string, data: any) =>
    api.put(`/portfolios/${portfolioId}`, data),

  deletePortfolio: (portfolioId: string) =>
    api.delete(`/portfolios/${portfolioId}`),

  getPortfolioPerformance: (portfolioId: string, period?: string) =>
    api.get(`/portfolios/${portfolioId}/performance`, {
      params: { period },
    }),

  getPositions: (portfolioId: string) =>
    api.get(`/portfolios/${portfolioId}/positions`),
};

// Challenges API
export const challengesAPI = {
  getChallenges: (params?: {
    page?: number;
    limit?: number;
    status?: string;
  }) => api.get("/challenges", { params }),

  getChallenge: (challengeId: string) => api.get(`/challenges/${challengeId}`),

  createChallenge: (challengeData: {
    name: string;
    description?: string;
    initial_balance: number;
    target_profit: number;
    max_loss: number;
    duration_days: number;
    max_daily_loss?: number;
    entry_fee?: number;
  }) => api.post("/challenges", challengeData),

  joinChallenge: (challengeId: string) =>
    api.post(`/challenges/${challengeId}/join`),

  leaveChallenge: (challengeId: string) =>
    api.post(`/challenges/${challengeId}/leave`),

  getChallengeLeaderboard: (challengeId: string) =>
    api.get(`/challenges/${challengeId}/leaderboard`),

  getChallengePerformance: (challengeId: string) =>
    api.get(`/challenges/${challengeId}/performance`),
};

// Market Data API
export const marketAPI = {
  getSymbols: () => api.get("/market/symbols"),

  getQuote: (symbol: string) => api.get(`/market/quote/${symbol}`),

  getQuotes: (symbols: string[]) => api.post("/market/quotes", { symbols }),

  getCandles: (
    symbol: string,
    params: {
      timeframe: string;
      start_date?: string;
      end_date?: string;
      limit?: number;
    },
  ) => api.get(`/market/candles/${symbol}`, { params }),

  searchSymbols: (query: string) =>
    api.get("/market/search", { params: { q: query } }),

  getMarketStatus: () => api.get("/market/status"),

  getTopMovers: () => api.get("/market/movers"),
};

// Risk Management API
export const riskAPI = {
  getRiskAssessment: (portfolioId?: string) =>
    api.get("/risk/assessment", {
      params: portfolioId ? { portfolio_id: portfolioId } : {},
    }),

  getRiskMetrics: (portfolioId: string) =>
    api.get(`/risk/metrics/${portfolioId}`),

  updateRiskSettings: (
    portfolioId: string,
    settings: {
      max_daily_loss?: number;
      max_total_loss?: number;
      max_position_size?: number;
    },
  ) => api.put(`/risk/settings/${portfolioId}`, settings),

  getRiskAlerts: () => api.get("/risk/alerts"),

  dismissRiskAlert: (alertId: string) =>
    api.post(`/risk/alerts/${alertId}/dismiss`),
};

// Analytics API
export const analyticsAPI = {
  getPerformanceMetrics: (params?: {
    portfolio_id?: string;
    start_date?: string;
    end_date?: string;
  }) => api.get("/analytics/performance", { params }),

  getTradingStats: (params?: { portfolio_id?: string; period?: string }) =>
    api.get("/analytics/trading-stats", { params }),

  getDrawdownAnalysis: (portfolioId: string) =>
    api.get(`/analytics/drawdown/${portfolioId}`),

  getCorrelationMatrix: (portfolioId: string) =>
    api.get(`/analytics/correlation/${portfolioId}`),

  getBacktestResults: (backtestId: string) =>
    api.get(`/analytics/backtest/${backtestId}`),
};

// Payments API
export const paymentsAPI = {
  getPayments: (params?: { page?: number; limit?: number; status?: string }) =>
    api.get("/payments", { params }),

  createPayment: (paymentData: {
    amount: number;
    currency: string;
    payment_type: string;
    description?: string;
  }) => api.post("/payments", paymentData),

  getPayment: (paymentId: string) => api.get(`/payments/${paymentId}`),

  processPayment: (
    paymentId: string,
    paymentMethod: {
      type: string;
      details: any;
    },
  ) => api.post(`/payments/${paymentId}/process`, paymentMethod),

  getPaymentMethods: () => api.get("/payments/methods"),

  addPaymentMethod: (methodData: any) =>
    api.post("/payments/methods", methodData),

  removePaymentMethod: (methodId: string) =>
    api.delete(`/payments/methods/${methodId}`),
};

// Notifications API
export const notificationsAPI = {
  getNotifications: (params?: {
    page?: number;
    limit?: number;
    status?: string;
  }) => api.get("/notifications", { params }),

  markAsRead: (notificationId: string) =>
    api.put(`/notifications/${notificationId}/read`),

  markAllAsRead: () => api.put("/notifications/read-all"),

  deleteNotification: (notificationId: string) =>
    api.delete(`/notifications/${notificationId}`),

  getNotificationSettings: () => api.get("/notifications/settings"),

  updateNotificationSettings: (settings: {
    email_notifications?: boolean;
    push_notifications?: boolean;
    trade_alerts?: boolean;
    market_alerts?: boolean;
    challenge_updates?: boolean;
  }) => api.put("/notifications/settings", settings),
};

export default api;
