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
  FiBriefcase
} from 'react-icons/fi';

const Navbar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [user, setUser] = useState(null);
  const [residentialStatus, setResidentialStatus] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();
  
  // Track auth status from localStorage on route changes
  useEffect(() => {
    const checkAuth = () => {
      const stored = localStorage.getItem('student_sync_user');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          setUser(parsed);
          if (parsed.residential_status) {
            setResidentialStatus(parsed.residential_status);
          } else if (parsed.auth_token) {
            // Lazy fetch verified residential eligibility from backend
            fetch(`/api/v1/hostel/status?auth_token=${encodeURIComponent(parsed.auth_token)}`)
              .then(res => res.json())
              .then(data => {
                if (data.success && data.status) {
                  setResidentialStatus(data.status);
                  const updated = { ...parsed, residential_status: data.status, can_access_hostel: data.canAccessHostel };
                  localStorage.setItem('student_sync_user', JSON.stringify(updated));
                }
              })
              .catch(() => {});
          }
        } catch (e) {
          setUser(null);
          setResidentialStatus(null);
        }
      } else {
        setUser(null);
        setResidentialStatus(null);
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
    sessionStorage.clear();
    setUser(null);
    setResidentialStatus(null);
    navigate('/', { replace: true });
  };

  const isHosteller = (residentialStatus === 'HOSTELLER') || (user && user.residential_status === 'HOSTELLER');

  const navItems = user ? [
    { path: '/dashboard', name: 'Dashboard', icon: <FiGrid className="text-base" /> },
    { path: '/attendance', name: 'Attendance', icon: <FiCheckSquare className="text-base" /> },
    { path: '/grades', name: 'Grades & Analytics', icon: <FiAward className="text-base" /> },
    { path: '/schedule', name: 'Schedule & Exams', icon: <FiCalendar className="text-base" /> },
    { path: '/services', name: 'Campus Services', icon: <FiBriefcase className="text-base" /> },
    ...(isHosteller ? [{ path: '/hostel', name: 'Hostel', icon: <FiHome className="text-base" /> }] : []),
    { path: '/welcome', name: 'Notifications', icon: <FiBell className="text-base" /> },
    { path: '/about', name: 'Developers', icon: <FiUsers className="text-base" /> },
  ] : [
    { path: '/', name: 'Home', icon: <FiHome className="text-base" /> },
    { path: '/login', name: 'Login', icon: <FiLogIn className="text-base" /> },
    { path: '/register', name: 'Register', icon: <FiUserPlus className="text-base" /> },
    { path: '/about', name: 'Developers', icon: <FiUsers className="text-base" /> },
  ];

  return (
    <nav 
      className="fixed top-0 left-0 right-0 z-50 bg-[#0e1118] border-b border-[#1f2433] shadow-sm transition-all duration-200"
    >
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4 flex-nowrap">
        
        {/* Brand Logo - Fixed Anchor */}
        <Link 
          to={user ? "/dashboard" : "/"} 
          className="flex items-center gap-2.5 text-white font-semibold text-base sm:text-lg tracking-tight hover:opacity-90 transition-opacity flex-shrink-0 whitespace-nowrap"
        >
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 flex-shrink-0">
            <FiBell className="text-base" />
          </div>
          <span className="whitespace-nowrap font-bold text-white tracking-tight">Student Sync</span>
        </Link>

        {/* Desktop Navigation - Neat Single Line */}
        <div className={`hidden ${user ? 'xl:flex' : 'md:flex'} items-center gap-1.5 2xl:gap-2 flex-nowrap flex-shrink-0`}>
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link 
                key={item.path}
                to={item.path} 
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs 2xl:text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${
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
            <div className="flex items-center pl-3 ml-2 border-l border-[#242938] gap-2.5 flex-shrink-0 whitespace-nowrap">
              <span className="text-xs font-mono text-gray-300 bg-[#161a26] border border-[#242a3a] px-2.5 py-1 rounded-md">
                {user.rollNo}
              </span>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/20 rounded-lg transition-colors whitespace-nowrap"
                title="Logout"
              >
                <FiLogOut className="text-xs" />
                <span>Logout</span>
              </button>
            </div>
          )}
        </div>

        {/* Mobile Menu Button */}
        <div className={user ? 'xl:hidden' : 'md:hidden'}>
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
        <div className={`${user ? 'xl:hidden' : 'md:hidden'} bg-[#0f121a] border-b border-[#1f2433] px-4 pt-2 pb-4 space-y-1`}>
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
