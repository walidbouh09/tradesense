import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Chip,
  IconButton,
  Menu,
  MenuItem,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Assessment as AssessmentIcon,
  AccountCircle as AccountIcon,
  ExitToApp as LogoutIcon,
  TrendingUp as TradingIcon,
} from '@mui/icons-material';

import { useAuth } from '../../contexts/AuthContext';

const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    handleClose();
    navigate('/login');
  };

  const navigationItems = [
    {
      label: 'Dashboard',
      path: '/dashboard',
      icon: <DashboardIcon />,
    },
    {
      label: 'Challenges',
      path: '/challenges',
      icon: <TradingIcon />,
    },
    {
      label: 'Risk Monitor',
      path: '/risk-monitoring',
      icon: <AssessmentIcon />,
    },
  ];

  return (
    <AppBar position="static" elevation={1}>
      <Toolbar>
        {/* Logo/Brand */}
        <Typography
          variant="h6"
          component="div"
          sx={{
            flexGrow: 0,
            mr: 4,
            fontWeight: 'bold',
            cursor: 'pointer',
            background: 'linear-gradient(45deg, #1976d2, #42a5f5)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
          onClick={() => navigate('/dashboard')}
        >
          TradeSense AI
        </Typography>

        {/* Navigation Items */}
        <Box sx={{ flexGrow: 1, display: 'flex', gap: 1 }}>
          {navigationItems.map((item) => (
            <Button
              key={item.path}
              color="inherit"
              startIcon={item.icon}
              onClick={() => navigate(item.path)}
              sx={{
                backgroundColor: location.pathname === item.path ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                },
              }}
            >
              {item.label}
            </Button>
          ))}
        </Box>

        {/* User Menu */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip
            label="AI Risk Engine: Active"
            size="small"
            color="success"
            variant="outlined"
            sx={{ color: 'white', borderColor: 'rgba(255, 255, 255, 0.3)' }}
          />

          <Typography variant="body2" sx={{ mr: 1 }}>
            Welcome, {user?.name || 'Trader'}
          </Typography>

          <IconButton
            size="large"
            aria-label="account menu"
            aria-controls="menu-appbar"
            aria-haspopup="true"
            onClick={handleMenu}
            color="inherit"
          >
            <AccountIcon />
          </IconButton>

          <Menu
            id="menu-appbar"
            anchorEl={anchorEl}
            anchorOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
            keepMounted
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
            open={Boolean(anchorEl)}
            onClose={handleClose}
          >
            <MenuItem onClick={handleClose}>
              <AccountIcon sx={{ mr: 1 }} />
              Profile
            </MenuItem>
            <MenuItem onClick={handleClose}>
              <AssessmentIcon sx={{ mr: 1 }} />
              Settings
            </MenuItem>
            <MenuItem onClick={handleLogout}>
              <LogoutIcon sx={{ mr: 1 }} />
              Logout
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;