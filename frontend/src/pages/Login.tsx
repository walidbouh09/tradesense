import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
  Tab,
  Tabs,
  Divider,
} from '@mui/material';
import { Login as LoginIcon, PersonAdd as RegisterIcon } from '@mui/icons-material';

import { useAuth } from '../contexts/AuthContext';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`auth-tabpanel-${index}`}
      aria-labelledby={`auth-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const Login: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register } = useAuth();

  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Login form state
  const [loginData, setLoginData] = useState({
    email: 'demo@tradesense.ai',
    password: 'demo123',
  });

  // Register form state
  const [registerData, setRegisterData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const from = location.state?.from?.pathname || '/dashboard';

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    setError('');
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await login(loginData.email, loginData.password);
      navigate(from, { replace: true });
    } catch (err) {
      setError('Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (registerData.password !== registerData.confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    if (registerData.password.length < 6) {
      setError('Password must be at least 6 characters');
      setLoading(false);
      return;
    }

    try {
      await register(registerData.email, registerData.password, registerData.name);
      navigate(from, { replace: true });
    } catch (err) {
      setError('Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Paper elevation={3} sx={{ p: 0 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange} aria-label="auth tabs">
            <Tab
              icon={<LoginIcon />}
              label="Login"
              iconPosition="start"
              sx={{ minHeight: 64 }}
            />
            <Tab
              icon={<RegisterIcon />}
              label="Register"
              iconPosition="start"
              sx={{ minHeight: 64 }}
            />
          </Tabs>
        </Box>

        {error && (
          <Box sx={{ px: 3, pt: 2 }}>
            <Alert severity="error">{error}</Alert>
          </Box>
        )}

        {/* Login Tab */}
        <TabPanel value={tabValue} index={0}>
          <Typography variant="h4" component="h1" gutterBottom align="center">
            Welcome to TradeSense AI
          </Typography>
          <Typography variant="body1" color="text.secondary" align="center" sx={{ mb: 3 }}>
            Advanced Prop Trading with AI-Powered Risk Management
          </Typography>

          <Box component="form" onSubmit={handleLogin} sx={{ width: '100%' }}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={loginData.email}
              onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
              margin="normal"
              required
              autoComplete="email"
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
              value={loginData.password}
              onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
              margin="normal"
              required
              autoComplete="current-password"
            />

            <Box sx={{ mt: 3, mb: 2 }}>
              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                disabled={loading}
                startIcon={<LoginIcon />}
              >
                {loading ? 'Signing In...' : 'Sign In'}
              </Button>
            </Box>
          </Box>

          <Divider sx={{ my: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Demo Credentials
            </Typography>
          </Divider>

          <Alert severity="info" sx={{ mb: 2 }}>
            <strong>Demo Account:</strong><br />
            Email: demo@tradesense.ai<br />
            Password: demo123
          </Alert>
        </TabPanel>

        {/* Register Tab */}
        <TabPanel value={tabValue} index={1}>
          <Typography variant="h4" component="h1" gutterBottom align="center">
            Join TradeSense AI
          </Typography>
          <Typography variant="body1" color="text.secondary" align="center" sx={{ mb: 3 }}>
            Start your prop trading journey with AI-powered insights
          </Typography>

          <Box component="form" onSubmit={handleRegister} sx={{ width: '100%' }}>
            <TextField
              fullWidth
              label="Full Name"
              value={registerData.name}
              onChange={(e) => setRegisterData({ ...registerData, name: e.target.value })}
              margin="normal"
              required
              autoComplete="name"
            />
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={registerData.email}
              onChange={(e) => setRegisterData({ ...registerData, email: e.target.value })}
              margin="normal"
              required
              autoComplete="email"
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
              value={registerData.password}
              onChange={(e) => setRegisterData({ ...registerData, password: e.target.value })}
              margin="normal"
              required
              autoComplete="new-password"
              helperText="Minimum 6 characters"
            />
            <TextField
              fullWidth
              label="Confirm Password"
              type="password"
              value={registerData.confirmPassword}
              onChange={(e) => setRegisterData({ ...registerData, confirmPassword: e.target.value })}
              margin="normal"
              required
              autoComplete="new-password"
            />

            <Box sx={{ mt: 3, mb: 2 }}>
              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                disabled={loading}
                startIcon={<RegisterIcon />}
              >
                {loading ? 'Creating Account...' : 'Create Account'}
              </Button>
            </Box>
          </Box>
        </TabPanel>
      </Paper>

      <Box sx={{ mt: 4, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          TradeSense AI - Powered by Advanced Risk Intelligence
        </Typography>
      </Box>
    </Container>
  );
};

export default Login;