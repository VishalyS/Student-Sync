import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { 
  FiRefreshCw, 
  FiAlertCircle, 
  FiCompass, 
  FiCalendar, 
  FiArrowLeft,
  FiLogIn,
  FiBookOpen,
  FiCheckCircle,
  FiShield
} from 'react-icons/fi';

import Navbar from './components/Navbar';
import Footer from './Footer';
import AcademicHealthCards from './components/planner/AcademicHealthCards';
import DailyFocusCard from './components/planner/DailyFocusCard';
import SubjectRiskMatrix from './components/planner/SubjectRiskMatrix';
import StudyGoalAllocator from './components/planner/StudyGoalAllocator';

const PersonalizedPlannerDashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [currentUser, setCurrentUser] = useState(null);
  const [plannerData, setPlannerData] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingDay, setLoadingDay] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [errorStatus, setErrorStatus] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

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

    if (!user && location.state && location.state.rollNo) {
      user = location.state;
    }

    if (!user || (!user.rollNo && !user.auth_token)) {
      setLoading(false);
      setErrorStatus(401);
      setErrorMessage('Your session has expired. Please log in again to access your academic study planner.');
      return;
    }

    setCurrentUser(user);
  }, [location.state]);

  // 2. Fetch Planner Intelligence from Backend API
  const fetchPlannerData = async (user, day = null, isRefresh = false) => {
    if (!user || !user.rollNo) return;

    if (day) {
      setLoadingDay(true);
    } else if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setErrorStatus(null);
    setErrorMessage('');

    try {
      const token = user.auth_token || '';
      let url = `/api/planner/intelligence?rollNo=${encodeURIComponent(user.rollNo)}&auth_token=${encodeURIComponent(token)}`;
      if (day) {
        url += `&day=${encodeURIComponent(day)}`;
      }

      const res = await fetch(url);
      const data = await res.json();

      if (!res.ok) {
        setErrorStatus(res.status);
        setErrorMessage(data.error || 'Failed to fetch academic planner intelligence.');
        return;
      }

      setPlannerData(data);
      if (!selectedDay && data.today_context?.day_name) {
        setSelectedDay(data.today_context.day_name);
      }
    } catch (err) {
      console.error('Fetch error:', err);
      setErrorStatus(500);
      setErrorMessage('Network connection error while communicating with Student Sync planner services.');
    } finally {
      setLoading(false);
      setLoadingDay(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (currentUser) {
      fetchPlannerData(currentUser, selectedDay);
    }
  }, [currentUser]);

  const handleSelectDay = (day) => {
    setSelectedDay(day);
    if (currentUser) {
      fetchPlannerData(currentUser, day);
    }
  };

  const handleRefresh = () => {
    if (currentUser) {
      fetchPlannerData(currentUser, selectedDay, true);
    }
  };

  // 3. Render Session Required / Error States
  if (!loading && errorStatus === 401) {
    return (
      <div className="min-vh-100 bg-[#0e1118] text-gray-200 flex flex-col justify-between">
        <Navbar />
        <div className="max-w-md mx-auto px-4 py-24 text-center">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mx-auto mb-4">
            <FiAlertCircle className="text-3xl" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Authentication Required</h2>
          <p className="text-sm text-gray-400 mb-6">{errorMessage}</p>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold transition-all shadow-lg shadow-purple-600/20"
          >
            <FiLogIn /> Log In to Student Sync
          </Link>
        </div>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-vh-100 bg-[#0e1118] text-gray-200 flex flex-col justify-between selection:bg-purple-500/20 selection:text-purple-300">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16 flex-grow w-full">
        {/* Top Breadcrumb & Action Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <Link to="/dashboard" className="hover:text-purple-400 transition-colors flex items-center gap-1">
              <FiArrowLeft className="text-xs" /> Back to Dashboard
            </Link>
            <span>/</span>
            <span className="text-gray-200 font-medium">Academic Planner</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
              Active Session: {plannerData?.student?.rollNo || currentUser?.rollNo || '25MX232'}
            </span>
            <button
              onClick={handleRefresh}
              disabled={refreshing || loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#161a23] hover:bg-[#1e2330] border border-[#262c3d] text-xs text-gray-300 hover:text-white transition-all disabled:opacity-50"
            >
              <FiRefreshCw className={`text-xs ${refreshing ? 'animate-spin text-purple-400' : ''}`} />
              <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
            </button>
          </div>
        </div>

        {/* Header Hero Banner */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-purple-900/30 via-indigo-900/20 to-[#151922] border border-[#232938] p-6 sm:p-8 mb-8 shadow-sm">
          <div className="relative z-10 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30 mb-3">
              <FiCompass className="text-purple-400" />
              <span>Personalized Academic Intelligence & Study Planner</span>
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-white tracking-tight">
              Study Planner & Academic Priorities
            </h1>
            <p className="text-sm sm:text-base text-gray-300 mt-2 leading-relaxed">
              Synthesizing your verified attendance buffers, weekly timetable slots, continuous assessment workload, and examination schedule into a unified daily action plan.
            </p>
          </div>
          <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-purple-500/5 to-transparent pointer-events-none" />
        </div>

        {/* Main Content Area */}
        {loading ? (
          <div className="text-center py-24">
            <div className="w-12 h-12 border-4 border-purple-500/20 border-t-purple-500 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-gray-400">Loading personalized academic intelligence...</p>
          </div>
        ) : errorStatus ? (
          <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-center my-8">
            <FiAlertCircle className="text-3xl text-rose-400 mx-auto mb-2" />
            <h3 className="text-lg font-bold text-white mb-1">Error Loading Planner</h3>
            <p className="text-sm text-rose-300 mb-4">{errorMessage}</p>
            <button
              onClick={handleRefresh}
              className="px-4 py-2 rounded-lg bg-rose-600 text-white text-xs font-semibold hover:bg-rose-500 transition-all"
            >
              Try Again
            </button>
          </div>
        ) : (
          <>
            {/* Section 1: Academic Health Snapshot */}
            <AcademicHealthCards
              student={plannerData?.student}
              attendance={plannerData?.attendance}
              academicHealth={plannerData?.academic_health}
              registeredExamsSummary={plannerData?.registered_exams_summary}
            />

            {/* Section 2: What Should I Study Today? (Contextual Focus) */}
            <DailyFocusCard
              todayContext={plannerData?.today_context}
              selectedDay={selectedDay}
              onSelectDay={handleSelectDay}
              loadingDay={loadingDay}
            />

            {/* Section 3: Cross-Module Subject Intelligence Matrix */}
            <SubjectRiskMatrix
              subjectMatrix={plannerData?.subject_matrix || []}
            />

            {/* Section 4: Interactive Study Goal Allocator */}
            <StudyGoalAllocator
              subjectMatrix={plannerData?.subject_matrix || []}
              rollNo={plannerData?.student?.rollNo || currentUser?.rollNo}
            />
          </>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default PersonalizedPlannerDashboard;
