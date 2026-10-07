import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  FiHome, 
  FiLogIn, 
  FiUserPlus, 
  FiMenu, 
  FiX, 
  FiBell, 
  FiUsers, 
  FiGrid, 
  FiLogOut,
  FiCheckSquare,
  FiAward,
  FiCalendar,
  FiCompass,
  FiBriefcase
} from 'react-icons/fi';

const Navbar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [user, setUser] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();
  
  // Track auth status from localStorage on route changes
  useEffect(() => {
    const checkAuth = () => {
      const stored = localStorage.getItem('student_sync_user');
      if (stored) {
        try {
          setUser(JSON.parse(stored));
        } catch (e) {
          setUser(null);
        }
      } else {
        setUser(null);
      }
    };

    checkAuth();
  }, [location.pathname]);

  // Handle scroll effect
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 15);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('student_sync_user');
    setUser(null);
    navigate('/', { replace: true });
  };

  const navItems = user ? [
    { path: '/dashboard', name: 'Dashboard', icon: <FiGrid className="text-base" /> },
    { path: '/attendance', name: 'Attendance', icon: <FiCheckSquare className="text-base" /> },
    { path: '/grades', name: 'Grades & Analytics', icon: <FiAward className="text-base" /> },
    { path: '/schedule', name: 'Schedule & Exams', icon: <FiCalendar className="text-base" /> },
    { path: '/planner', name: 'Academic Planner', icon: <FiCompass className="text-base" /> },
    { path: '/services', name: 'Campus Services', icon: <FiBriefcase className="text-base" /> },
    { path: '/welcome', name: 'Notifications', icon: <FiBell className="text-base" /> },
    { path: '/about', name: 'Developers', icon: <FiUsers className="text-base" /> },
  ] : [
    { path: '/', name: 'Home', icon: <FiHome className="text-base" /> },
    { path: '/login', name: 'Log In', icon: <FiLogIn className="text-base" /> },
    { path: '/register', name: 'Register', icon: <FiUserPlus className="text-base" /> },
    { path: '/about', name: 'Developers', icon: <FiUsers className="text-base" /> },
  ];

  return (
    <nav 
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${
        scrolled 
          ? 'bg-[#0e1118]/90 backdrop-blur-md border-b border-[#1f2433] shadow-sm' 
          : 'bg-transparent border-b border-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand Logo */}
        <Link 
          to={user ? "/dashboard" : "/"} 
          className="flex items-center gap-2.5 text-white font-semibold text-lg tracking-tight hover:opacity-90 transition-opacity"
        >
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <FiBell className="text-base" />
          </div>
          <span>Student Sync</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center space-x-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link 
                key={item.path}
                to={item.path} 
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive 
                    ? 'text-white bg-[#1a1e2c] border border-[#2a3045]' 
                    : 'text-gray-400 hover:text-gray-200 hover:bg-[#141824]'
                }`}
              >
                {item.icon}
                <span>{item.name}</span>
              </Link>
            );
          })}

          {/* User Session Info & Logout */}
          {user && (
            <div className="flex items-center pl-3 ml-2 border-l border-[#242938] gap-3">
              <span className="text-xs font-mono text-gray-300 bg-[#161a26] border border-[#242a3a] px-2.5 py-1 rounded-md">
                {user.rollNo}
              </span>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/20 rounded-lg transition-colors"
                title="Sign Out"
              >
                <FiLogOut className="text-xs" />
                <span>Logout</span>
              </button>
            </div>
          )}
        </div>

        {/* Mobile Menu Button */}
        <div className="md:hidden">
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-[#1a1e2c] transition-colors"
            aria-label="Toggle menu"
          >
            {isOpen ? <FiX size={20} /> : <FiMenu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Dropdown */}
      {isOpen && (
        <div className="md:hidden bg-[#0f121a] border-b border-[#1f2433] px-4 pt-2 pb-4 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link 
                key={item.path}
                to={item.path} 
                className={`flex items-center gap-2.5 w-full px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive 
                    ? 'text-white bg-[#1a1e2c] font-semibold' 
                    : 'text-gray-400 hover:text-white hover:bg-[#141824]'
                }`}
                onClick={() => setIsOpen(false)}
              >
                {item.icon}
                <span>{item.name}</span>
              </Link>
            );
          })}

          {user && (
            <div className="pt-3 mt-2 border-t border-[#1f2433] flex items-center justify-between px-2">
              <span className="text-xs font-mono text-gray-400">{user.rollNo}</span>
              <button
                onClick={() => {
                  handleLogout();
                  setIsOpen(false);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-400 bg-red-500/10 border border-red-500/20 rounded-md"
              >
                <FiLogOut className="text-xs" />
                <span>Logout</span>
              </button>
            </div>
          )}
        </div>
      )}
    </nav>
  );
};

export default Navbar;
