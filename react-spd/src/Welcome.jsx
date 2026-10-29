import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { 
  FiBell, 
  FiUser, 
  FiCheck, 
  FiLayers, 
  FiLogOut, 
  FiCalendar, 
  FiFileText, 
  FiMapPin, 
  FiAward, 
  FiCheckCircle, 
  FiAlertCircle,
  FiMail,
  FiRefreshCw
} from 'react-icons/fi';

const Welcome = () => {
  const location = useLocation();
  const navigate = useNavigate();
  
  const storedUser = localStorage.getItem('student_sync_user');
  const initialData = location.state || (storedUser ? JSON.parse(storedUser) : { rollNo: '', name: '', notifications: {} });

  const [profile, setProfile] = useState(initialData);
  const [mainNotificationsEnabled, setMainNotificationsEnabled] = useState(true);
  const [notificationPreferences, setNotificationPreferences] = useState({
    attendance: true,
    marks: true,
    timetable: true,
    seatingArrangement: true,
    results: true,
    fees: true,
    hostel: true
  });
  const [saveStatus, setSaveStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [resendingWelcome, setResendingWelcome] = useState(false);
  const [welcomeStatus, setWelcomeStatus] = useState(null);

  useEffect(() => {
    if (!profile.rollNo) {
      navigate('/login');
      return;
    }

    const fetchPreferences = async () => {
      try {
        setLoading(true);
        const storedUser = JSON.parse(localStorage.getItem('student_sync_user') || '{}');
        const token = profile.auth_token || storedUser.auth_token;
        const headers = { 'Content-Type': 'application/json', ...(token ? { 'Authorization': `Bearer ${token}` } : {}) };
        const response = await fetch(`/api/profile?rollNo=${profile.rollNo}`, {
          method: 'GET',
          headers,
        });

        if (response.ok) {
          const data = await response.json();
          setProfile(data);
          localStorage.setItem('student_sync_user', JSON.stringify(data));
          
          if (data.notifications) {
            setNotificationPreferences({
              attendance: data.notifications.attendance ?? true,
              marks: data.notifications.marks ?? true,
              timetable: data.notifications.timetable ?? true,
              seatingArrangement: data.notifications.seatingArrangement ?? true,
              results: data.notifications.results ?? true,
              fees: data.notifications.fees ?? true,
              hostel: data.notifications.hostel ?? true
            });
            
            const anyEnabled = Object.values(data.notifications).some(val => val === true);
            setMainNotificationsEnabled(anyEnabled);
          }
        }
      } catch (err) {
        console.error('Error fetching notification preferences:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPreferences();
  }, [profile.rollNo]);

  const handleMainToggle = async () => {
    const newState = !mainNotificationsEnabled;
    setMainNotificationsEnabled(newState);
    
    const updatedPreferences = {
      attendance: newState,
      marks: newState,
      timetable: newState,
      seatingArrangement: newState,
      results: newState,
      fees: newState,
      hostel: newState
    };
    
    setNotificationPreferences(updatedPreferences);
    await savePreferences(updatedPreferences);
  };

  const handlePreferenceChange = async (key) => {
    const updatedPreferences = {
      ...notificationPreferences,
      [key]: !notificationPreferences[key]
    };
    
    setNotificationPreferences(updatedPreferences);
    
    const anyEnabled = Object.values(updatedPreferences).some(val => val === true);
    setMainNotificationsEnabled(anyEnabled);
    
    await savePreferences(updatedPreferences);
  };

  const savePreferences = async (preferences) => {
    try {
      setSaveStatus('Saving...');
      const anyEnabled = Object.values(preferences).some(val => val === true);
      const storedUser = JSON.parse(localStorage.getItem('student_sync_user') || '{}');
      const token = profile.auth_token || storedUser.auth_token;
      const headers = { 'Content-Type': 'application/json', ...(token ? { 'Authorization': `Bearer ${token}` } : {}) };
      const response = await fetch('/api/notifications', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          rollNo: profile.rollNo,
          notifications: preferences,
          monitoring_enabled: anyEnabled
        }),
      });

      if (response.ok) {
        setSaveStatus('Saved');
        setTimeout(() => setSaveStatus(''), 2000);
      } else {
        setSaveStatus('Failed to save');
      }
    } catch (err) {
      console.error('Error saving notification preferences:', err);
      setSaveStatus('Connection error');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('student_sync_user');
    navigate('/', { replace: true });
  };

  const handleResendWelcome = async () => {
    if (!profile.rollNo) return;
    setResendingWelcome(true);
    setWelcomeStatus(null);
    try {
      const response = await fetch('/api/resend-welcome', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rollNo: profile.rollNo,
          email: profile.email
        })
      });
      const data = await response.json();
      if (response.ok) {
        setWelcomeStatus({
          type: 'success',
          text: `Welcome mail sent to ${data.email || profile.email}!`
        });
      } else {
        setWelcomeStatus({
          type: 'error',
          text: data.error || 'Failed to send welcome email.'
        });
      }
    } catch (err) {
      setWelcomeStatus({
        type: 'error',
        text: 'Network error connecting to mail server.'
      });
    } finally {
      setResendingWelcome(false);
    }
  };

  const fullName = profile.name && profile.name !== profile.rollNo 
    ? profile.name 
    : (profile.rollNo || 'Student');

  const notificationItems = [
    {
      key: 'attendance',
      label: 'Attendance Alerts',
      description: 'Receive notifications when subject attendance drops or updates.',
      icon: <FiCheckCircle className="text-emerald-400" />
    },
    {
      key: 'marks',
      label: 'Mark Updates',
      description: 'Get notified when new continuous assessment marks are published.',
      icon: <FiFileText className="text-purple-400" />
    },
    {
      key: 'timetable',
      label: 'Timetable Changes',
      description: 'Stay informed about examination schedule and slot updates.',
      icon: <FiCalendar className="text-blue-400" />
    },
    {
      key: 'seatingArrangement',
      label: 'Seating Arrangements',
      description: 'Receive examination hall and desk room numbers prior to tests.',
      icon: <FiMapPin className="text-rose-400" />
    },
    {
      key: 'results',
      label: 'Results & CGPA',
      description: 'Get notified as soon as end-semester grades and CGPA are out.',
      icon: <FiAward className="text-amber-400" />
    },
    {
      key: 'fees',
      label: 'Fee Updates & Receipts',
      description: 'Get alerts when new semester tuition fees or exam dues are uploaded.',
      icon: <FiFileText className="text-emerald-400" />
    },
    {
      key: 'hostel',
      label: 'Hostel & Campus Alerts',
      description: 'Stay notified on hostel room allocations and mess updates.',
      icon: <FiUser className="text-indigo-400" />
    }
  ];

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] px-4 sm:px-6 lg:px-8 pt-24 pb-16">
      <div className="max-w-4xl mx-auto space-y-6">
        
        {/* Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#1c202e]">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Notification Settings</h1>
            <p className="text-xs text-gray-400 mt-1">Choose which academic updates you want to receive</p>
          </div>

          <div className="flex items-center gap-3">
            {saveStatus && (
              <span className={`text-xs px-2.5 py-1 rounded-md ${
                saveStatus === 'Saved' 
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                  : 'bg-white/5 text-gray-400'
              }`}>
                {saveStatus}
              </span>
            )}
            <Link
              to="/dashboard"
              state={profile}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#141722] hover:bg-[#1a1e2c] border border-[#232738] text-xs font-medium text-purple-300 hover:text-white transition-colors"
            >
              <FiLayers className="text-xs" />
              <span>Academic Dashboard</span>
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Student Profile Summary Card */}
          <div className="bg-[#131620] border border-[#232738] rounded-xl p-5 space-y-5 h-fit">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-lg font-bold text-purple-300">
                {fullName.charAt(0)}
              </div>
              <div className="overflow-hidden">
                <h3 className="text-sm font-semibold text-white truncate">{fullName}</h3>
                <p className="font-mono text-xs text-gray-400">{profile.rollNo}</p>
              </div>
            </div>

            <div className="space-y-2 pt-3 border-t border-[#1c202e] text-xs">
              <div className="flex justify-between items-center text-gray-400">
                <span>Account Status</span>
                <span className="text-emerald-400 font-medium flex items-center gap-1">
                  <FiCheck className="text-xs" /> Active
                </span>
              </div>
              <div className="flex justify-between items-center text-gray-400">
                <span>Institution</span>
                <span className="text-gray-300">PSG Tech</span>
              </div>
            </div>

            <div className="space-y-2 pt-3 border-t border-[#1c202e] text-xs">
              <div className="flex justify-between items-center text-gray-400">
                <span className="flex items-center gap-1">
                  <FiMail className="text-xs text-purple-400" />
                  Alert Email
                </span>
                <span className="text-emerald-400 text-[10px]">Verified</span>
              </div>
              <div className="font-mono text-[11px] text-white bg-[#0b0d13] p-2 rounded border border-[#272c3d] break-all">
                {profile.email || (profile.rollNo ? `${profile.rollNo.toLowerCase()}@psgtech.ac.in` : 'Email')}
              </div>
              <button
                type="button"
                onClick={handleResendWelcome}
                disabled={resendingWelcome}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 text-xs font-medium text-purple-300 hover:text-white transition-colors disabled:opacity-50"
              >
                <FiRefreshCw className={`text-xs ${resendingWelcome ? 'animate-spin' : ''}`} />
                <span>{resendingWelcome ? 'Dispatching...' : 'Resend Welcome Email'}</span>
              </button>
              {welcomeStatus && (
                <p className={`text-[11px] mt-1 text-center ${welcomeStatus.type === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {welcomeStatus.text}
                </p>
              )}
            </div>

            <div className="pt-2">
              <button
                onClick={handleLogout}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-xs font-medium text-red-400 transition-colors"
              >
                <FiLogOut className="text-xs" />
                <span>Logout</span>
              </button>
            </div>
          </div>

          {/* Preferences Settings List */}
          <div className="md:col-span-2 space-y-4">
            
            {/* Master Toggle */}
            <div className="bg-[#131620] border border-[#232738] rounded-xl p-5 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">All Academic Notifications</h3>
                <p className="text-xs text-gray-400 mt-0.5">Master toggle for email alerts & notifications</p>
              </div>
              
              <button
                type="button"
                onClick={handleMainToggle}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                  mainNotificationsEnabled ? 'bg-purple-600' : 'bg-[#272c3d]'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    mainNotificationsEnabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Individual Notification Items */}
            <div className="bg-[#131620] border border-[#232738] rounded-xl divide-y divide-[#1c202e] overflow-hidden">
              {notificationItems.map((item) => (
                <div key={item.key} className="p-4 sm:p-5 flex items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-[#191d2a] border border-[#242938] text-sm mt-0.5">
                      {item.icon}
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-white">{item.label}</h4>
                      <p className="text-xs text-gray-400 mt-0.5">{item.description}</p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handlePreferenceChange(item.key)}
                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                      notificationPreferences[item.key] ? 'bg-purple-600' : 'bg-[#272c3d]'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        notificationPreferences[item.key] ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
              ))}
            </div>

          </div>

        </div>

      </div>
    </div>
  );
};

export default Welcome;
