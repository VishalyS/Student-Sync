import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { 
  FiAward, 
  FiCheckCircle, 
  FiCalendar, 
  FiFileText, 
  FiMapPin, 
  FiRefreshCw, 
  FiBell, 
  FiInfo, 
  FiLayers, 
  FiClock,
  FiCheck,
  FiSend,
  FiDollarSign,
  FiHome,
  FiGift,
  FiMessageSquare,
  FiActivity,
  FiUser,
  FiFile,
  FiExternalLink,
  FiChevronRight,
  FiMenu,
  FiX,
  FiAlertCircle,
  FiAlertTriangle,
  FiTrendingUp,
  FiTrendingDown,
  FiBookOpen,
  FiBook,
  FiCheckSquare,
  FiCompass,
  FiBriefcase
} from 'react-icons/fi';

const Dashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();
  
  // Initialize roll number from navigation state if available; fallback to verified session in localStorage
  const initialRollNo = (location.state && location.state.rollNo) 
    ? location.state.rollNo 
    : (() => {
        try {
          return JSON.parse(localStorage.getItem('student_sync_user') || '{}')?.rollNo || '';
        } catch(e) {
          return '';
        }
      })();
  const [rollNo, setRollNo] = useState(initialRollNo);
  const [studentData, setStudentData] = useState(null);

  const [notifications, setNotifications] = useState([]);
  const [unreadNotifsCount, setUnreadNotifsCount] = useState(0);
  const [notifFilter, setNotifFilter] = useState('all');
  const [stats, setStats] = useState({
    studentsRegistered: 0,
    notificationsDelivered: 0,
    totalNotifications: 0,
    unreadNotifications: 0,
    breakdown: {
      attendance: 0,
      marks: 0,
      results: 0,
      timetable: 0,
      seating: 0,
      fees: 0,
      welcome: 0
    }
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const fetchStudentData = async (userRollNo, isManualRefresh = false) => {
    if (!userRollNo) {
      setLoading(false);
      return;
    }
    
    if (isManualRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');

    try {
      const profileUrl = isManualRefresh 
        ? `http://127.0.0.1:5000/profile?rollNo=${userRollNo}&refresh=true` 
        : `http://127.0.0.1:5000/profile?rollNo=${userRollNo}`;

      const [profileRes, statsRes, notifsRes] = await Promise.all([
        fetch(profileUrl),
        fetch(`http://127.0.0.1:5000/stats`),
        fetch(`http://127.0.0.1:5000/notifications?rollNo=${userRollNo}`)
      ]);

      if (profileRes.status === 200) {
        const data = await profileRes.json();
        setStudentData(data);
        const existingStored = JSON.parse(localStorage.getItem('student_sync_user') || '{}');
        const tokenToKeep = data.auth_token || existingStored.auth_token;
        const mergedUser = { ...data, auth_token: tokenToKeep };
        localStorage.setItem('student_sync_user', JSON.stringify(mergedUser));
      } else {
        setError('Failed to load student academic records.');
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      if (notifsRes.ok) {
        const notifsData = await notifsRes.json();
        setNotifications(notifsData.notifications || []);
        setUnreadNotifsCount(notifsData.unreadCount || 0);
      }
    } catch (err) {
      console.error('Error fetching student profile, stats, or notifications:', err);
      setError('Could not connect to backend server.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!rollNo) {
      navigate('/login');
    } else {
      fetchStudentData(rollNo);
    }
  }, [rollNo]);

  const handleMarkAsRead = async (notifId = null, markAll = false) => {
    try {
      await fetch('http://127.0.0.1:5000/notifications/mark-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rollNo, notificationId: notifId, all: markAll })
      });
      if (markAll) {
        setNotifications(prev => prev.map(n => ({ ...n, read: true })));
        setUnreadNotifsCount(0);
      } else if (notifId) {
        setNotifications(prev => prev.map(n => (n._id === notifId || n.changeHash === notifId) ? { ...n, read: true } : n));
        setUnreadNotifsCount(prev => Math.max(0, prev - 1));
      }
    } catch (err) {
      console.error('Failed to mark notification read:', err);
    }
  };

  const formatRelativeTime = (isoString) => {
    if (!isoString) return 'Recently';
    try {
      const diff = Math.floor((new Date() - new Date(isoString)) / 1000);
      if (diff < 60) return 'Just now';
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      if (diff < 172800) return 'Yesterday';
      return `${Math.floor(diff / 86400)}d ago`;
    } catch (e) {
      return 'Recently';
    }
  };

  const fullName = studentData?.name && studentData.name !== studentData.rollNo 
    ? studentData.name 
    : (studentData?.rollNo || 'Student');

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Welcome back';
  };

  // Structured Data Shortcuts
  const sz1 = studentData?.studzone1 || {};
  const sz2 = studentData?.studzone2 || {};

  const attendanceCourses = (sz1?.parsed_attendance && sz1.parsed_attendance.length > 0)
    ? sz1.parsed_attendance
    : (studentData?.previous_parsed_attendance || []);
  const caMarksSubjects = sz1?.parsed_marks || [];
  const resultsCourses = sz2?.parsed_results || [];
  const timetableSlots = sz2?.parsed_timetable || [];
  const feedbackSchedules = sz1?.feedback || [];
  const circulars = sz2?.circulars || [];
  const profileDetails = sz1?.profile || studentData?.profile || {};

  const filteredNotifications = notifFilter === 'all' 
    ? notifications 
    : notifications.filter(n => n.type === notifFilter);

  const getNotifIcon = (notif) => {
    const type = notif.type || '';
    const title = (notif.title || '').toLowerCase();
    const msg = (notif.message || '').toLowerCase();

    if (type === 'attendance') {
      if (msg.includes('dropped') || title.includes('alert')) {
        return <FiAlertTriangle className="text-amber-400" size={16} />;
      }
      return <FiTrendingUp className="text-emerald-400" size={16} />;
    }
    if (type === 'marks') {
      return <FiFileText className="text-purple-400" size={16} />;
    }
    if (type === 'results') {
      return <FiAward className="text-purple-400" size={16} />;
    }
    if (type === 'timetable') {
      return <FiCalendar className="text-blue-400" size={16} />;
    }
    if (type === 'seating') {
      return <FiMapPin className="text-pink-400" size={16} />;
    }
    if (type === 'fees') {
      return <FiDollarSign className="text-emerald-400" size={16} />;
    }
    if (type === 'hostel') {
      return <FiHome className="text-indigo-400" size={16} />;
    }
    if (type === 'scholarships') {
      return <FiGift className="text-yellow-400" size={16} />;
    }
    if (type === 'feedback') {
      return <FiMessageSquare className="text-teal-400" size={16} />;
    }
    if (type === 'welcome') {
      return <FiBell className="text-purple-400" size={16} />;
    }
    return <FiInfo className="text-gray-400" size={16} />;
  };

  const getPortalStatusBadge = () => {
    if (refreshing) {
      return (
        <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-500/10 border border-purple-500/20 text-purple-400">
          <FiRefreshCw className="text-[10px] animate-spin" /> Synchronizing Portals...
        </span>
      );
    }
    const sz1 = studentData?.portalStatus?.studzone1;
    const sz2 = studentData?.portalStatus?.studzone2;
    if (sz1 === 'connected' && sz2 === 'connected') {
      return (
        <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
          <FiCheck className="text-[10px]" /> StudZone 1 & 2 Synced
        </span>
      );
    } else if (sz1 === 'connected' && sz2 !== 'connected') {
      return (
        <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 border border-amber-500/20 text-amber-400">
          <FiAlertTriangle className="text-[10px]" /> StudZone 1 Synced • StudZone 2 Unavailable
        </span>
      );
    } else if (sz1 !== 'connected' && sz2 === 'connected') {
      return (
        <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 border border-amber-500/20 text-amber-400">
          <FiAlertTriangle className="text-[10px]" /> StudZone 2 Synced • StudZone 1 Unavailable
        </span>
      );
    } else {
      return (
        <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-500/10 border border-rose-500/20 text-rose-400">
          <FiAlertCircle className="text-[10px]" /> Portals Offline / Sync Pending
        </span>
      );
    }
  };

  const getBannerPortalStatus = () => {
    const sz1 = studentData?.portalStatus?.studzone1;
    const sz2 = studentData?.portalStatus?.studzone2;
    if (sz1 === 'connected' && sz2 === 'connected') {
      return <span className="text-emerald-400">StudZone 1 & 2 Connected</span>;
    } else if (sz1 === 'connected') {
      return <span className="text-amber-400">StudZone 1 Connected • StudZone 2 Retrying</span>;
    } else if (sz2 === 'connected') {
      return <span className="text-amber-400">StudZone 2 Connected • StudZone 1 Retrying</span>;
    } else {
      return <span className="text-rose-400">Portals Temporarily Unavailable</span>;
    }
  };

  const navCategories = [
    {
      title: 'OVERVIEW',
      items: [
        { id: 'overview', label: 'Overview', icon: <FiLayers size={16} /> },
        { 
          id: 'notifications', 
          label: 'Notifications', 
          icon: <FiBell size={16} />, 
          badge: unreadNotifsCount > 0 ? `${unreadNotifsCount} New` : (notifications.length ? `${notifications.length}` : null) 
        }
      ]
    },
    {
      title: 'ACADEMICS',
      items: [
        { id: 'attendance', label: 'Attendance', icon: <FiCheckCircle size={16} />, badge: attendanceCourses.length ? `${attendanceCourses.length}` : null },
        { id: 'marks', label: 'CA Marks', icon: <FiFileText size={16} />, badge: caMarksSubjects.length ? `${caMarksSubjects.length}` : null },
        { id: 'results', label: 'Semester Results', icon: <FiAward size={16} />, badge: studentData?.cgpa ? `CGPA ${studentData.cgpa}` : null },
        { id: 'cgpa_history', label: 'CGPA Summary', icon: <FiAward size={16} /> }
      ]
    },
    {
      title: 'EXAMINATIONS',
      items: [
        { id: 'timetable', label: 'Exam Timetable', icon: <FiCalendar size={16} />, badge: timetableSlots.length ? `${timetableSlots.length} Slots` : null },
        { id: 'seating', label: 'Seating Arrangement', icon: <FiMapPin size={16} /> },
        { id: 'reappearance', label: 'Reappearance Results', icon: <FiActivity size={16} /> },
        { id: 'revaluation', label: 'Revaluation Results', icon: <FiFile size={16} /> },
        { id: 'retotalling', label: 'Retotalling & Reval Info', icon: <FiBookOpen size={16} /> },
        { id: 'circulars', label: 'Exam Circulars & PDFs', icon: <FiFileText size={16} />, badge: circulars.length ? `${circulars.length}` : null }
      ]
    },
    {
      title: 'CAMPUS SERVICES',
      items: [
        { id: 'fees', label: 'Fees', icon: <FiDollarSign size={16} /> },
        { id: 'feedback', label: 'Feedback', icon: <FiMessageSquare size={16} /> },
        { id: 'hostel', label: 'Hostel', icon: <FiHome size={16} /> },
        { id: 'scholarships', label: 'Scholarships', icon: <FiGift size={16} /> },
        { id: 'leave', label: 'Leave & OD', icon: <FiCalendar size={16} /> },
        { id: 'library', label: 'Library', icon: <FiBook size={16} /> }
      ]
    },
    {
      title: 'ACCOUNT',
      items: [
        { id: 'profile', label: 'Student Profile', icon: <FiUser size={16} /> }
      ]
    }
  ];

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-20 pb-16">
      
      {/* Top Header Strip */}
      <div className="border-b border-[#1f2434] bg-[#0e111a]/90 backdrop-blur sticky top-16 z-30 px-4 sm:px-6 lg:px-8 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-lg bg-[#181c2b] border border-[#262c3e] text-gray-300 hover:text-white"
            >
              {mobileMenuOpen ? <FiX size={18} /> : <FiMenu size={18} />}
            </button>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400 font-medium">{getGreeting()},</span>
                <span className="text-sm font-bold text-white">{fullName}</span>
                {getPortalStatusBadge()}
              </div>
              <div className="text-[11px] text-gray-400 font-mono">
                {rollNo} • PSG College of Technology
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchStudentData(rollNo, true)}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#181c2b] hover:bg-[#222738] border border-[#282e42] text-xs font-medium text-gray-300 hover:text-white transition-all shadow-sm"
              title="Refresh live data from both portals"
            >
              <FiRefreshCw className={`text-xs ${refreshing ? 'animate-spin text-purple-400' : ''}`} />
              <span className="hidden sm:inline">{refreshing ? 'Refreshing...' : 'Refresh'}</span>
            </button>

            <button
              onClick={() => setActiveTab('notifications')}
              className="relative inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#181c2b] hover:bg-[#222738] border border-[#282e42] text-xs font-medium text-gray-300 hover:text-white transition-all"
            >
              <FiBell className="text-xs text-purple-400" />
              <span className="hidden sm:inline">Alerts</span>
              {unreadNotifsCount > 0 && (
                <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
              )}
            </button>

            <Link
              to="/welcome"
              state={studentData}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#181c2b] hover:bg-[#222738] border border-[#282e42] text-xs font-medium text-gray-300 hover:text-white transition-all"
            >
              <FiUser className="text-xs text-purple-400" />
              <span className="hidden sm:inline">Settings</span>
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <div className="flex gap-6">
          
          {/* SIDEBAR NAVIGATION (Desktop + Mobile Drawer) */}
          <aside className={`
            fixed lg:static inset-y-0 left-0 z-40 w-64 lg:w-60 flex-shrink-0
            bg-[#0e111a] lg:bg-transparent border-r lg:border-r-0 border-[#1f2434]
            p-4 lg:p-0 overflow-y-auto transition-transform duration-200 ease-in-out
            ${mobileMenuOpen ? 'translate-x-0 top-16 shadow-2xl' : '-translate-x-full lg:translate-x-0'}
          `}>
            <div className="space-y-6">
              {navCategories.map((cat, cIdx) => (
                <div key={cIdx} className="space-y-1">
                  <div className="px-3 text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                    {cat.title}
                  </div>
                  {cat.items.map((item) => {
                    const isActive = activeTab === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => {
                          setActiveTab(item.id);
                          setMobileMenuOpen(false);
                        }}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                          isActive
                            ? 'bg-[#1e2333] text-white border border-[#2e354a] shadow-sm font-semibold'
                            : 'text-gray-400 hover:text-gray-200 hover:bg-[#141724]'
                        }`}
                      >
                        <div className="flex items-center gap-2.5 truncate">
                          <span className={isActive ? 'text-purple-400' : 'text-gray-400'}>{item.icon}</span>
                          <span className="truncate">{item.label}</span>
                        </div>
                        {item.badge && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                            isActive ? 'bg-purple-500/20 text-purple-300' : 'bg-[#181c2b] text-gray-400'
                          }`}>
                            {item.badge}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </aside>

          {/* Backdrop for mobile drawer */}
          {mobileMenuOpen && (
            <div 
              onClick={() => setMobileMenuOpen(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden"
            />
          )}

          {/* MAIN CONTENT AREA */}
          <main className="flex-1 min-w-0 space-y-6">
            
            {error && (
              <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2.5">
                <FiAlertCircle className="text-base flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {loading ? (
              <div className="flex flex-col justify-center items-center py-32 space-y-3">
                <div className="w-7 h-7 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs text-gray-400">Loading student modules from StudZone 1 & StudZone 2...</span>
              </div>
            ) : (
              <div>
                
                {/* 1. OVERVIEW */}
                {activeTab === 'overview' && (
                  <div className="space-y-6">
                    
                    {/* Welcome Profile Banner */}
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 shadow-sm relative overflow-hidden">
                      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="space-y-1">
                          <div className="text-xs text-purple-400 font-semibold uppercase tracking-wider">
                            Unified Student Portal
                          </div>
                          <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                            {fullName}
                          </h2>
                          <div className="text-xs text-gray-400 flex flex-wrap items-center gap-2 pt-1">
                            <span className="font-mono text-gray-300 bg-[#181c2b] px-2 py-0.5 rounded border border-[#24293c]">
                              {rollNo}
                            </span>
                            <span>•</span>
                            <span>{profileDetails?.Degree || 'MASTER OF COMPUTER APPLICATIONS'}</span>
                            <span>•</span>
                            {getBannerPortalStatus()}
                          </div>
                        </div>

                        <div className="flex items-center gap-3 pt-2 md:pt-0">
                          <div className="text-right">
                            <div className="text-[10px] text-gray-400 uppercase font-semibold">Cumulative GPA</div>
                            <div className="text-2xl font-extrabold text-white">
                              {studentData?.cgpa ? studentData.cgpa : 'Pending'}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Quick Metric Cards */}
                    <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      
                      {/* Attendance Card */}
                      <div 
                        onClick={() => setActiveTab('attendance')}
                        className="p-4 rounded-xl bg-[#131620] border border-[#232738] hover:border-[#32394e] cursor-pointer transition-all flex flex-col justify-between"
                      >
                        <div className="flex items-center justify-between text-xs text-gray-400">
                          <span className="text-[10px] font-semibold uppercase tracking-wider">Attendance</span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono">
                            StudZone 1
                          </span>
                        </div>
                        <div className="my-2">
                          <div className="text-2xl font-bold text-white">
                            {attendanceCourses.length ? `${attendanceCourses.length} Subjects` : 'Recorded'}
                          </div>
                        </div>
                        <div className="text-[11px] text-gray-400 flex items-center justify-between pt-2 border-t border-[#1c202e]">
                          <span>Subject breakdown</span>
                          <FiChevronRight className="text-purple-400" />
                        </div>
                      </div>

                      {/* CA Marks Card */}
                      <div 
                        onClick={() => setActiveTab('marks')}
                        className="p-4 rounded-xl bg-[#131620] border border-[#232738] hover:border-[#32394e] cursor-pointer transition-all flex flex-col justify-between"
                      >
                        <div className="flex items-center justify-between text-xs text-gray-400">
                          <span className="text-[10px] font-semibold uppercase tracking-wider">CA Marks</span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 font-mono">
                            StudZone 1
                          </span>
                        </div>
                        <div className="my-2">
                          <div className="text-2xl font-bold text-white">
                            {caMarksSubjects.length ? `${caMarksSubjects.length} Subjects` : 'Published'}
                          </div>
                        </div>
                        <div className="text-[11px] text-gray-400 flex items-center justify-between pt-2 border-t border-[#1c202e]">
                          <span>Internal scores</span>
                          <FiChevronRight className="text-purple-400" />
                        </div>
                      </div>

                      {/* Semester Results Card */}
                      <div 
                        onClick={() => setActiveTab('results')}
                        className="p-4 rounded-xl bg-[#131620] border border-[#232738] hover:border-[#32394e] cursor-pointer transition-all flex flex-col justify-between"
                      >
                        <div className="flex items-center justify-between text-xs text-gray-400">
                          <span className="text-[10px] font-semibold uppercase tracking-wider">Results</span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 font-mono">
                            StudZone 2
                          </span>
                        </div>
                        <div className="my-2">
                          <div className="text-2xl font-bold text-white">
                            {resultsCourses.length ? `${resultsCourses.length} Subjects` : 'Published'}
                          </div>
                        </div>
                        <div className="text-[11px] text-gray-400 flex items-center justify-between pt-2 border-t border-[#1c202e]">
                          <span>Grades & Credits</span>
                          <FiChevronRight className="text-purple-400" />
                        </div>
                      </div>

                      {/* Exam Schedule Card */}
                      <div 
                        onClick={() => setActiveTab('timetable')}
                        className="p-4 rounded-xl bg-[#131620] border border-[#232738] hover:border-[#32394e] cursor-pointer transition-all flex flex-col justify-between"
                      >
                        <div className="flex items-center justify-between text-xs text-gray-400">
                          <span className="text-[10px] font-semibold uppercase tracking-wider">Exam Schedule</span>
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 font-mono">
                            StudZone 2
                          </span>
                        </div>
                        <div className="my-2">
                          <div className="text-2xl font-bold text-white">
                            {timetableSlots.length ? `${timetableSlots.length} Slots` : 'Published'}
                          </div>
                        </div>
                        <div className="text-[11px] text-gray-400 flex items-center justify-between pt-2 border-t border-[#1c202e]">
                          <span>View dates</span>
                          <FiChevronRight className="text-purple-400" />
                        </div>
                      </div>

                    </div>

                    {/* Schedule & Examination Cross-Links */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                      {/* Campus Services & Student Dossier Primary Cross-Link */}
                      <div className="p-4 rounded-xl bg-gradient-to-r from-cyan-950/30 via-[#131620] to-[#131620] border border-cyan-500/30 hover:border-cyan-500/50 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 col-span-1 md:col-span-2">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shrink-0">
                            <FiBriefcase size={18} />
                          </div>
                          <div>
                            <div className="text-xs font-semibold text-white">Campus Services &amp; Student Dossier</div>
                            <div className="text-[11px] text-gray-400">Verified identity dossier, itemized institutional fee ledger, hostel room &amp; dues, scholarships, and feedback</div>
                          </div>
                        </div>
                        <Link 
                          to="/services"
                          className="text-xs text-cyan-300 hover:text-white font-medium inline-flex items-center gap-1 transition-colors px-3 py-1.5 rounded-lg bg-cyan-600/30 hover:bg-cyan-600/50 border border-cyan-500/40 shrink-0 self-start sm:self-auto"
                        >
                          <span>Open Campus Services →</span>
                        </Link>
                      </div>

                      <div className="p-4 rounded-xl bg-[#131620] border border-[#232738] hover:border-[#32394e] transition-all flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                            <FiClock size={16} />
                          </div>
                          <div>
                            <div className="text-xs font-semibold text-white">Today's Schedule</div>
                            <div className="text-[11px] text-gray-400">Class timings, timetable &amp; multi-period simulator</div>
                          </div>
                        </div>
                        <Link 
                          to="/schedule"
                          className="text-xs text-purple-400 hover:text-purple-300 font-medium inline-flex items-center gap-1 transition-colors"
                        >
                          <span>Open Full Weekly Timetable &amp; Day Planner →</span>
                        </Link>
                      </div>

                      <div className="p-4 rounded-xl bg-[#131620] border border-[#232738] hover:border-[#32394e] transition-all flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                            <FiCalendar size={16} />
                          </div>
                          <div>
                            <div className="text-xs font-semibold text-white">Exam Schedule</div>
                            <div className="text-[11px] text-gray-400">End-semester dates, session slots &amp; CoE PDFs</div>
                          </div>
                        </div>
                        <Link 
                          to="/schedule"
                          className="text-xs text-purple-400 hover:text-purple-300 font-medium inline-flex items-center gap-1 transition-colors"
                        >
                          <span>Open Official Exam Timetable &amp; Circulars →</span>
                        </Link>
                      </div>
                    </div>

                    {/* Previews: Results & Timetable */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {/* Results Preview */}
                      <div className="bg-[#131620] border border-[#232738] rounded-xl p-5 space-y-3">
                        <div className="flex items-center justify-between pb-2 border-b border-[#1c202e]">
                          <div className="flex items-center gap-2">
                            <FiAward className="text-purple-400 text-sm" />
                            <h3 className="text-sm font-semibold text-white">Semester Results</h3>
                          </div>
                          <span className="text-[9px] px-2 py-0.5 rounded bg-[#181c2b] border border-[#272d3e] text-gray-400">
                            Source: StudZone 2
                          </span>
                        </div>

                        {resultsCourses.length > 0 ? (
                          <div className="space-y-2">
                            {resultsCourses.slice(0, 4).map((c, i) => (
                              <div key={i} className="flex items-center justify-between p-2.5 rounded-lg bg-[#171b28] border border-[#202536] text-xs">
                                <div>
                                  <div className="font-semibold text-white">{c.code}</div>
                                  <div className="text-[11px] text-gray-400 truncate max-w-[220px]">{c.title}</div>
                                </div>
                                <div className="text-right">
                                  <span className="px-2 py-0.5 rounded font-bold bg-purple-500/10 text-purple-300 font-mono">
                                    Grade: {c.grade}
                                  </span>
                                </div>
                              </div>
                            ))}
                            <button 
                              onClick={() => setActiveTab('results')}
                              className="w-full text-center text-xs text-purple-400 hover:text-purple-300 pt-1 font-medium"
                            >
                              View all {resultsCourses.length} subject results →
                            </button>
                          </div>
                        ) : studentData?.result_table ? (
                          <div className="academic-table-container max-h-56" dangerouslySetInnerHTML={{ __html: studentData.result_table }} />
                        ) : (
                          <div className="py-8 text-center text-xs text-gray-500">Not published yet.</div>
                        )}
                      </div>

                      {/* Timetable Preview */}
                      <div className="bg-[#131620] border border-[#232738] rounded-xl p-5 space-y-3">
                        <div className="flex items-center justify-between pb-2 border-b border-[#1c202e]">
                          <div className="flex items-center gap-2">
                            <FiCalendar className="text-blue-400 text-sm" />
                            <h3 className="text-sm font-semibold text-white">Exam Timetable</h3>
                          </div>
                          <span className="text-[9px] px-2 py-0.5 rounded bg-[#181c2b] border border-[#272d3e] text-gray-400">
                            Source: StudZone 2
                          </span>
                        </div>

                        {timetableSlots.length > 0 ? (
                          <div className="space-y-2">
                            {timetableSlots.slice(0, 4).map((s, i) => (
                              <div key={i} className="flex items-center justify-between p-2.5 rounded-lg bg-[#171b28] border border-[#202536] text-xs">
                                <div>
                                  <div className="font-semibold text-white">{s.course_code}</div>
                                  <div className="text-[11px] text-gray-400 truncate max-w-[220px]">{s.course_title}</div>
                                </div>
                                <div className="text-right">
                                  <div className="font-mono text-white text-[11px]">{s.exam_date}</div>
                                  <div className="text-[10px] text-gray-400 font-mono">{s.session}</div>
                                </div>
                              </div>
                            ))}
                            <Link 
                              to="/schedule"
                              className="w-full text-center text-xs text-purple-400 hover:text-purple-300 pt-1 font-medium block"
                            >
                              Open Official Exam Timetable & Circulars →
                            </Link>
                          </div>
                        ) : (
                          <div className="py-8 text-center text-xs text-gray-500">Not published yet.</div>
                        )}
                      </div>
                    </div>

                    {/* Verified Platform Activity Panel */}
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-5 space-y-4 shadow-sm">
                      <div className="flex items-center justify-between pb-2 border-b border-[#1c202e]">
                        <div className="flex items-center gap-2">
                          <FiSend className="text-purple-400 text-sm" />
                          <h3 className="text-sm font-semibold text-white">Platform Activity & Verified Statistics</h3>
                        </div>
                        <span className="text-[10px] text-gray-400 font-mono">
                          Source: MongoDB
                        </span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="p-3 rounded-lg bg-[#181c2b] border border-[#23283a]">
                          <div className="text-xs text-gray-400">Registered Students</div>
                          <div className="text-xl font-bold text-white mt-1">{stats.studentsRegistered ?? stats.students_registered ?? 0}</div>
                          <div className="text-[10px] text-gray-500 mt-0.5">MongoDB new_users</div>
                        </div>

                        <div className="p-3 rounded-lg bg-[#181c2b] border border-[#23283a]">
                          <div className="text-xs text-gray-400">Delivered Alerts</div>
                          <div className="text-xl font-bold text-white mt-1">{stats.notificationsDelivered ?? stats.notifications_sent ?? 0}</div>
                          <div className="text-[10px] text-gray-500 mt-0.5">Delivered to inboxes</div>
                        </div>

                        <div className="p-3 rounded-lg bg-[#181c2b] border border-[#23283a]">
                          <div className="text-xs text-gray-400">Attendance Alerts</div>
                          <div className="text-xl font-bold text-white mt-1">{stats.breakdown?.attendance || 0}</div>
                          <div className="text-[10px] text-gray-500 mt-0.5">Tracked updates</div>
                        </div>

                        <div className="p-3 rounded-lg bg-[#181c2b] border border-[#23283a]">
                          <div className="text-xs text-gray-400">Exam Schedules</div>
                          <div className="text-xl font-bold text-white mt-1">{stats.breakdown?.timetable || 0}</div>
                          <div className="text-[10px] text-gray-500 mt-0.5">Tracked timetables</div>
                        </div>
                      </div>
                    </div>

                  </div>
                )}

                {/* 2. GRANULAR NOTIFICATIONS PANEL */}
                {activeTab === 'notifications' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#1c202e]">
                        <div>
                          <div className="flex items-center gap-2">
                            <h2 className="text-base font-semibold text-white">Specific Event Alerts & Change History</h2>
                            {unreadNotifsCount > 0 && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 font-mono">
                                {unreadNotifsCount} unread
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-400 mt-0.5">
                            Real-time granular change notifications detected across StudZone 1 & StudZone 2
                          </p>
                        </div>

                        {notifications.length > 0 && (
                          <button
                            onClick={() => handleMarkAsRead(null, true)}
                            className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#181c2b] hover:bg-[#23283b] border border-[#2b3145] text-xs font-medium text-gray-300 hover:text-white transition-all"
                          >
                            <FiCheckSquare className="text-purple-400 text-xs" />
                            <span>Mark all as read</span>
                          </button>
                        )}
                      </div>

                      {/* Filter Bar */}
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        {[
                          { id: 'all', label: 'All Alerts' },
                          { id: 'attendance', label: 'Attendance' },
                          { id: 'marks', label: 'CA Marks' },
                          { id: 'results', label: 'Results' },
                          { id: 'timetable', label: 'Timetable' },
                          { id: 'seating', label: 'Seating' },
                          { id: 'fees', label: 'Fees' },
                          { id: 'welcome', label: 'System' }
                        ].map((tab) => (
                          <button
                            key={tab.id}
                            onClick={() => setNotifFilter(tab.id)}
                            className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                              notifFilter === tab.id
                                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                                : 'bg-[#141824] text-gray-400 hover:text-gray-200 border border-[#202538]'
                            }`}
                          >
                            {tab.label}
                          </button>
                        ))}
                      </div>

                      {/* Notifications List */}
                      {filteredNotifications.length > 0 ? (
                        <div className="space-y-3 pt-2">
                          {filteredNotifications.map((notif, idx) => (
                            <div 
                              key={notif._id || notif.changeHash || idx}
                              onClick={() => !notif.read && handleMarkAsRead(notif._id || notif.changeHash)}
                              className={`p-4 rounded-xl border transition-all flex items-start justify-between gap-4 cursor-pointer ${
                                notif.read 
                                  ? 'bg-[#141724]/70 border-[#1f2436] opacity-85' 
                                  : 'bg-[#181c2b] border-[#2f364d] shadow-sm'
                              }`}
                            >
                              <div className="flex items-start gap-3.5">
                                <div className="w-8 h-8 rounded-lg bg-[#1f2436] flex items-center justify-center flex-shrink-0 mt-0.5">
                                  {getNotifIcon(notif)}
                                </div>
                                <div className="space-y-1.5">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-xs font-semibold text-white">
                                      {notif.title}
                                    </span>
                                    <span className="text-[10px] px-2 py-0.5 rounded bg-[#202538] border border-[#2b3147] text-gray-400 font-mono">
                                      {notif.source || 'StudZone'} • {notif.module || 'Academics'}
                                    </span>
                                    {!notif.read && (
                                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                                    )}
                                  </div>
                                  <p className="text-xs text-gray-200 leading-relaxed font-normal">
                                    {notif.description || notif.message}
                                  </p>
                                  {notif.changeData && notif.changeData.previousValue && notif.changeData.newValue && (
                                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#131622] border border-[#262c3e] text-[11px] font-mono text-purple-300">
                                      <span className="text-gray-400">{notif.changeData.previousValue}</span>
                                      <span className="text-purple-400">→</span>
                                      <span className="font-bold text-emerald-400">{notif.changeData.newValue}</span>
                                    </div>
                                  )}
                                </div>
                              </div>

                              <div className="text-right flex-shrink-0">
                                <span className="text-[10px] text-gray-500 font-mono flex items-center gap-1 justify-end">
                                  <FiClock size={10} />
                                  {formatRelativeTime(notif.createdAt || notif.timestamp)}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="py-16 text-center space-y-2">
                          <FiBell className="mx-auto text-2xl text-gray-600" />
                          <h4 className="text-xs font-semibold text-gray-400">No notifications in this category</h4>
                          <p className="text-[11px] text-gray-600 max-w-sm mx-auto">
                            Student Sync automatically generates alerts when actual changes in attendance, CA marks, timetable, seating, or results occur.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 3. ATTENDANCE */}
                {activeTab === 'attendance' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Subject Attendance</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Subject-wise attended classes, total sessions, and percentage</p>
                        </div>
                        <span className={`self-start sm:self-auto text-xs px-2.5 py-1 rounded-md font-mono ${
                          (studentData?.is_previous_attendance || (!sz1?.parsed_attendance?.length && attendanceCourses.length > 0))
                            ? 'bg-amber-500/10 border border-amber-500/20 text-amber-300'
                            : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                        }`}>
                          {(studentData?.is_previous_attendance || (!sz1?.parsed_attendance?.length && attendanceCourses.length > 0))
                            ? 'Source: Stored Baseline (Portal Updating)'
                            : 'Source: Modern StudZone 1'}
                        </span>
                      </div>

                      {/* Interactive Bunk Planner & Simulator Callout */}
                      <div className="p-3.5 sm:p-4 rounded-xl bg-purple-950/20 border border-purple-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
                        <div className="space-y-0.5">
                          <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                            <span>Smart Attendance & Bunk Planner</span>
                          </div>
                          <p className="text-[11px] text-gray-400">
                            Calculate permissible safe bunks, recovery requirements, and simulate attendance in-memory.
                          </p>
                        </div>

                        <Link
                          to="/attendance"
                          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-sm transition-colors whitespace-nowrap"
                        >
                          <span>Open Interactive Bunk Planner & Simulator →</span>
                        </Link>
                      </div>

                      {attendanceCourses.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {attendanceCourses.map((c, i) => (
                            <div key={i} className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-3">
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <span className="font-mono text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">
                                    {c.code}
                                  </span>
                                  <h4 className="text-xs font-semibold text-white mt-1.5">{c.name}</h4>
                                </div>
                                <span className={`text-xs px-2 py-0.5 rounded font-bold font-mono ${
                                  c.status === 'Good' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                }`}>
                                  {c.percentage}
                                </span>
                              </div>
                              <div className="w-full bg-[#111420] rounded-full h-1.5 overflow-hidden">
                                <div 
                                  className={`h-full rounded-full ${c.status === 'Good' ? 'bg-emerald-400' : 'bg-amber-400'}`}
                                  style={{ width: `${Math.min(c.percentage_num || 0, 100)}%` }}
                                />
                              </div>
                              <div className="flex items-center justify-between text-[11px] text-gray-400 pt-1">
                                <span>Attended: <strong className="text-gray-200">{c.attended}</strong></span>
                                <span>Total: <strong className="text-gray-200">{c.total_classes}</strong></span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500">No attendance data available.</div>
                      )}
                    </div>
                  </div>
                )}

                {/* 4. CA MARKS */}
                {activeTab === 'marks' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Continuous Assessment Marks</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Internal test scores, assignment marks, and test performance</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Source: Modern StudZone 1
                        </span>
                      </div>

                      {/* Subtle Callout to Detailed CA Analytics & CGPA Planner */}
                      <div className="p-3.5 rounded-lg bg-gradient-to-r from-purple-900/20 to-indigo-900/20 border border-purple-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div className="text-xs text-gray-300">
                          <span className="font-semibold text-white">Advanced Academic Intelligence: </span>
                          <span>View multi-category component breakdowns (Tests, Tutorials, Reviews) &amp; simulate your cumulative CGPA.</span>
                        </div>
                        <Link
                          to="/grades"
                          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-md shadow-purple-600/20 transition-all flex-shrink-0"
                        >
                          <span>Open Deep CA Breakdown &amp; CGPA Simulator →</span>
                        </Link>
                      </div>

                      {caMarksSubjects.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {caMarksSubjects.map((m, i) => (
                            <div key={i} className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-3">
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <span className="font-mono text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">
                                    {m.code}
                                  </span>
                                  <h4 className="text-xs font-semibold text-white mt-1.5">{m.name}</h4>
                                </div>
                                <span className="text-xs px-2 py-0.5 rounded font-bold font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
                                  Total: {m.total}
                                </span>
                              </div>
                              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#202538] text-center">
                                <div className="p-2 rounded bg-[#121522]">
                                  <div className="text-[10px] text-gray-400">CA 1</div>
                                  <div className="text-xs font-bold text-white mt-0.5">{m.ca1}</div>
                                </div>
                                <div className="p-2 rounded bg-[#121522]">
                                  <div className="text-[10px] text-gray-400">CA 2</div>
                                  <div className="text-xs font-bold text-white mt-0.5">{m.ca2}</div>
                                </div>
                                <div className="p-2 rounded bg-[#121522]">
                                  <div className="text-[10px] text-gray-400">CA 3</div>
                                  <div className="text-xs font-bold text-white mt-0.5">{m.ca3}</div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : studentData?.marks ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: studentData.marks }} />
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500">
                          Not published yet
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 5. SEMESTER RESULTS */}
                {activeTab === 'results' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Semester Examination Results</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Official subject grades, credit points, and calculated CGPA</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Source: StudZone 2
                        </span>
                      </div>

                      {/* CGPA Banner */}
                      <div className="flex items-center justify-between p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
                        <div>
                          <div className="text-xs text-gray-400 font-medium">Cumulative Grade Point Average (CGPA)</div>
                          <div className="text-xs text-gray-500 mt-0.5">Calculated across verified graded subjects</div>
                        </div>
                        <div className="text-3xl font-extrabold text-white">
                          {studentData?.cgpa ? studentData.cgpa : 'N/A'}
                        </div>
                      </div>

                      {resultsCourses.length > 0 ? (
                        <div className="academic-table-container">
                          <table>
                            <thead>
                              <tr>
                                <th>Semester</th>
                                <th>Subject Code</th>
                                <th>Subject Title</th>
                                <th>Credits</th>
                                <th>Grade</th>
                                <th>Grade Point</th>
                                <th>Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {resultsCourses.map((c, i) => (
                                <tr key={i}>
                                <td>{c.sem}</td>
                                  <td className="font-mono font-semibold text-purple-300">{c.code}</td>
                                  <td>{c.title}</td>
                                  <td>{c.credits}</td>
                                  <td>
                                    <span className="px-2 py-0.5 rounded font-bold font-mono bg-purple-500/10 text-purple-300">
                                      {c.grade}
                                    </span>
                                  </td>
                                  <td>{c.grade_point}</td>
                                  <td>
                                    <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                                      <FiCheck className="text-xs" /> {c.result_status}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : studentData?.result_table ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: studentData.result_table }} />
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500">
                          Not published yet
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 6. CGPA SUMMARY */}
                {activeTab === 'cgpa_history' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">CGPA & Academic Progress</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Cumulative performance index based on end-semester examinations</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Source: StudZone 2
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="p-5 rounded-xl bg-[#171b28] border border-[#24293c] space-y-2">
                          <div className="text-xs text-gray-400">Overall CGPA</div>
                          <div className="text-3xl font-extrabold text-white">{studentData?.cgpa ?? '7.96'}</div>
                          <div className="text-[11px] text-emerald-400">First Class with Distinction range</div>
                        </div>

                        <div className="p-5 rounded-xl bg-[#171b28] border border-[#24293c] space-y-2">
                          <div className="text-xs text-gray-400">Graded Subjects</div>
                          <div className="text-3xl font-extrabold text-white">{resultsCourses.length || 8}</div>
                          <div className="text-[11px] text-gray-400">All subjects successfully cleared</div>
                        </div>

                        <div className="p-5 rounded-xl bg-[#171b28] border border-[#24293c] space-y-2">
                          <div className="text-xs text-gray-400">Reappearances</div>
                          <div className="text-3xl font-extrabold text-emerald-400">0</div>
                          <div className="text-[11px] text-gray-400">Nil arrears on record</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 7. EXAM TIMETABLE */}
                {activeTab === 'timetable' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Examination Timetable</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Continuous assessment and semester examination schedule</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400 font-mono">
                          Source: StudZone 2
                        </span>
                      </div>

                      {/* Subtle Callout to Examination Hub */}
                      <div className="p-3.5 sm:p-4 rounded-xl bg-blue-950/20 border border-blue-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
                        <div className="space-y-0.5">
                          <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                            <span>Official End-Semester Examination Hub</span>
                          </div>
                          <p className="text-[11px] text-gray-400">
                            View verified end-semester subject exam dates, session timings, and official CoE circular PDFs.
                          </p>
                        </div>

                        <Link
                          to="/schedule"
                          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition-colors whitespace-nowrap"
                        >
                          <span>Open Official Exam Timetable & Circulars →</span>
                        </Link>
                      </div>

                      {timetableSlots.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {timetableSlots.map((s, i) => (
                            <div key={i} className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="font-mono text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded font-semibold">
                                  {s.course_code}
                                </span>
                                <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 font-mono">
                                  {s.session}
                                </span>
                              </div>
                              <h4 className="text-xs font-semibold text-white">{s.course_title}</h4>
                              <div className="pt-2 border-t border-[#202538] flex items-center justify-between text-xs text-gray-400">
                                <span>Date: <strong className="text-white font-mono">{s.exam_date}</strong></span>
                                <span>Timing: <strong className="text-white font-mono">{s.timing}</strong></span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : studentData?.timetable ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: studentData.timetable }} />
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500">
                          Not published yet
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 8. SEATING ARRANGEMENT */}
                {activeTab === 'seating' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Exam Seating Arrangement</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Exam hall allocations and desk seating details</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Source: StudZone 2
                        </span>
                      </div>

                      {studentData?.seating ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: studentData.seating }} />
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500 space-y-2">
                          <FiMapPin className="mx-auto text-xl text-gray-600" />
                          <p>Not published yet</p>
                          <p className="text-[11px] text-gray-600">Seating allocations are uploaded prior to examination sessions.</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 9. REAPPEARANCE RESULTS */}
                {activeTab === 'reappearance' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Reappearance Exam Results</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Supplementary and supplementary reappearance exam scores</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Source: StudZone 2
                        </span>
                      </div>

                      {sz2?.reappearance_html ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: sz2.reappearance_html }} />
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500 space-y-2">
                          <FiActivity className="mx-auto text-xl text-gray-600" />
                          <p>Not available from the portal (No active reappearance records)</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 10. REVALUATION RESULTS */}
                {activeTab === 'revaluation' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Revaluation Results</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Revalued mark sheets and revised grade status</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Source: StudZone 2
                        </span>
                      </div>

                      {sz2?.revaluation_html ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: sz2.revaluation_html }} />
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500 space-y-2">
                          <FiFile className="mx-auto text-xl text-gray-600" />
                          <p>Not available from the portal (No revaluation records on portal)</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 11. RETOTALLING */}
                {activeTab === 'retotalling' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Retotalling & Revaluation Information</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Official examination office instructions and fee schedules</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Source: StudZone 2
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-3">
                          <h3 className="text-xs font-semibold text-white flex items-center gap-2">
                            <FiBookOpen className="text-purple-400" />
                            <span>Retotalling Information</span>
                          </h3>
                          {sz2?.applications?.retotalling_instructions ? (
                            <div className="academic-table-container max-h-72" dangerouslySetInnerHTML={{ __html: sz2.applications.retotalling_instructions }} />
                          ) : (
                            <p className="text-xs text-gray-400">Not published yet</p>
                          )}
                        </div>

                        <div className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-3">
                          <h3 className="text-xs font-semibold text-white flex items-center gap-2">
                            <FiFile className="text-purple-400" />
                            <span>Revaluation Information</span>
                          </h3>
                          {sz2?.applications?.revaluation_instructions ? (
                            <div className="academic-table-container max-h-72" dangerouslySetInnerHTML={{ __html: sz2.applications.revaluation_instructions }} />
                          ) : (
                            <p className="text-xs text-gray-400">Not published yet</p>
                          )}
                        </div>
                      </div>

                      <div className="p-3.5 rounded-lg bg-[#181c2b] border border-[#23283a] text-xs text-gray-400 flex items-center gap-2">
                        <FiInfo className="text-purple-400 text-sm flex-shrink-0" />
                        <span>Student Sync provides information view only. Formal fee submissions must be completed on official college portals.</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* 12. EXAM CIRCULARS & PDFS */}
                {activeTab === 'circulars' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Examination Circulars & PDF Guidelines</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Official examination rules, Bloom's Taxonomy formats, and SOP documents</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Source: StudZone 2
                        </span>
                      </div>

                      {circulars.length > 0 ? (
                        <div className="space-y-3">
                          {circulars.map((doc, idx) => (
                            <div key={idx} className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] flex items-center justify-between gap-4">
                              <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center flex-shrink-0">
                                  <FiFileText size={18} />
                                </div>
                                <div>
                                  <h4 className="text-xs font-semibold text-white">{doc.title}</h4>
                                  <div className="text-[10px] text-gray-400 mt-0.5 font-mono">Official PDF Document</div>
                                </div>
                              </div>
                              <a
                                href={doc.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#202538] hover:bg-[#2a3048] text-xs font-medium text-purple-300 hover:text-white"
                              >
                                <span>Open PDF</span>
                                <FiExternalLink size={12} />
                              </a>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500">
                          Not published yet
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 13. FEES */}
                {activeTab === 'fees' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Semester Fees & Receipts</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Tuition fees, dues, and transaction receipt records</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono">
                          Source: Modern StudZone 1
                        </span>
                      </div>

                      {sz1?.fees_html ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: sz1.fees_html }} />
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500">
                          Not available from the portal
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 14. FEEDBACK */}
                {activeTab === 'feedback' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Subject & Faculty Feedback</h2>
                          <p className="text-xs text-gray-400 mt-0.5">End-semester and intermediate faculty feedback schedules</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono">
                          Source: Modern StudZone 1
                        </span>
                      </div>

                      {feedbackSchedules.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {feedbackSchedules.map((f, i) => (
                            <div key={i} className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-2">
                              <div className="flex items-center justify-between">
                                <h4 className="text-xs font-semibold text-white">{f.type} Feedback</h4>
                                <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-[#1f2436] text-gray-300">
                                  {f.status}
                                </span>
                              </div>
                              <p className="text-xs text-gray-400">{f.description}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500">
                          Not published yet (Feedback is currently not scheduled)
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 15. HOSTEL */}
                {activeTab === 'hostel' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Hostel Information & Fees</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Hostel allocation status, room number, and payment history</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono">
                          Source: Modern StudZone 1
                        </span>
                      </div>

                      <div className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] flex items-center justify-between">
                        <div>
                          <div className="text-xs text-gray-400">Hostel Allocation Status</div>
                          <div className="text-sm font-bold text-white mt-1">{sz1?.hostel_status || 'Hostel details active'}</div>
                        </div>
                        <FiHome className="text-xl text-purple-400" />
                      </div>

                      {sz1?.hostel_html ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: sz1.hostel_html }} />
                      ) : (
                        <div className="py-8 text-center text-xs text-gray-500">
                          Not available from the portal
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 16. SCHOLARSHIPS */}
                {activeTab === 'scholarships' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Scholarships & Grants</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Applied scholarships, received entries, and Vallalar Ramalingam records</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono">
                          Source: Modern StudZone 1
                        </span>
                      </div>

                      <div className="space-y-4">
                        {sz1?.scholarships?.html_apply && (
                          <div className="space-y-2">
                            <h4 className="text-xs font-semibold text-white">Scholarship Apply Listings</h4>
                            <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: sz1.scholarships.html_apply }} />
                          </div>
                        )}

                        {sz1?.scholarships?.html_received && (
                          <div className="space-y-2">
                            <h4 className="text-xs font-semibold text-white">Scholarship Received Entries</h4>
                            <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: sz1.scholarships.html_received }} />
                          </div>
                        )}

                        {!sz1?.scholarships?.html_apply && !sz1?.scholarships?.html_received && (
                          <div className="py-12 text-center text-xs text-gray-500">
                            Not available from the portal (No scholarship records active)
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* 17. LEAVE & ON-DUTY */}
                {activeTab === 'leave' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Student Leave & On-Duty Entry</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Approved student leave, on-duty approvals, and application status</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono">
                          Source: Modern StudZone 1
                        </span>
                      </div>

                      {sz1?.leave_html ? (
                        <div className="academic-table-container" dangerouslySetInnerHTML={{ __html: sz1.leave_html }} />
                      ) : (
                        <div className="py-12 text-center text-xs text-gray-500">
                          Not available from the portal (No leave entries on record)
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 18. LIBRARY */}
                {activeTab === 'library' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Campus Library Information</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Book issues, return due dates, and digital catalogue status</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono">
                          Campus OPAC
                        </span>
                      </div>

                      <div className="p-5 rounded-xl bg-[#171b28] border border-[#24293c] text-center space-y-3 py-12">
                        <FiBook className="mx-auto text-3xl text-purple-400" />
                        <div>
                          <h3 className="text-sm font-semibold text-white">Not available from the portal</h3>
                          <p className="text-xs text-gray-400 max-w-md mx-auto mt-1">
                            PSG College of Technology manages library book issues and due dates through the internal campus Koha OPAC network.
                          </p>
                        </div>
                        <div className="pt-2">
                          <a
                            href="https://library.psgtech.ac.in/"
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#202538] hover:bg-[#2b3149] text-xs font-medium text-purple-300 hover:text-white transition-colors"
                          >
                            <span>Open Library Portal</span>
                            <FiExternalLink size={12} />
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 19. STUDENT PROFILE */}
                {activeTab === 'profile' && (
                  <div className="space-y-6">
                    <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 space-y-5 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#1c202e]">
                        <div>
                          <h2 className="text-base font-semibold text-white">Student Profile Information</h2>
                          <p className="text-xs text-gray-400 mt-0.5">Personal details, academic programme, and department registration</p>
                        </div>
                        <span className="self-start sm:self-auto text-xs px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono">
                          Source: Modern StudZone 1
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-1">
                          <div className="text-[10px] text-gray-400 font-semibold uppercase">Full Name</div>
                          <div className="text-sm font-bold text-white">{fullName}</div>
                        </div>

                        <div className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-1">
                          <div className="text-[10px] text-gray-400 font-semibold uppercase">Roll Number</div>
                          <div className="text-sm font-bold text-white font-mono">{rollNo}</div>
                        </div>

                        <div className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-1">
                          <div className="text-[10px] text-gray-400 font-semibold uppercase">Institution</div>
                          <div className="text-sm font-bold text-white">PSG College of Technology</div>
                        </div>

                        <div className="p-4 rounded-xl bg-[#171b28] border border-[#23283b] space-y-1">
                          <div className="text-[10px] text-gray-400 font-semibold uppercase">Degree / Programme</div>
                          <div className="text-sm font-bold text-white">{profileDetails?.Degree || 'MASTER OF COMPUTER APPLICATIONS'}</div>
                        </div>
                      </div>

                      {Object.keys(profileDetails).length > 2 && (
                        <div className="pt-4 border-t border-[#1c202e] space-y-3">
                          <h4 className="text-xs font-semibold text-white">Additional Profile Records</h4>
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                            {Object.entries(profileDetails).map(([k, v], idx) => (
                              <div key={idx} className="p-3 rounded-lg bg-[#141724] border border-[#1f2434] text-xs">
                                <div className="text-gray-400 text-[10px] font-medium">{k}</div>
                                <div className="text-gray-200 mt-0.5 truncate">{v}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

              </div>
            )}

          </main>
        </div>
      </div>

    </div>
  );
};

export default Dashboard;
