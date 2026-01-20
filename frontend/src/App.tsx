import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "react-query";
import { ThemeProvider, createTheme, CssBaseline } from "@mui/material";
import { Toaster } from "react-hot-toast";

// Components
import Layout from "./components/Layout/Layout";
import ProtectedRoute from "./components/Auth/ProtectedRoute";

// Pages
import Login from "./pages/Auth/Login";
import Register from "./pages/Auth/Register";
import Dashboard from "./pages/Dashboard/Dashboard";
import Trading from "./pages/Trading/Trading";
import Portfolio from "./pages/Portfolio/Portfolio";
import Challenges from "./pages/Challenges/Challenges";
import Profile from "./pages/Profile/Profile";
import NotFound from "./pages/NotFound/NotFound";

// Hooks and Context
import { AuthProvider } from "./contexts/AuthContext";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import { useAuthStore } from "./stores/authStore";

// Styles
import "./App.css";

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

// Create Material-UI theme
const theme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#1976d2",
      dark: "#115293",
      light: "#42a5f5",
    },
    secondary: {
      main: "#dc004e",
      dark: "#9a0036",
      light: "#e5336d",
    },
    background: {
      default: "#0a0e27",
      paper: "#1a1d36",
    },
    text: {
      primary: "#ffffff",
      secondary: "#b0bec5",
    },
    success: {
      main: "#4caf50",
    },
    error: {
      main: "#f44336",
    },
    warning: {
      main: "#ff9800",
    },
  },
  typography: {
    fontFamily: [
      "-apple-system",
      "BlinkMacSystemFont",
      '"Segoe UI"',
      "Roboto",
      '"Helvetica Neue"',
      "Arial",
      "sans-serif",
    ].join(","),
    h1: {
      fontSize: "2.5rem",
      fontWeight: 600,
    },
    h2: {
      fontSize: "2rem",
      fontWeight: 600,
    },
    h3: {
      fontSize: "1.75rem",
      fontWeight: 500,
    },
    h4: {
      fontSize: "1.5rem",
      fontWeight: 500,
    },
    h5: {
      fontSize: "1.25rem",
      fontWeight: 500,
    },
    h6: {
      fontSize: "1rem",
      fontWeight: 500,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          borderRadius: 8,
          fontWeight: 600,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)",
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: 8,
          },
        },
      },
    },
  },
});

const App: React.FC = () => {
  const { isAuthenticated } = useAuthStore();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <AuthProvider>
          <WebSocketProvider>
            <Router>
              <div className="App">
                <Routes>
                  {/* Public Routes */}
                  <Route
                    path="/login"
                    element={
                      isAuthenticated ? (
                        <Navigate to="/dashboard" replace />
                      ) : (
                        <Login />
                      )
                    }
                  />
                  <Route
                    path="/register"
                    element={
                      isAuthenticated ? (
                        <Navigate to="/dashboard" replace />
                      ) : (
                        <Register />
                      )
                    }
                  />

                  {/* Protected Routes */}
                  <Route path="/" element={<Layout />}>
                    <Route
                      index
                      element={<Navigate to="/dashboard" replace />}
                    />

                    <Route
                      path="dashboard"
                      element={
                        <ProtectedRoute>
                          <Dashboard />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="trading"
                      element={
                        <ProtectedRoute>
                          <Trading />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="portfolio"
                      element={
                        <ProtectedRoute>
                          <Portfolio />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="challenges"
                      element={
                        <ProtectedRoute>
                          <Challenges />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="profile"
                      element={
                        <ProtectedRoute>
                          <Profile />
                        </ProtectedRoute>
                      }
                    />
                  </Route>

                  {/* 404 Route */}
                  <Route path="*" element={<NotFound />} />
                </Routes>

                {/* Toast Notifications */}
                <Toaster
                  position="top-right"
                  toastOptions={{
                    duration: 4000,
                    style: {
                      background: theme.palette.background.paper,
                      color: theme.palette.text.primary,
                      borderRadius: "8px",
                      boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)",
                    },
                    success: {
                      iconTheme: {
                        primary: theme.palette.success.main,
                        secondary: "#ffffff",
                      },
                    },
                    error: {
                      iconTheme: {
                        primary: theme.palette.error.main,
                        secondary: "#ffffff",
                      },
                    },
                  }}
                />
              </div>
            </Router>
          </WebSocketProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;
