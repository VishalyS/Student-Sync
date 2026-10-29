import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  FiHome,
  FiRefreshCw,
  FiAlertCircle,
  FiUser,
  FiCoffee,
  FiDollarSign,
  FiCalendar,
  FiShield,
  FiMapPin,
  FiPhone,
  FiMail,
  FiCheckCircle,
  FiArrowRight,
  FiInfo,
  FiFileText,
  FiTag,
  FiClock
} from 'react-icons/fi';

export default function HostelDashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [eligibilityLoading, setEligibilityLoading] = useState(true);
  const [eligibility, setEligibility] = useState(null); // { status, isHosteller, isDayScholar, canAccessHostel, roomNumber }

  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [hostelData, setHostelData] = useState(null);
  const [meta, setMeta] = useState(null);
  const [currentTab, setCurrentTab] = useState('overview');

  // 1. Initial User Session Check
  useEffect(() => {
    const stored = localStorage.getItem('student_sync_user');
    if (!stored) {
      navigate('/login', { replace: true });
      return;
    }
    try {
      const parsed = JSON.parse(stored);
      setUser(parsed);
    } catch (e) {
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  // 2. Verified Residential Status Check (Backend-Enforced)
  const verifyEligibility = async (currentUser) => {
    if (!currentUser || !currentUser.auth_token) return;
    setEligibilityLoading(true);
    setError('');

    try {
      const token = encodeURIComponent(currentUser.auth_token);
      const res = await fetch(`/api/v1/hostel/status?auth_token=${token}`);
      const data = await res.json();

      if (res.ok && data.success) {
        setEligibility(data);
        if (data.canAccessHostel) {
          fetchHostelRecords(currentUser, false);
        } else {
          setLoading(false);
        }
      } else {
        // Fallback to cached state if present on student document
        if (currentUser.residential_status) {
          const fallbackElig = {
            status: currentUser.residential_status,
            isHosteller: currentUser.residential_status === 'HOSTELLER',
            isDayScholar: currentUser.residential_status === 'DAY_SCHOLAR',
            canAccessHostel: currentUser.residential_status === 'HOSTELLER',
            roomNumber: currentUser.room_number || null,
          };
          setEligibility(fallbackElig);
          if (fallbackElig.canAccessHostel) {
            fetchHostelRecords(currentUser, false);
          } else {
            setLoading(false);
          }
        } else {
          setEligibility({ status: 'UNKNOWN', canAccessHostel: false });
          setLoading(false);
        }
      }
    } catch (err) {
      console.warn('Residential status verification error:', err);
      if (currentUser?.residential_status) {
        const fallbackElig = {
          status: currentUser.residential_status,
          isHosteller: currentUser.residential_status === 'HOSTELLER',
          isDayScholar: currentUser.residential_status === 'DAY_SCHOLAR',
          canAccessHostel: currentUser.residential_status === 'HOSTELLER',
          roomNumber: currentUser.room_number || null,
        };
        setEligibility(fallbackElig);
        if (fallbackElig.canAccessHostel) {
          fetchHostelRecords(currentUser, false);
        } else {
          setLoading(false);
        }
      } else {
        setEligibility({ status: 'UNKNOWN', canAccessHostel: false });
        setLoading(false);
      }
    } finally {
      setEligibilityLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      verifyEligibility(user);
    }
  }, [user]);

  // 3. Fetch Full Hostel Records for Verified Hosteller
  const fetchHostelRecords = async (currentUser, isManual = false) => {
    if (!currentUser || !currentUser.auth_token) return;
    if (isManual) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError('');

    try {
      const token = encodeURIComponent(currentUser.auth_token);
      const roll = encodeURIComponent(currentUser.rollNo);
      const refreshParam = isManual ? '&refresh=true' : '';

      const res = await fetch(`/api/v1/hostel/student/${roll}?auth_token=${token}${refreshParam}`);
      const data = await res.json();

      if (res.ok && data.success && data.data) {
        setHostelData(data.data);
        if (data.meta) setMeta(data.meta);
      } else if (res.status === 403) {
        setError(data.error || 'Access Denied: You are not authorized to view hostel records.');
        setEligibility({ status: 'DAY_SCHOLAR', canAccessHostel: false });
      } else {
        setError(data.error || 'Failed to retrieve hostel records.');
      }
    } catch (err) {
      setError('Network communication failed. Please check your connection.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    if (user) {
      verifyEligibility(user);
    }
  };

  // Safe destructuring of hostel data domains
  const profile = hostelData?.profile || {};
  const room = hostelData?.room || {};
  const mess = hostelData?.mess || {};
  const fees = hostelData?.fees || {};
  const leave = hostelData?.leave || {};
  const feeDue = hostelData?.feeDue || [];

  const tabs = [
    { id: 'overview', label: 'Overview', icon: <FiHome className="text-sm" /> },
    { id: 'room', label: 'Room & Warden', icon: <FiShield className="text-sm" /> },
    { id: 'mess', label: 'Mess & Dining', icon: <FiCoffee className="text-sm" /> },
    { id: 'fees', label: 'Fees & Dues', icon: <FiDollarSign className="text-sm" /> },
    { id: 'leave', label: 'Leave & Passes', icon: <FiCalendar className="text-sm" /> },
  ];

  // =========================================================================
  // VIEW 1: ELIGIBILITY LOADING SKELETON
  // =========================================================================
  if (eligibilityLoading) {
    return (
      <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-24 pb-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto space-y-6 animate-pulse">
          <div className="h-28 rounded-2xl bg-[#131620] border border-[#1f2434]" />
          <div className="h-64 rounded-2xl bg-[#131620] border border-[#1f2434]" />
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 2: VERIFIED DAY SCHOLAR (ACCESS FORBIDDEN VIEW)
  // =========================================================================
  if (eligibility && eligibility.status === 'DAY_SCHOLAR') {
    return (
      <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-24 pb-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto">
          <div className="bg-[#121520] border border-[#1e2333] rounded-3xl p-8 sm:p-10 shadow-2xl text-center space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center mx-auto">
              <FiHome className="text-2xl" />
            </div>

            <div className="space-y-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-gray-500/10 border border-gray-500/30 text-gray-300">
                Institutional Category: Day Scholar
              </span>
              <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                Hostel Services Exclusively for Residents
              </h1>
              <p className="text-sm text-gray-400 max-w-lg mx-auto leading-relaxed">
                Student <strong className="text-white font-mono">{user?.rollNo}</strong> is officially registered as a
                <span className="text-cyan-300 font-semibold"> Day Scholar</span> in the PSG Tech StudZone institutional portal.
                Hostel room allotments, mess subscriptions, and leave passes are reserved for campus residents.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-[#161a27] border border-[#23293e] text-left max-w-md mx-auto space-y-2 text-xs">
              <div className="flex justify-between text-gray-400">
                <span>Verified Source:</span>
                <span className="text-gray-200 font-mono">StudZone 1 Vallalar Portal</span>
              </div>
              <div className="flex justify-between text-gray-400">
                <span>Status Flag:</span>
                <span className="text-emerald-400 font-semibold font-mono">DAY_SCHOLAR</span>
              </div>
              <div className="flex justify-between text-gray-400">
                <span>Allocated Room:</span>
                <span className="text-gray-400 font-mono">None (Day Scholar)</span>
              </div>
            </div>

            <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
              <Link
                to="/dashboard"
                className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition-all flex items-center gap-2"
              >
                <span>Return to Dashboard</span>
                <FiArrowRight />
              </Link>
              <Link
                to="/services"
                className="px-5 py-2.5 rounded-xl bg-[#1a1e2c] hover:bg-[#22283a] border border-[#2a3045] text-gray-300 hover:text-white text-xs font-semibold transition-colors"
              >
                View Academic Campus Services
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 3: UNKNOWN OR UNVERIFIABLE STATUS (FAIL-CLOSED)
  // =========================================================================
  if (eligibility && eligibility.status === 'UNKNOWN') {
    return (
      <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-24 pb-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mx-auto">
          <div className="bg-[#121520] border border-[#1e2333] rounded-3xl p-8 sm:p-10 shadow-2xl text-center space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mx-auto">
              <FiAlertCircle className="text-2xl" />
            </div>

            <div className="space-y-2">
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Residential Eligibility Verification Required
              </h1>
              <p className="text-sm text-gray-400 leading-relaxed max-w-md mx-auto">
                Your residential category could not be verified automatically from your current StudZone 1 records.
                Hostel services fail closed to protect student privacy.
              </p>
            </div>

            <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition-all flex items-center gap-2 disabled:opacity-50"
              >
                <FiRefreshCw className={refreshing ? 'animate-spin' : ''} />
                <span>Retry Verification</span>
              </button>
              <Link
                to="/dashboard"
                className="px-5 py-2.5 rounded-xl bg-[#1a1e2c] hover:bg-[#22283a] border border-[#2a3045] text-gray-300 hover:text-white text-xs font-semibold transition-colors"
              >
                Back to Dashboard
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 4: VERIFIED HOSTELLER DASHBOARD
  // =========================================================================
  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] pt-20 pb-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">

        {/* Top Header Banner */}
        <div className="bg-[#121520] border border-[#1e2333] rounded-3xl p-6 sm:p-8 shadow-xl">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 tracking-wide uppercase">
                  Verified Resident
                </span>
                <span className="px-3 py-1 rounded-full text-xs font-mono font-medium bg-[#1a1e2d] border border-[#282f45] text-gray-300">
                  Room: {room?.room_number || eligibility?.roomNumber || 'Assigned'}
                </span>
                <span className="px-3 py-1 rounded-full text-xs font-mono font-medium bg-[#1a1e2d] border border-[#282f45] text-cyan-300">
                  Source: {meta?.source || 'PSG Tech Hostel Portal'}
                </span>
                {meta?.updatedAt && (
                  <span className="text-xs text-gray-400 font-mono">
                    Synced: {new Date(meta.updatedAt).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'short', timeStyle: 'short' })}
                  </span>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
                <FiHome className="text-cyan-400 text-2xl sm:text-3xl" />
                <span>Student Sync — Hostel Portal</span>
              </h1>
              <p className="text-xs sm:text-sm text-gray-400 max-w-2xl">
                Official residency oversight, room allotments, mess token management, fee ledgers, and leave approvals.
              </p>
            </div>

            <div className="flex items-center gap-3 self-start lg:self-center">
              <button
                onClick={() => fetchHostelRecords(user, true)}
                disabled={refreshing || loading}
                className="px-4 py-2.5 rounded-xl bg-[#161a27] hover:bg-[#1e2436] border border-[#242b3e] text-xs font-semibold text-gray-200 hover:text-white transition-all flex items-center gap-2 disabled:opacity-50"
              >
                <FiRefreshCw className={`text-xs ${refreshing ? 'animate-spin text-cyan-400' : ''}`} />
                <span>{refreshing ? 'Syncing...' : 'Refresh'}</span>
              </button>
            </div>
          </div>

          {/* Navigation Sub-Tabs */}
          <div className="flex items-center gap-2 mt-8 pt-6 border-t border-[#1e2333] overflow-x-auto pb-1 scrollbar-none">
            {tabs.map((tab) => {
              const isActive = currentTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setCurrentTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
                    isActive
                      ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/20'
                      : 'bg-[#161a26] hover:bg-[#1d2232] text-gray-400 hover:text-gray-200 border border-[#222838]'
                  }`}
                >
                  {tab.icon}
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Global Error Banner if any */}
        {error && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
            <FiAlertCircle className="text-base flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* TAB CONTENT */}
        {loading ? (
          <div className="py-20 text-center space-y-3">
            <FiRefreshCw className="animate-spin text-2xl text-cyan-400 mx-auto" />
            <p className="text-xs text-gray-400">Loading authorized hostel records...</p>
          </div>
        ) : (
          <div className="space-y-8">

            {/* OVERVIEW TAB */}
            {currentTab === 'overview' && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">

                {/* Metric 1: Room Allotment */}
                <div className="p-6 rounded-2xl bg-[#121520] border border-[#1e2333] space-y-2">
                  <div className="flex items-center justify-between text-gray-400 text-xs">
                    <span className="font-semibold uppercase tracking-wider text-[10px]">Room Number</span>
                    <FiShield className="text-cyan-400" />
                  </div>
                  <div className="text-2xl font-mono font-bold text-white">
                    {room?.room_number || eligibility?.roomNumber || 'Assigned'}
                  </div>
                  <p className="text-xs text-gray-400 truncate">
                    {room?.hostel_name || 'PSG Tech Hostel'} • {room?.block_name || 'Main Block'}
                  </p>
                </div>

                {/* Metric 2: Mess Subscription */}
                <div className="p-6 rounded-2xl bg-[#121520] border border-[#1e2333] space-y-2">
                  <div className="flex items-center justify-between text-gray-400 text-xs">
                    <span className="font-semibold uppercase tracking-wider text-[10px]">Mess Subscription</span>
                    <FiCoffee className="text-emerald-400" />
                  </div>
                  <div className="text-2xl font-bold text-white truncate">
                    {mess?.mess_name || 'Student Dining'}
                  </div>
                  <p className="text-xs text-emerald-400 font-medium">
                    Cuisine: {mess?.mess_type || 'South Indian'}
                  </p>
                </div>

                {/* Metric 3: Fee Balance */}
                <div className="p-6 rounded-2xl bg-[#121520] border border-[#1e2333] space-y-2">
                  <div className="flex items-center justify-between text-gray-400 text-xs">
                    <span className="font-semibold uppercase tracking-wider text-[10px]">Hostel Fee Balance</span>
                    <FiDollarSign className="text-purple-400" />
                  </div>
                  <div className="text-2xl font-mono font-bold text-white">
                    ₹ {Number(fees?.hostel_fee_balance || 0).toLocaleString('en-IN')}
                  </div>
                  <p className="text-xs text-gray-400">
                    Caution Deposit: ₹ {Number(fees?.caution_deposit || 0).toLocaleString('en-IN')}
                  </p>
                </div>

                {/* Metric 4: Leave Summary */}
                <div className="p-6 rounded-2xl bg-[#121520] border border-[#1e2333] space-y-2">
                  <div className="flex items-center justify-between text-gray-400 text-xs">
                    <span className="font-semibold uppercase tracking-wider text-[10px]">Designated Approvers</span>
                    <FiCalendar className="text-amber-400" />
                  </div>
                  <div className="text-2xl font-mono font-bold text-white">
                    {leave?.approvers?.length || 0} Approvers
                  </div>
                  <p className="text-xs text-gray-400">
                    {leave?.history?.length || 0} Active Passes & Gate Logs
                  </p>
                </div>

                {/* Detailed Overview Cards: Resident Profile Dossier */}
                <div className="md:col-span-2 lg:col-span-2 p-6 rounded-2xl bg-[#121520] border border-[#1e2333] space-y-4">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <FiUser className="text-cyan-400" /> Resident Profile Dossier
                  </h3>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Student Name</span>
                      <p className="text-white font-medium">{profile?.name || user?.name || user?.rollNo}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Programme</span>
                      <p className="text-white font-medium">{profile?.programme || 'Academic Programme'}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Batch / Class</span>
                      <p className="text-white font-medium">{profile?.class_name || 'Standard Batch'}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Mobile</span>
                      <p className="text-white font-mono">{profile?.mobile_number || 'Registered Mobile'}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Parent Contact</span>
                      <p className="text-white font-mono">{profile?.father_mobile || 'Parent Contact'}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Academic Year</span>
                      <p className="text-white font-mono">{hostelData?.academicYear?.[0]?.academic_year || 'Current'}</p>
                    </div>
                  </div>
                </div>

                {/* Warden & Oversight Card */}
                <div className="md:col-span-2 lg:col-span-2 p-6 rounded-2xl bg-[#121520] border border-[#1e2333] space-y-4">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <FiShield className="text-purple-400" /> Warden & Administrative Oversight
                  </h3>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Hostel Warden</span>
                      <p className="text-white font-medium">{room?.warden_name || 'Not Assigned / Unavailable'}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Resident Tutor</span>
                      <p className="text-white font-medium">{room?.resident_tutor || 'Not Assigned / Unavailable'}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1 col-span-2">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Mess Supervisor</span>
                      <p className="text-white font-medium truncate" title={mess?.mess_supervisor}>
                        {mess?.mess_supervisor || 'Not Assigned / Unavailable'}
                      </p>
                    </div>
                    <div className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1 col-span-2">
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Date of Joining</span>
                      <p className="text-white font-mono">{room?.date_of_joining || 'Not Available'}</p>
                    </div>
                  </div>
                </div>

              </div>
            )}

            {/* ROOM TAB */}
            {currentTab === 'room' && (
              <div className="bg-[#121520] border border-[#1e2333] rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
                <div className="flex items-center justify-between pb-4 border-b border-[#1e2333]">
                  <div>
                    <h2 className="text-lg font-bold text-white">Room Allotment & Facilities</h2>
                    <p className="text-xs text-gray-400">Institutional accommodation allocation on record</p>
                  </div>
                  <span className="px-3 py-1 rounded-lg text-xs font-mono font-semibold bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                    Room {room?.room_number || eligibility?.roomNumber || 'Assigned'}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Hostel Complex</span>
                    <p className="text-sm font-bold text-white">{room?.hostel_name || 'Not Available'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Block & Floor</span>
                    <p className="text-sm font-bold text-white">{room?.block_name || 'Not Available'} • {room?.floor_description || 'Not Available'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Room Type</span>
                    <p className="text-sm font-bold text-white">{room?.room_type || 'Standard Resident Room'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Date of Joining</span>
                    <p className="text-sm font-bold text-white font-mono">{room?.date_of_joining || 'Not Available'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Warden Name</span>
                    <p className="text-sm font-bold text-white">{room?.warden_name || 'Not Assigned / Unavailable'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Resident Tutor</span>
                    <p className="text-sm font-bold text-white">{room?.resident_tutor || 'Not Assigned / Unavailable'}</p>
                  </div>
                </div>
              </div>
            )}

            {/* MESS TAB */}
            {currentTab === 'mess' && (
              <div className="bg-[#121520] border border-[#1e2333] rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
                <div className="flex items-center justify-between pb-4 border-b border-[#1e2333]">
                  <div>
                    <h2 className="text-lg font-bold text-white">Mess & Dining Subscription</h2>
                    <p className="text-xs text-gray-400">Meal plans, tokens, and mess hall supervisor</p>
                  </div>
                  <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    Active Subscription
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Dining Hall</span>
                    <p className="text-sm font-bold text-white">{mess?.mess_name || 'Hostel Mess Hall'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Cuisine / Mess Type</span>
                    <p className="text-sm font-bold text-white">{mess?.mess_type || 'South Indian'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Egg Token Status</span>
                    <p className="text-sm font-bold text-white">{mess?.egg_token_status || 'No'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Non-Veg Token Status</span>
                    <p className="text-sm font-bold text-white">{mess?.non_veg_token_status || 'No'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Special Tokens Balance</span>
                    <p className="text-sm font-bold text-white font-mono">{fees?.mess_token_balance || 0} Tokens</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1 col-span-1 md:col-span-3">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Mess Supervisors</span>
                    <p className="text-sm font-medium text-white break-words">{mess?.mess_supervisor || 'Not Assigned / Unavailable'}</p>
                  </div>
                </div>
              </div>
            )}

            {/* FEES TAB */}
            {currentTab === 'fees' && (
              <div className="bg-[#121520] border border-[#1e2333] rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
                <div className="flex items-center justify-between pb-4 border-b border-[#1e2333]">
                  <div>
                    <h2 className="text-lg font-bold text-white">Hostel Fee Balances & Deposits</h2>
                    <p className="text-xs text-gray-400">Institutional fee records and caution deposits</p>
                  </div>
                  <span className="px-3 py-1 rounded-lg text-xs font-mono font-semibold bg-purple-500/10 border border-purple-500/20 text-purple-400">
                    Official Hostel Ledger
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Hostel Fee Balance</span>
                    <p className="text-xl font-bold font-mono text-white">₹ {Number(fees?.hostel_fee_balance || 0).toLocaleString('en-IN')}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Caution Deposit</span>
                    <p className="text-xl font-bold font-mono text-emerald-400">₹ {Number(fees?.caution_deposit || 0).toLocaleString('en-IN')}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Establishment Fee</span>
                    <p className="text-xl font-bold font-mono text-white">₹ {Number(fees?.establishment_fee || 0).toLocaleString('en-IN')}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] space-y-1">
                    <span className="text-gray-400 font-semibold uppercase text-[10px]">Mess Token Balance</span>
                    <p className="text-xl font-bold font-mono text-cyan-400">₹ {Number(fees?.mess_token_balance || 0).toLocaleString('en-IN')}</p>
                  </div>
                </div>

                <div className="space-y-3 pt-4 border-t border-[#1e2333]">
                  <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider">Pending Dues Ledger</h3>
                  {feeDue && feeDue.length > 0 ? (
                    <div className="space-y-2">
                      {feeDue.map((due, idx) => (
                        <div key={idx} className="p-3 rounded-xl bg-[#161a27] border border-[#22283a] flex justify-between items-center text-xs">
                          <span className="text-gray-300">{due?.description || `Hostel Dues Item ${idx + 1}`}</span>
                          <span className="font-mono font-bold text-rose-400">₹ {due?.amount || '0'}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] text-center text-xs text-gray-400">
                      No outstanding hostel dues on record.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* LEAVE TAB */}
            {currentTab === 'leave' && (
              <div className="bg-[#121520] border border-[#1e2333] rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
                <div className="flex items-center justify-between pb-4 border-b border-[#1e2333]">
                  <div>
                    <h2 className="text-lg font-bold text-white">Leave Quotas & Gate History</h2>
                    <p className="text-xs text-gray-400">Hostel gate entry logs and designated warden permissions</p>
                  </div>
                  <span className="px-3 py-1 rounded-lg text-xs font-semibold bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                    Official Approvals
                  </span>
                </div>

                {/* Designated Leave Approvers */}
                {leave?.approvers && leave.approvers.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-2">
                      <FiShield className="text-cyan-400" /> Designated Leave Approvers
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {leave.approvers.map((approver, idx) => (
                        <div key={idx} className="p-3.5 rounded-xl bg-[#161a27] border border-[#22283a] flex items-center justify-between text-xs">
                          <div>
                            <p className="font-bold text-white">{approver.staff_name || 'Staff'}</p>
                            <p className="text-[11px] text-gray-400 font-mono">Staff ID: {approver.staff_id || 'N/A'}</p>
                          </div>
                          <span className="px-2.5 py-1 rounded-lg text-[10px] font-semibold bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                            Hostel Authority
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Leave Quota Summary */}
                {leave?.summary && leave.summary.length > 0 && (
                  <div className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] flex items-center justify-between text-xs">
                    <div>
                      <span className="text-gray-400 text-[10px] uppercase font-semibold">Allocated Leave Quota</span>
                      <p className="text-sm font-bold text-white">
                        {leave.summary[0]?.allocated_days ?? 0} Days ({leave.summary[0]?.leave_type || 'Regular'})
                      </p>
                    </div>
                    <span className="text-[11px] text-gray-400 font-mono">Per Institutional Guidelines</span>
                  </div>
                )}

                {/* Gate Entry & Leave History */}
                <div className="space-y-3 pt-2">
                  <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider">Leave Applications & History</h3>
                  {leave?.history && leave.history.length > 0 ? (
                    <div className="space-y-3">
                      {leave.history.map((l, idx) => (
                        <div key={idx} className="p-4 rounded-xl bg-[#161a27] border border-[#22283a] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                          <div className="space-y-1">
                            <div className="font-bold text-white flex items-center gap-2">
                              <span>{l?.leave_type || 'Hostel Leave Pass'}</span>
                              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-semibold">
                                {l?.status || 'Approved'}
                              </span>
                            </div>
                            <p className="text-gray-400 text-[11px]">{l?.reason || 'Home Visit / Academic Event'}</p>
                          </div>
                          <div className="text-right text-gray-400 font-mono text-[11px]">
                            <span>From: {l?.from_date || 'N/A'}</span>
                            <span className="mx-2">•</span>
                            <span>To: {l?.to_date || 'N/A'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 rounded-xl bg-[#161a27] border border-[#22283a] text-center text-xs text-gray-400">
                      No active leave records on file for the current semester.
                    </div>
                  )}
                </div>
              </div>
            )}

          </div>
        )}

      </div>
    </div>
  );
}
