import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  FiCheckCircle, 
  FiCalendar, 
  FiFileText, 
  FiClock, 
  FiArrowRight 
} from 'react-icons/fi';

const Home = () => {
  const [stats, setStats] = useState({
    students_registered: 0,
    notifications_sent: 0,
    loading: true
  });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/stats');
        if (response.ok) {
          const data = await response.json();
          setStats({
            students_registered: data.studentsRegistered ?? data.students_registered ?? 0,
            notifications_sent: data.notificationsDelivered ?? data.notifications_sent ?? 0,
            loading: false
          });
        } else {
          setStats(prev => ({ ...prev, loading: false }));
        }
      } catch (err) {
        console.error('Error loading stats:', err);
        setStats(prev => ({ ...prev, loading: false }));
      }
    };

    fetchStats();
  }, []);

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6]">
      
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center">
        {/* Subtle Accent Glow */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-64 bg-purple-600/10 blur-[120px] pointer-events-none rounded-full" />

        <div className="relative z-10 space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#161a26] border border-[#262c3e] text-xs text-purple-300 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
            Designed for PSG Tech Students
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white max-w-3xl mx-auto leading-tight">
            Student Sync
          </h1>

          <p className="text-lg sm:text-xl text-gray-400 max-w-2xl mx-auto font-normal leading-relaxed">
            Stay updated with attendance, marks, results, timetable, and examination information in one unified platform.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
            <Link 
              to="/register" 
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-white text-gray-950 hover:bg-gray-100 font-semibold text-sm transition-all shadow-sm"
            >
              <span>Get Started</span>
              <FiArrowRight className="text-sm" />
            </Link>

            <Link 
              to="/login" 
              className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg bg-[#151924] hover:bg-[#1d2232] border border-[#272d3e] text-gray-300 hover:text-white font-medium text-sm transition-all"
            >
              Login to Account
            </Link>
          </div>
        </div>
      </section>

      {/* Real Statistics Section */}
      <section className="py-12 border-y border-[#181c28] bg-[#0e1118]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 text-center sm:text-left">
            <div className="p-6 rounded-xl bg-[#131620] border border-[#222738]">
              <div className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                {stats.loading ? '—' : stats.students_registered}
              </div>
              <div className="text-sm font-semibold text-purple-400 mt-1">Students Registered</div>
              <p className="text-xs text-gray-400 mt-1">Active verified students registered on Student Sync.</p>
            </div>

            <div className="p-6 rounded-xl bg-[#131620] border border-[#222738]">
              <div className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                {stats.loading ? '—' : stats.notifications_sent}
              </div>
              <div className="text-sm font-semibold text-purple-400 mt-1">Notifications Delivered</div>
              <p className="text-xs text-gray-400 mt-1">Total verified notifications delivered to student email inboxes.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
        <div className="text-center space-y-3 mb-14">
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Academic Information at a Glance
          </h2>
          <p className="text-sm text-gray-400 max-w-xl mx-auto">
            Everything you need across your college semester in one clean, distraction-free interface.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div className="p-6 rounded-xl bg-[#131620] border border-[#222738] hover:border-[#333a4f] transition-all">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-4">
              <FiCheckCircle className="text-lg" />
            </div>
            <h3 className="text-base font-semibold text-white mb-1.5">Attendance Alerts</h3>
            <p className="text-xs text-gray-400 leading-relaxed">
              Subject-wise percentage tracking to stay ahead of requirements.
            </p>
          </div>

          <div className="p-6 rounded-xl bg-[#131620] border border-[#222738] hover:border-[#333a4f] transition-all">
            <div className="w-10 h-10 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center mb-4">
              <FiFileText className="text-lg" />
            </div>
            <h3 className="text-base font-semibold text-white mb-1.5">Mark Updates</h3>
            <p className="text-xs text-gray-400 leading-relaxed">
              Continuous assessment marks and internal test score breakdown.
            </p>
          </div>

          <div className="p-6 rounded-xl bg-[#131620] border border-[#222738] hover:border-[#333a4f] transition-all">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center mb-4">
              <FiCalendar className="text-lg" />
            </div>
            <h3 className="text-base font-semibold text-white mb-1.5">Timetable Updates</h3>
            <p className="text-xs text-gray-400 leading-relaxed">
              Test schedules, dates, and subject session slots in one schedule view.
            </p>
          </div>

          <div className="p-6 rounded-xl bg-[#131620] border border-[#222738] hover:border-[#333a4f] transition-all">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center mb-4">
              <FiClock className="text-lg" />
            </div>
            <h3 className="text-base font-semibold text-white mb-1.5">Exam Schedule</h3>
            <p className="text-xs text-gray-400 leading-relaxed">
              Examination hall seating arrangements available prior to test days.
            </p>
          </div>
        </div>
      </section>

      {/* About Student Sync Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 border-t border-[#181c28] bg-[#0e1118]">
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
            About Student Sync
          </h2>
          <p className="text-sm text-gray-400 leading-relaxed font-normal">
            Student Sync brings important academic information together in one place and helps students stay informed about attendance, marks, examinations, and academic updates.
          </p>
          <div className="pt-2">
            <Link 
              to="/about"
              className="inline-flex items-center gap-1.5 text-xs text-purple-400 hover:text-purple-300 font-medium"
            >
              <span>Meet the developers</span>
              <FiArrowRight className="text-xs" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-[#181c28] text-center text-xs text-gray-500">
        <p>© 2026 Student Sync | All rights reserved.</p>
      </footer>

    </div>
  );
};

export default Home;