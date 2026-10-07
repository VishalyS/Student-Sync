import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { 
  FiRefreshCw, 
  FiAlertCircle, 
  FiAlertTriangle, 
  FiArrowLeft,
  FiCalendar,
  FiClock,
  FiSliders,
  FiFileText,
  FiLogIn,
  FiBookOpen,
  FiCheckCircle
} from 'react-icons/fi';

import Navbar from './components/Navbar';
import Footer from './Footer';
import WeeklyTimetableGrid from './components/schedule/WeeklyTimetableGrid';
import DayBunkSimulator from './components/schedule/DayBunkSimulator';
import ExamScheduleList from './components/schedule/ExamScheduleList';
import CircularsViewer from './components/schedule/CircularsViewer';

const ScheduleDashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [currentUser, setCurrentUser] = useState(null);
  const [weeklySchedule, setWeeklySchedule] = useState(null);
  const [examsData, setExamsData] = useState(null);
  const [unifiedCourses, setUnifiedCourses] = useState([]);
  
  const [activeTab, setActiveTab] = useState('weekly'); // 'weekly' | 'bunk_planner' | 'exams' | 'circulars'
  const [loading, setLoading] = useState(true);
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
      setErrorMessage('Your session has expired. Please log in again to access your timetable and exam schedule.');
      return;
    }

    setCurrentUser(user);
  }, [location.state]);

  // 2. Fetch Schedule and Exam Records
  const fetchScheduleData = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);

    setErrorStatus(null);
    setErrorMessage('');

    const rawStored = localStorage.getItem('student_sync_user');
    let user = currentUser;
    if (!user && rawStored) {
      try { user = JSON.parse(rawStored); } catch(e){}
    }

    const authToken = user?.auth_token;
    const rollNo = user?.rollNo;

    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const queryParams = new URLSearchParams();
    if (authToken) queryParams.set('auth_token', authToken);
    if (rollNo) queryParams.set('rollNo', rollNo);

    try {
      const [weeklyResp, examsResp, coursesResp] = await Promise.all([
        fetch(`/api/schedule/weekly?${queryParams.toString()}`, { credentials: 'omit', headers }),
        fetch(`/api/schedule/exams?${queryParams.toString()}`, { credentials: 'omit', headers }),
        fetch(`/api/courses/unified-summary?${queryParams.toString()}`, { credentials: 'omit', headers })
      ]);

      if (weeklyResp.status === 401 || examsResp.status === 401) {
        setErrorStatus(401);
        setErrorMessage('Authentication required. Please log in with your PSG Tech credentials.');
        return;
      }

      if (weeklyResp.status === 403 || examsResp.status === 403) {
        setErrorStatus(403);
        setErrorMessage('Access denied. You can only view your own timetable and exam schedule.');
        return;
      }

      if (!weeklyResp.ok || !examsResp.ok) {
        setErrorStatus(500);
        setErrorMessage('Failed to fetch schedule records from backend service.');
        return;
      }

      const [weeklyJson, examsJson, coursesJson] = await Promise.all([
        weeklyResp.json(),
        examsResp.json(),
        coursesResp.ok ? coursesResp.json() : { courses: [] }
      ]);

      setWeeklySchedule(weeklyJson);
      setExamsData(examsJson);
      setUnifiedCourses(coursesJson.courses || []);
    } catch (err) {
      setErrorStatus(500);
      setErrorMessage(`Network error connecting to backend: ${err.message}`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (currentUser) {
      fetchScheduleData();
    }
  }, [currentUser]);

  // Compute top level quick stats
  const totalWeeklyClasses = weeklySchedule?.days?.reduce((sum, d) => sum + (d.scheduled_classes || 0), 0) || 0;
  const totalExams = examsData?.total_exams || 0;
  const pendingExams = examsData?.pending_count || 0;
  const circularsCount = examsData?.circulars?.length || 0;

  return (
    <div className="min-h-screen bg-[#0b0d13] text-gray-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
        
        {/* Top Header & Navigation Breadcrumb */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#1c202e]">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Link 
                to="/dashboard"
                className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-purple-400 transition-colors"
              >
                <FiArrowLeft size={13} />
                <span>Dashboard</span>
              </Link>
              <span className="text-gray-600">/</span>
              <span className="text-xs text-purple-300 font-medium">Schedule &amp; Exams</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <span>Timetable Intelligence &amp; Examination Hub</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300">
                Phase 6
              </span>
            </h1>
            <p className="text-xs text-gray-400 mt-1 max-w-2xl">
              Verified weekly class schedule, schedule-aware day-bunk simulator, official end-semester examination timetable, and CoE circulars.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3 self-start sm:self-auto">
            <button
              onClick={() => fetchScheduleData(true)}
              disabled={loading || refreshing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#141824] hover:bg-[#1d2233] border border-[#23283b] text-xs font-medium text-gray-300 hover:text-white transition-all disabled:opacity-50"
            >
              <FiRefreshCw className={`text-purple-400 ${refreshing ? 'animate-spin' : ''}`} size={13} />
              <span>{refreshing ? 'Syncing...' : 'Refresh'}</span>
            </button>
          </div>
        </div>

        {/* Error States */}
        {errorStatus === 401 && (
          <div className="p-6 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 space-y-3 text-center max-w-md mx-auto my-12">
            <FiAlertTriangle className="mx-auto text-3xl text-amber-400" />
            <h2 className="text-sm font-semibold text-white">Authentication Required</h2>
            <p className="text-xs text-gray-300">{errorMessage}</p>
            <div className="pt-2">
              <Link 
                to="/login"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs font-semibold hover:from-purple-500 hover:to-indigo-500 transition-all"
              >
                <FiLogIn size={13} />
                <span>Return to Login</span>
              </Link>
            </div>
          </div>
        )}

        {errorStatus && errorStatus !== 401 && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 flex items-start gap-3">
            <FiAlertCircle className="flex-shrink-0 mt-0.5 text-rose-400" size={16} />
            <div className="text-xs space-y-1">
              <span className="font-semibold text-white">Error loading schedule: </span>
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="py-24 text-center space-y-3">
            <FiRefreshCw className="mx-auto text-2xl text-purple-400 animate-spin" />
            <p className="text-xs text-gray-400">Loading verified timetable and examination records...</p>
          </div>
        )}

        {/* Main Content Area */}
        {!loading && !errorStatus && weeklySchedule && examsData && (
          <div className="space-y-6">
            
            {/* Quick Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-[#131620] border border-[#232738]">
                <div className="text-[10px] text-gray-400 uppercase font-semibold">Weekly Lecture Hours</div>
                <div className="text-2xl font-extrabold text-white mt-1">
                  {totalWeeklyClasses} Classes
                </div>
                <div className="text-[11px] text-gray-400 mt-0.5">Monday through Friday</div>
              </div>

              <div className="p-4 rounded-xl bg-[#131620] border border-[#232738]">
                <div className="text-[10px] text-gray-400 uppercase font-semibold">Registered Courses</div>
                <div className="text-2xl font-extrabold text-purple-300 mt-1">
                  {weeklySchedule.course_codes?.length || 8} Courses
                </div>
                <div className="text-[11px] text-gray-400 mt-0.5">StudZone 1 curriculum</div>
              </div>

              <div className="p-4 rounded-xl bg-[#131620] border border-[#232738]">
                <div className="text-[10px] text-gray-400 uppercase font-semibold">End-Semester Exams</div>
                <div className="text-2xl font-extrabold text-white mt-1">
                  {totalExams} Exams
                </div>
                <div className="text-[11px] text-amber-400 mt-0.5 font-mono">
                  {pendingExams > 0 ? `${pendingExams} Dates Pending CoE` : 'All dates set'}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-[#131620] border border-[#232738]">
                <div className="text-[10px] text-gray-400 uppercase font-semibold">Official CoE Circulars</div>
                <div className="text-2xl font-extrabold text-emerald-400 mt-1">
                  {circularsCount} Available
                </div>
                <div className="text-[11px] text-gray-400 mt-0.5">Verified exam guidelines</div>
              </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-[#1c202e] gap-2 pt-2 overflow-x-auto">
              <button
                onClick={() => setActiveTab('weekly')}
                className={`pb-3 px-3 text-xs font-semibold transition-all flex items-center gap-2 border-b-2 whitespace-nowrap ${
                  activeTab === 'weekly'
                    ? 'border-purple-500 text-white'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <FiClock size={14} className={activeTab === 'weekly' ? 'text-purple-400' : ''} />
                <span>Weekly Class Timetable</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#181c2b] text-purple-300 font-mono">
                  5 Days
                </span>
              </button>

              <button
                onClick={() => setActiveTab('bunk_planner')}
                className={`pb-3 px-3 text-xs font-semibold transition-all flex items-center gap-2 border-b-2 whitespace-nowrap ${
                  activeTab === 'bunk_planner'
                    ? 'border-purple-500 text-white'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <FiSliders size={14} className={activeTab === 'bunk_planner' ? 'text-purple-400' : ''} />
                <span>Day-Bunk Planner</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-300 font-mono">
                  In-Memory
                </span>
              </button>

              <button
                onClick={() => setActiveTab('exams')}
                className={`pb-3 px-3 text-xs font-semibold transition-all flex items-center gap-2 border-b-2 whitespace-nowrap ${
                  activeTab === 'exams'
                    ? 'border-purple-500 text-white'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <FiCalendar size={14} className={activeTab === 'exams' ? 'text-purple-400' : ''} />
                <span>End-Semester Examination Hub</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#181c2b] text-blue-300 font-mono">
                  {totalExams} Courses
                </span>
              </button>

              <button
                onClick={() => setActiveTab('circulars')}
                className={`pb-3 px-3 text-xs font-semibold transition-all flex items-center gap-2 border-b-2 whitespace-nowrap ${
                  activeTab === 'circulars'
                    ? 'border-purple-500 text-white'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <FiFileText size={14} className={activeTab === 'circulars' ? 'text-purple-400' : ''} />
                <span>Official CoE Circulars</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#181c2b] text-emerald-300 font-mono">
                  {circularsCount} PDFs
                </span>
              </button>
            </div>

            {/* Tab Views */}
            {activeTab === 'weekly' && (
              <WeeklyTimetableGrid 
                weeklySchedule={weeklySchedule}
                unifiedCourses={unifiedCourses}
              />
            )}

            {activeTab === 'bunk_planner' && (
              <DayBunkSimulator 
                weeklySchedule={weeklySchedule}
                authToken={currentUser?.auth_token}
                rollNo={currentUser?.rollNo}
              />
            )}

            {activeTab === 'exams' && (
              <ExamScheduleList examsData={examsData} />
            )}

            {activeTab === 'circulars' && (
              <CircularsViewer circulars={examsData.circulars} />
            )}

          </div>
        )}

      </main>

      <Footer />
    </div>
  );
};

export default ScheduleDashboard;
