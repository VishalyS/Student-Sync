import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  FiBriefcase, 
  FiRefreshCw, 
  FiAlertCircle, 
  FiShield, 
  FiUser, 
  FiDollarSign, 
  FiHome, 
  FiAward, 
  FiMessageSquare,
  FiExternalLink
} from 'react-icons/fi';

import StudentDossierCard from './components/services/StudentDossierCard';
import FeeLedgerTable from './components/services/FeeLedgerTable';
import HostelStatusCard from './components/services/HostelStatusCard';
import ScholarshipSummary from './components/services/ScholarshipSummary';
import FeedbackCycleAlert from './components/services/FeedbackCycleAlert';

const CampusServicesDashboard = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [servicesData, setServicesData] = useState(null);

  // Authenticated user session
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('student_sync_user') || 'null');
    } catch (e) {
      return null;
    }
  });

  const fetchServicesData = async (isManual = false) => {
    if (!user || !user.auth_token) {
      setLoading(false);
      navigate('/login');
      return;
    }

    if (isManual) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');

    try {
      // Use relative path for Vite dev proxy, with fallback
      const token = encodeURIComponent(user.auth_token);
      const roll = encodeURIComponent(user.rollNo);
      
      const res = await fetch(`/api/campus-services/overview?auth_token=${token}&rollNo=${roll}`);

      if (res.status === 401) {
        localStorage.removeItem('student_sync_user');
        navigate('/login');
        return;
      } else if (res.status === 403) {
        setError('Cross-user authorization failed. Please log in again.');
        return;
      } else if (!res.ok) {
        throw new Error(`Failed to load campus services records (HTTP ${res.status})`);
      }

      const data = await res.json();
      setServicesData(data);
    } catch (err) {
      setError(err.message || 'Unable to connect to Student Sync server.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!user) {
      navigate('/login');
    } else {
      fetchServicesData(false);
    }
  }, [user]);

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-20 pb-20">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* Top Header Strip */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#1b2030]">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
                <FiBriefcase className="text-xl" />
              </span>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Campus Services & Student Dossier
              </h1>
            </div>
            <p className="text-sm text-gray-400">
              Verified institutional identity, official fee ledger, hostel accommodation, scholarships, and feedback cycles.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchServicesData(true)}
              disabled={refreshing || loading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-[#161a26] hover:bg-[#1f2537] border border-[#23293e] text-gray-200 transition-colors disabled:opacity-50"
            >
              <FiRefreshCw className={`text-xs ${refreshing ? 'animate-spin text-purple-400' : ''}`} />
              <span>{refreshing ? 'Refreshing...' : 'Refresh Records'}</span>
            </button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-between gap-3 text-rose-300 text-sm">
            <div className="flex items-center gap-2">
              <FiAlertCircle className="text-lg flex-shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => fetchServicesData(true)}
              className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-xs font-semibold"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading State Skeleton */}
        {loading && (
          <div className="space-y-6 animate-pulse">
            <div className="h-64 bg-[#131622] rounded-2xl border border-[#1e2333]" />
            <div className="h-80 bg-[#131622] rounded-2xl border border-[#1e2333]" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="h-64 bg-[#131622] rounded-2xl border border-[#1e2333]" />
              <div className="h-64 bg-[#131622] rounded-2xl border border-[#1e2333]" />
            </div>
          </div>
        )}

        {/* Content Sections */}
        {!loading && servicesData && (
          <div className="space-y-8">
            
            {/* SECTION 1: Student Identity Dossier */}
            <section id="section-dossier">
              <StudentDossierCard dossier={servicesData.student_dossier} />
            </section>

            {/* SECTION 2: Institutional Fee Ledger */}
            <section id="section-fees">
              <FeeLedgerTable fees={servicesData.fees} />
            </section>

            {/* Grid of Section 3 (Hostel) & Section 4 (Scholarships) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* SECTION 3: Hostel & Accommodation */}
              <section id="section-hostel">
                <HostelStatusCard hostel={servicesData.hostel} />
              </section>

              {/* SECTION 4: Scholarships */}
              <section id="section-scholarships">
                <ScholarshipSummary scholarships={servicesData.scholarships} />
              </section>
            </div>

            {/* SECTION 5: Institutional Course Feedback */}
            <section id="section-feedback">
              <FeedbackCycleAlert feedback={servicesData.feedback} />
            </section>

            {/* Trust & Transparency Banner */}
            <div className="p-5 rounded-2xl bg-[#111420] border border-[#1d2232] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-400">
              <div className="flex items-center gap-2">
                <FiShield className="text-emerald-400 text-base flex-shrink-0" />
                <span>
                  All campus administrative records are synchronized directly from official StudZone 1 sessions. No financial transactions or record mutations are executed by Student Sync.
                </span>
              </div>
              <span className="font-mono text-[11px] text-gray-400 flex-shrink-0">
                100% Read-Only Mode
              </span>
            </div>

          </div>
        )}

      </div>
    </div>
  );
};

export default CampusServicesDashboard;
