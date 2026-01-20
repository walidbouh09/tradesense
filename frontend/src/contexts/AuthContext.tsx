import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { jwtDecode } from 'jwt-decode';

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing token on app start
    const token = localStorage.getItem('auth_token');
    if (token) {
      try {
        const decoded = jwtDecode<User & { exp: number }>(token);
        const currentTime = Date.now() / 1000;

        if (decoded.exp > currentTime) {
          setUser({
            id: decoded.id,
            email: decoded.email,
            name: decoded.name,
            role: decoded.role,
          });
        } else {
          // Token expired
          localStorage.removeItem('auth_token');
        }
      } catch (error) {
        console.error('Invalid token:', error);
        localStorage.removeItem('auth_token');
      }
    }
    setLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    try {
      // For demo purposes, we'll simulate authentication
      // In a real app, this would call the API
      if (email === 'demo@tradesense.ai' && password === 'demo123') {
        const mockToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjEiLCJlbWFpbCI6ImRlbW9AdHJhZGVzZW5zZS5haSIsIm5hbWUiOiJEZW1vIFRyYWRlciIsInJvbGUiOiJVU0VSIiwiZXhwIjoxNzUyNzI5NjAwfQ.signature';
        const mockUser = {
          id: '1',
          email: 'demo@tradesense.ai',
          name: 'Demo Trader',
          role: 'USER',
        };

        localStorage.setItem('auth_token', mockToken);
        setUser(mockUser);
      } else {
        throw new Error('Invalid credentials');
      }
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const register = async (email: string, password: string, name: string) => {
    try {
      // For demo purposes, simulate registration
      const mockToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjIiLCJlbWFpbCI6Im5ld0B0cmFkZXNlbnNlLmFpIiwibmFtZSI6Ik5ldyBVc2VyIiwicm9sZSI6IlVTRVIiLCJleHAiOjE3NTI3Mjk2MDB9.signature';
      const mockUser = {
        id: '2',
        email: email,
        name: name,
        role: 'USER',
      };

      localStorage.setItem('auth_token', mockToken);
      setUser(mockUser);
    } catch (error) {
      console.error('Registration failed:', error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setUser(null);
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    loading,
    login,
    register,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};