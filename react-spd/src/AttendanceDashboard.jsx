import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { 
  FiRefreshCw, 
  FiAlertCircle, 
  FiAlertTriangle, 
  FiCheckCircle, 
  FiCalendar, 
  FiClock, 
  FiBookOpen, 
  FiSliders,
  FiLogIn,
  FiArrowLeft
} from 'react-icons/fi';

import AttendanceOverview from './components/attendance/AttendanceOverview';
import TodaySchedule from './components/attendance/TodaySchedule';
import SubjectAttendanceCard from './components/attendance/SubjectAttendanceCard';
import BunkPlanner from './components/attendance/BunkPlanner';
import AttendanceSimulator from './components/attendance/AttendanceSimulator';

const AttendanceDashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // State management
  const [currentUser, setCurrentUser] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  const [target, setTarget] = useState(75.0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorStatus, setErrorStatus] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [selectedSubjectCode, setSelectedSubjectCode] = useState('');

  // 1. Session and Identity Resolution
  useEffect(() => {
    const rawStored = localStorage.getItem('student_sync_user');
    let user = null;
    if (rawStored) {
      try {
        user = JSON.parse(rawStored);
      } catch (e) {
        user = null;
      }
    }

    // Support location.state fallback
    if (!user && location.state && location.state.rollNo) {
      user = location.state;
    }

    if (!user || (!user.rollNo && !user.auth_token)) {
      setLoading(false);
      setErrorStatus(401);
      setErrorMessage('Your session has expired. Please log in again to access attendance tracking.');
      return;
    }

    setCurrentUser(user);
  }, [location.state]);

  // 2. Fetch Attendance Summary from Backend API
  const fetchAttendanceSummary = async (currentTarget = target, isManualRefresh = false) => {
    if (isManualRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setErrorStatus(null);
    setErrorMessage('');

    const rawStored = localStorage.getItem('student_sync_user');
    let user = currentUser;
    if (!user && rawStored) {
      try { user = JSON.parse(rawStored); } catch(e){}
    }

    const authToken = user?.auth_token;
    const rollNo = user?.rollNo;

    try {
      const headers = {};
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      } else if (rollNo) {
        headers['X-Roll-No'] = rollNo;
      }

      // Fetch from API with target threshold parameter
      const apiUrl = `/api/attendance/summary?target=${currentTarget}${isManualRefresh ? '&refresh=true' : ''}`;
      const response = await fetch(apiUrl, { headers });

      if (response.status === 200) {
        const data = await response.json();
        setSummaryData(data);
        // Default selected subject to first enrolled subject if not set
        if (data.subjects && data.subjects.length > 0 && !selectedSubjectCode) {
          setSelectedSubjectCode(data.subjects[0].code);
        }
      } else if (response.status === 401) {
        setErrorStatus(401);
        setErrorMessage('Your session has expired. Please log in again.');
      } else if (response.status === 403) {
        setErrorStatus(403);
        setErrorMessage('You are not authorized to access this attendance data.');
      } else if (response.status === 404) {
        setErrorStatus(404);
        setErrorMessage('Attendance records for your roll number were not found.');
      } else {
        setErrorStatus(response.status || 500);
        setErrorMessage('Attendance data is temporarily unavailable.');
      }
    } catch (err) {
      console.error('Failed to load attendance summary:', err);
      setErrorStatus(500);
      setErrorMessage('Attendance data is temporarily unavailable.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Re-fetch when user is resolved or when target threshold changes
  useEffect(() => {
    if (currentUser) {
      fetchAttendanceSummary(target);
    }
  }, [currentUser, target]);

  const handleTargetChange = (newTarget) => {
    setTarget(newTarget);
  };

  const handleScrollToSimulator = (subjectCode = null) => {
    if (subjectCode) {
      setSelectedSubjectCode(subjectCode);
    }
    const simSection = document.getElementById('attendance-simulator-section');
    if (simSection) {
      simSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const formatLastSynced = (isoString) => {
    if (!isoString) return 'Just now';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-IN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return 'Recently';
    }
  };

  // -------------------------------------------------------------
  // RENDER: Loading / Skeleton State
  // -------------------------------------------------------------
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-24 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto space-y-6">
        <div className="space-y-2">
          <div className="h-6 w-48 bg-[#181c2b] rounded-lg animate-pulse" />
          <div className="h-4 w-72 bg-[#141824] rounded-lg animate-pulse" />
        </div>

        {/* Skeleton Overall Card */}
        <div className="bg-[#131620] border border-[#232738] rounded-2xl p-8 space-y-6 animate-pulse">
          <div className="flex justify-between items-center">
            <div className="h-5 w-40 bg-[#1e2436] rounded" />
            <div className="h-5 w-24 bg-[#1e2436] rounded-full" />
          </div>
          <div className="h-16 w-60 bg-[#1e2436] rounded-lg" />
          <div className="h-3 w-full bg-[#181c2b] rounded-full" />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="h-16 bg-[#181c2b] rounded-xl" />
            <div className="h-16 bg-[#181c2b] rounded-xl" />
            <div className="h-16 bg-[#181c2b] rounded-xl" />
          </div>
        </div>

        {/* Skeleton Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-48 bg-[#131620] border border-[#232738] rounded-xl animate-pulse p-4 space-y-3">
              <div className="h-4 w-28 bg-[#1c2234] rounded" />
              <div className="h-5 w-44 bg-[#1e2436] rounded" />
              <div className="h-10 bg-[#181c2b] rounded" />
            </div>
          ))}
        </div>

        <div className="text-center text-xs text-gray-500 font-mono py-4">
          Loading attendance...
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // RENDER: Error States (401, 403, 500)
  // -------------------------------------------------------------
  if (errorStatus) {
    return (
      <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-24 pb-16 px-4 flex items-center justify-center">
        <div className="max-w-md w-full bg-[#131620] border border-[#232738] rounded-2xl p-6 sm:p-8 text-center space-y-5 shadow-lg">
          <div className="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center mx-auto">
            {errorStatus === 401 ? <FiLogIn size={22} /> : <FiAlertTriangle size={22} />}
          </div>

          <div className="space-y-1.5">
            <h2 className="text-lg font-bold text-white">
              {errorStatus === 401 ? 'Session Expired' : errorStatus === 403 ? 'Access Forbidden' : 'Attendance Unavailable'}
            </h2>
            <p className="text-xs text-gray-400 leading-relaxed">
              {errorMessage}
            </p>
          </div>

          <div className="pt-2 flex flex-col gap-2">
            {errorStatus === 401 ? (
              <button
                onClick={() => navigate('/login')}
                className="w-full py-2.5 px-4 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs transition-colors shadow-md shadow-purple-600/20"
              >
                Login to Student Sync
              </button>
            ) : (
              <button
                onClick={() => fetchAttendanceSummary(target, true)}
                className="w-full py-2.5 px-4 rounded-lg bg-[#181c2b] hover:bg-[#202538] text-white border border-[#272c3d] font-semibold text-xs transition-colors"
              >
                Retry Loading
              </button>
            )}

            <Link
              to="/dashboard"
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors pt-2 inline-flex items-center justify-center gap-1"
            >
              <FiArrowLeft size={12} />
              <span>Return to Dashboard</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // RENDER: Empty Data State
  // -------------------------------------------------------------
  const subjects = summaryData?.subjects || [];
  if (!subjects.length) {
    return (
      <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-24 pb-16 px-4 max-w-4xl mx-auto space-y-6">
        <div className="bg-[#131620] border border-[#232738] rounded-2xl p-10 text-center space-y-4">
          <FiBookOpen className="text-4xl text-gray-600 mx-auto" />
          <h2 className="text-lg font-bold text-white">No attendance data available yet.</h2>
          <p className="text-xs text-gray-400 max-w-sm mx-auto">
            Your attendance records have not been synced from PSG StudZone yet. Please try refreshing your academic profile from the Dashboard.
          </p>
          <div className="pt-2">
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-purple-600 text-white text-xs font-semibold"
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // RENDER: Complete Attendance Dashboard
  // -------------------------------------------------------------
  const studentName = summaryData?.name || currentUser?.name || summaryData?.rollNo || 'Student';
  const rollNo = summaryData?.rollNo || currentUser?.rollNo || '';
  const lastSynced = summaryData?.last_synced || null;
  const isPreviousData = summaryData?.is_previous_data || false;

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-20 pb-20 px-4 sm:px-6 lg:px-8 overflow-x-hidden">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Top Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-4 border-b border-[#1b1f2e] pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs text-purple-400 font-semibold font-mono tracking-wide uppercase">
                Academic Portal • Attendance & Bunk Planner
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {studentName}
            </h1>
            <div className="text-xs text-gray-400 font-mono flex flex-wrap items-center gap-2">
              <span className="bg-[#151926] px-2 py-0.5 rounded border border-[#222739] text-gray-300">
                {rollNo}
              </span>
              <span>•</span>
              <span>PSG College of Technology</span>
              <span>•</span>
              <span className="text-gray-500">
                Last synced: {formatLastSynced(lastSynced)}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              onClick={() => fetchAttendanceSummary(target, true)}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#181c2b] hover:bg-[#202538] text-gray-300 hover:text-white border border-[#252b3d] text-xs font-medium transition-colors"
              title="Refresh attendance records"
            >
              <FiRefreshCw className={`text-xs ${refreshing ? 'animate-spin text-purple-400' : ''}`} />
              <span>{refreshing ? 'Syncing...' : 'Refresh'}</span>
            </button>

            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#181c2b] hover:bg-[#202538] text-gray-300 hover:text-white border border-[#252b3d] text-xs font-medium transition-colors"
            >
              <span>Dashboard →</span>
            </Link>
          </div>
        </div>

        {/* Informative notice when live portal attendance is updating */}
        {isPreviousData && (
          <div className="bg-amber-500/10 border border-amber-500/25 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-amber-200">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400 flex-shrink-0">
                <FiRefreshCw className="animate-spin text-sm" />
              </div>
              <div className="space-y-0.5">
                <div className="text-xs font-bold text-amber-300 flex items-center gap-2">
                  <span>Current Attendance is Updating</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-mono font-semibold">
                    Saved Baseline
                  </span>
                </div>
                <p className="text-[11px] text-amber-200/80">
                  PSG StudZone is currently publishing updated attendance. Displaying your previously recorded attendance data from the database.
                </p>
              </div>
            </div>
            {lastSynced && (
              <span className="text-[10px] text-amber-300/70 font-mono whitespace-nowrap self-start sm:self-auto">
                Last Recorded: {formatLastSynced(lastSynced)}
              </span>
            )}
          </div>
        )}

        {/* Section A: OVERALL ATTENDANCE CARD */}
        <AttendanceOverview
          summary={summaryData}
          target={target}
          onTargetChange={handleTargetChange}
          onScrollToSimulator={() => handleScrollToSimulator(selectedSubjectCode)}
        />

        {/* Section B: TODAY'S CLASSES TIMETABLE */}
        <TodaySchedule 
          schedule={summaryData?.today_schedule}
          onSelectSubject={handleScrollToSimulator}
        />

        {/* Section C: SUBJECT ATTENDANCE CARDS GRID */}
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-[#1b1f2e]">
            <div>
              <h2 className="text-lg font-bold text-white">Subject-wise Attendance</h2>
              <p className="text-xs text-gray-400">
                Detailed metrics for all enrolled subjects • Target: <strong className="text-white font-mono">{target}%</strong>
              </p>
            </div>
            <span className="text-xs text-gray-500 font-mono self-start sm:self-auto">
              {subjects.length} Enrolled Subjects
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {subjects.map((subj) => (
              <SubjectAttendanceCard
                key={subj.code}
                subject={subj}
                target={target}
                isSelected={selectedSubjectCode === subj.code}
                onSelect={handleScrollToSimulator}
              />
            ))}
          </div>
        </div>

        {/* Section D: BUNK PLANNER & RECOVERY */}
        <BunkPlanner
          subjects={subjects}
          selectedSubjectCode={selectedSubjectCode}
          onSubjectChange={setSelectedSubjectCode}
          target={target}
          onTargetChange={handleTargetChange}
          onOpenSimulator={handleScrollToSimulator}
        />

        {/* Section E: INTERACTIVE ATTENDANCE SIMULATOR */}
        <AttendanceSimulator
          subjects={subjects}
          selectedSubjectCode={selectedSubjectCode}
          onSubjectChange={setSelectedSubjectCode}
          target={target}
          authToken={currentUser?.auth_token}
        />

      </div>
    </div>
  );
};

export default AttendanceDashboard;
