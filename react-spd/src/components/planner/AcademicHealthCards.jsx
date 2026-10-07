import React from 'react';
import { 
  FiCheckCircle, 
  FiAward, 
  FiBookOpen, 
  FiCalendar, 
  FiAlertTriangle, 
  FiActivity,
  FiFileText
} from 'react-icons/fi';

const AcademicHealthCards = ({ student, attendance, academicHealth, registeredExamsSummary }) => {
  const attPct = attendance?.percentage ?? 0;
  const safeBunks = attendance?.safe_bunks ?? 0;
  const isHealthy = attPct >= 75.0;

  const cgpa = student?.cgpa ?? 'N/A';
  const credits = student?.verified_historical_credits ?? 0;
  const activeCourses = student?.active_courses_count ?? 8;

  const pendingCA = academicHealth?.total_pending_ca ?? 0;
  const enteredCA = academicHealth?.total_entered_ca ?? 0;
  const highPriority = academicHealth?.high_priority_count ?? 0;
  const attentionNeeded = academicHealth?.attention_needed_count ?? 0;

  const registeredExams = registeredExamsSummary?.total_registered ?? 0;
  const examStatus = registeredExamsSummary?.schedule_status ?? 'Schedule Pending';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {/* 1. Overall Attendance */}
      <div className="bg-[#151922] border border-[#232938] rounded-xl p-5 shadow-sm hover:border-[#343c52] transition-all relative overflow-hidden group">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-400">Overall Attendance</span>
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            isHealthy ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
          }`}>
            <FiCheckCircle className="text-base" />
          </div>
        </div>
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-2xl sm:text-3xl font-bold text-white tracking-tight">{attPct.toFixed(2)}%</span>
          <span className="text-xs text-gray-400">({attendance?.attended}/{attendance?.conducted})</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
          <span>{safeBunks} safe bunk{safeBunks !== 1 ? 's' : ''} available</span>
        </div>
        <div className="w-full bg-[#1e2330] rounded-full h-1.5 mt-3 overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${isHealthy ? 'bg-emerald-500' : 'bg-amber-500'}`}
            style={{ width: `${Math.min(attPct, 100)}%` }}
          />
        </div>
      </div>

      {/* 2. Cumulative GPA & Credits */}
      <div className="bg-[#151922] border border-[#232938] rounded-xl p-5 shadow-sm hover:border-[#343c52] transition-all relative overflow-hidden group">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-400">Cumulative GPA</span>
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center">
            <FiAward className="text-base" />
          </div>
        </div>
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-2xl sm:text-3xl font-bold text-white tracking-tight">{cgpa}</span>
          <span className="text-xs text-gray-400">/ 10.00</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-purple-300 font-medium">
          <span>{credits.toFixed(1)} verified credits completed</span>
        </div>
        <div className="w-full bg-[#1e2330] rounded-full h-1.5 mt-3 overflow-hidden">
          <div 
            className="h-full rounded-full bg-purple-500 transition-all duration-500"
            style={{ width: `${Math.min((parseFloat(cgpa) || 0) * 10, 100)}%` }}
          />
        </div>
      </div>

      {/* 3. Active Courses & Attention */}
      <div className="bg-[#151922] border border-[#232938] rounded-xl p-5 shadow-sm hover:border-[#343c52] transition-all relative overflow-hidden group">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-400">Active Courses</span>
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center">
            <FiBookOpen className="text-base" />
          </div>
        </div>
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-2xl sm:text-3xl font-bold text-white tracking-tight">{activeCourses}</span>
          <span className="text-xs text-gray-400">registered</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          {attentionNeeded > 0 ? (
            <span className="text-amber-400 font-medium flex items-center gap-1">
              <FiAlertTriangle className="text-xs" />
              {attentionNeeded} course{attentionNeeded !== 1 ? 's' : ''} need attention
            </span>
          ) : (
            <span className="text-emerald-400 font-medium">All courses stable</span>
          )}
        </div>
        <div className="w-full bg-[#1e2330] rounded-full h-1.5 mt-3 overflow-hidden">
          <div 
            className="h-full rounded-full bg-blue-500 transition-all duration-500"
            style={{ width: `${((activeCourses - attentionNeeded) / (activeCourses || 1)) * 100}%` }}
          />
        </div>
      </div>

      {/* 4. Examination & Assessment Status */}
      <div className="bg-[#151922] border border-[#232938] rounded-xl p-5 shadow-sm hover:border-[#343c52] transition-all relative overflow-hidden group">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-400">Assessments & Exams</span>
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center">
            <FiCalendar className="text-base" />
          </div>
        </div>
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-2xl sm:text-3xl font-bold text-white tracking-tight">{registeredExams}</span>
          <span className="text-xs text-gray-400">theory exams</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="px-1.5 py-0.5 rounded bg-[#1e2330] border border-[#2e3547] text-indigo-300 font-medium text-[11px]">
            {examStatus}
          </span>
          <span>{pendingCA} pending CA</span>
        </div>
        <div className="w-full bg-[#1e2330] rounded-full h-1.5 mt-3 overflow-hidden">
          <div 
            className="h-full rounded-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${(enteredCA / (enteredCA + pendingCA || 1)) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};

export default AcademicHealthCards;
