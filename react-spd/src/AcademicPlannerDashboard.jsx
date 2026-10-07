import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { 
  FiRefreshCw, 
  FiAlertCircle, 
  FiAlertTriangle, 
  FiCheckCircle, 
  FiArrowLeft,
  FiAward,
  FiFileText,
  FiSliders,
  FiLogIn
} from 'react-icons/fi';

import Navbar from './components/Navbar';
import Footer from './Footer';
import MarksSummaryCard from './components/academics/MarksSummaryCard';
import CAComponentBreakdown from './components/academics/CAComponentBreakdown';
import ResultsAnalytics from './components/academics/ResultsAnalytics';
import CgpaSimulator from './components/academics/CgpaSimulator';

const AcademicPlannerDashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [currentUser, setCurrentUser] = useState(null);
  const [academicData, setAcademicData] = useState(null);
  const [activeTab, setActiveTab] = useState('ca_marks'); // 'ca_marks' | 'results' | 'simulator'
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
      setErrorMessage('Your session has expired. Please log in again to view your academic analytics.');
      return;
    }

    setCurrentUser(user);
  }, [location.state]);

  // 2. Fetch Academic Summary from Backend API
  const fetchAcademicData = async (isManual = false) => {
    if (isManual) {
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

    const headers = { 'Content-Type': 'application/json' };
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const queryParams = new URLSearchParams();
    if (authToken) {
      queryParams.set('auth_token', authToken);
    }
    if (rollNo) {
      queryParams.set('rollNo', rollNo);
    }

    const apiUrl = `/api/academic/marks-summary?${queryParams.toString()}`;

    try {
      const resp = await fetch(apiUrl, { credentials: 'omit', headers });
      if (resp.status === 401) {
        setErrorStatus(401);
        setErrorMessage('Authentication required. Please log in with your PSG Tech roll number and password.');
        return;
      }
      if (resp.status === 403) {
        setErrorStatus(403);
        setErrorMessage('Access denied. You can only view your own academic records.');
        return;
      }
      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        setErrorStatus(resp.status);
        setErrorMessage(errJson.error || `Failed to fetch academic summary (HTTP ${resp.status}).`);
        return;
      }

      const json = await resp.json();
      setAcademicData(json);
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
      fetchAcademicData();
    }
  }, [currentUser]);

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
              <span className="text-xs text-purple-300 font-medium">Grades & Analytics</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <span>Academic Performance & CA Breakdown</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300">
                Phase 5
              </span>
            </h1>
            <p className="text-xs text-gray-400 mt-1 max-w-2xl">
              Verified Continuous Assessment evaluations, historical semester examination results, 
              and in-memory What-If CGPA simulator.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3 self-start sm:self-auto">
            <button
              onClick={() => fetchAcademicData(true)}
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
              <span className="font-semibold text-white">Error loading academic records: </span>
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="py-24 text-center space-y-3">
            <FiRefreshCw className="mx-auto text-2xl text-purple-400 animate-spin" />
            <p className="text-xs text-gray-400">Loading verified academic and CA evaluations...</p>
          </div>
        )}

        {/* Main Content Area */}
        {!loading && !errorStatus && academicData && (
          <div className="space-y-6">
            
            {/* Top Metric Cards */}
            <MarksSummaryCard 
              caData={academicData.ca_marks}
              resultsData={academicData.results}
            />

            {/* Navigation Tabs */}
            <div className="flex border-b border-[#1c202e] gap-2 pt-2">
              <button
                onClick={() => setActiveTab('ca_marks')}
                className={`pb-3 px-3 text-xs font-semibold transition-all flex items-center gap-2 border-b-2 ${
                  activeTab === 'ca_marks'
                    ? 'border-purple-500 text-white'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <FiFileText size={14} className={activeTab === 'ca_marks' ? 'text-purple-400' : ''} />
                <span>Continuous Assessment (CA) Breakdown</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#181c2b] text-purple-300 font-mono">
                  {academicData.ca_marks?.total_courses || 0}
                </span>
              </button>

              <button
                onClick={() => setActiveTab('results')}
                className={`pb-3 px-3 text-xs font-semibold transition-all flex items-center gap-2 border-b-2 ${
                  activeTab === 'results'
                    ? 'border-purple-500 text-white'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <FiAward size={14} className={activeTab === 'results' ? 'text-purple-400' : ''} />
                <span>Semester Results & CGPA</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#181c2b] text-emerald-300 font-mono">
                  {academicData.results?.total_credits || 0} Cr
                </span>
              </button>

              <button
                onClick={() => setActiveTab('simulator')}
                className={`pb-3 px-3 text-xs font-semibold transition-all flex items-center gap-2 border-b-2 ${
                  activeTab === 'simulator'
                    ? 'border-purple-500 text-white'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <FiSliders size={14} className={activeTab === 'simulator' ? 'text-purple-400' : ''} />
                <span>What-If CGPA Simulator</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-300 font-mono">
                  In-Memory
                </span>
              </button>
            </div>

            {/* Tab Views */}
            {activeTab === 'ca_marks' && (
              <CAComponentBreakdown courses={academicData.ca_marks?.courses || []} />
            )}

            {activeTab === 'results' && (
              <ResultsAnalytics resultsData={academicData.results} />
            )}

            {activeTab === 'simulator' && (
              <CgpaSimulator 
                baseCredits={academicData.base_credits || 24.0}
                baseCgpa={academicData.base_cgpa || 7.96}
              />
            )}

          </div>
        )}

      </main>

      <Footer />
    </div>
  );
};

export default AcademicPlannerDashboard;
