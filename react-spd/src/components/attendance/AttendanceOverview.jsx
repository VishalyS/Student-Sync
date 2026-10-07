import React from 'react';
import { 
  FiCheckCircle, 
  FiAlertTriangle, 
  FiAlertCircle, 
  FiTrendingUp, 
  FiTrendingDown,
  FiTarget,
  FiAward,
  FiBookOpen,
  FiCalendar
} from 'react-icons/fi';

const AttendanceOverview = ({ summary, target, onTargetChange, onScrollToSimulator }) => {
  if (!summary) return null;

  const totalAttended = summary.total_attended ?? 0;
  const totalConducted = summary.total_conducted ?? 0;
  const overallPercentage = summary.overall_percentage ?? 0;
  const overallStatus = summary.overall_status ?? 'SAFE';
  const overallSafeBunks = summary.overall_safe_bunks ?? 0;
  const overallRequiredClasses = summary.overall_required_classes ?? 0;
  const counts = summary.counts || { total: 0, safe: 0, warning: 0, critical: 0 };

  const getStatusColor = (status) => {
    switch (status) {
      case 'SAFE':
        return {
          badge: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
          dot: 'bg-emerald-400',
          bar: 'bg-emerald-500',
          text: 'text-emerald-400',
          border: 'border-emerald-500/20'
        };
      case 'WARNING':
        return {
          badge: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
          dot: 'bg-amber-400',
          bar: 'bg-amber-500',
          text: 'text-amber-400',
          border: 'border-amber-500/20'
        };
      case 'CRITICAL':
      default:
        return {
          badge: 'bg-rose-500/10 border-rose-500/20 text-rose-400',
          dot: 'bg-rose-400',
          bar: 'bg-rose-500',
          text: 'text-rose-400',
          border: 'border-rose-500/20'
        };
    }
  };

  const statusStyle = getStatusColor(overallStatus);
  const targetOptions = [75, 80, 85, 90];

  return (
    <div className="space-y-4">
      {/* Target Threshold Selector Bar */}
      <div className="bg-[#131620] border border-[#232738] rounded-xl p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
        <div className="flex items-center gap-2">
          <FiTarget className="text-purple-400 text-base flex-shrink-0" />
          <span className="text-xs sm:text-sm font-semibold text-white">Minimum Target Threshold:</span>
          <span className="text-xs text-gray-400 font-mono hidden sm:inline">Set your target attendance</span>
        </div>

        <div className="flex items-center gap-1.5 self-start sm:self-auto">
          {targetOptions.map((tgt) => (
            <button
              key={tgt}
              onClick={() => onTargetChange && onTargetChange(tgt)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all ${
                target === tgt
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20 border border-purple-500'
                  : 'bg-[#181c2b] text-gray-300 hover:text-white hover:bg-[#202538] border border-[#272c3e]'
              }`}
            >
              {tgt}%
            </button>
          ))}
        </div>
      </div>

      {/* Main Overall Attendance Card */}
      <div className="bg-[#131620] border border-[#232738] rounded-2xl p-6 sm:p-8 shadow-md relative overflow-hidden">
        {/* Background Accent Glow */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-600/5 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          {/* Left Column: Big Percentage & Metric */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="text-xs uppercase tracking-wider font-semibold text-gray-400">
                Official Consolidated Attendance
              </span>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusStyle.badge}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${statusStyle.dot}`} />
                {overallStatus}
              </span>
            </div>

            <div className="flex items-baseline gap-3">
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white font-mono">
                {overallPercentage.toFixed(2)}%
              </h1>
              <span className="text-xs sm:text-sm text-gray-400">
                Target: <strong className="text-white font-mono">{target}%</strong>
              </span>
            </div>

            {/* Visual Progress Bar */}
            <div className="space-y-1.5">
              <div className="w-full bg-[#1b1f2e] h-3 rounded-full overflow-hidden border border-[#252a3b] p-0.5">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${statusStyle.bar}`}
                  style={{ width: `${Math.min(overallPercentage, 100)}%` }}
                />
              </div>
              <div className="flex justify-between items-center text-[11px] text-gray-400 font-mono">
                <span>0%</span>
                <span className="text-purple-400 font-semibold">Target {target}%</span>
                <span>100%</span>
              </div>
            </div>

            {/* Attended vs Conducted Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
              <div className="p-3 rounded-xl bg-[#181c2b] border border-[#232738]">
                <div className="text-[11px] text-gray-400 uppercase tracking-wide">Attended</div>
                <div className="text-xl font-bold text-white font-mono mt-0.5">{totalAttended}</div>
                <div className="text-[10px] text-gray-500">Lectures present</div>
              </div>

              <div className="p-3 rounded-xl bg-[#181c2b] border border-[#232738]">
                <div className="text-[11px] text-gray-400 uppercase tracking-wide">Conducted</div>
                <div className="text-xl font-bold text-white font-mono mt-0.5">{totalConducted}</div>
                <div className="text-[10px] text-gray-500">Total sessions</div>
              </div>

              <div className="p-3 rounded-xl bg-[#181c2b] border border-[#232738] col-span-2 sm:col-span-1">
                <div className="text-[11px] text-gray-400 uppercase tracking-wide">Absent</div>
                <div className="text-xl font-bold text-rose-400 font-mono mt-0.5">{Math.max(0, totalConducted - totalAttended)}</div>
                <div className="text-[10px] text-gray-500">Sessions missed</div>
              </div>
            </div>
          </div>

          {/* Right Column: Safe Bunks / Recovery Spotlight Card */}
          <div className="lg:col-span-5 flex flex-col justify-center">
            {overallPercentage >= target ? (
              <div className="p-5 sm:p-6 rounded-xl bg-emerald-950/20 border border-emerald-500/30 text-emerald-200 space-y-3">
                <div className="flex items-center gap-2">
                  <FiCheckCircle className="text-emerald-400 text-lg flex-shrink-0" />
                  <span className="text-xs uppercase tracking-wide font-bold text-emerald-400">
                    Safe Bunk Reserve
                  </span>
                </div>

                <div>
                  <div className="text-3xl sm:text-4xl font-extrabold font-mono text-white">
                    {overallSafeBunks} {overallSafeBunks === 1 ? 'Class' : 'Classes'}
                  </div>
                  <p className="text-xs text-emerald-300/80 mt-1.5 leading-relaxed">
                    You can safely miss up to <strong className="text-emerald-200 font-semibold">{overallSafeBunks}</strong> aggregate classes and still maintain your target attendance of <strong className="text-emerald-200 font-semibold">{target}%</strong>.
                  </p>
                </div>

                <div className="pt-2">
                  <button
                    onClick={onScrollToSimulator}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-xs font-semibold border border-emerald-500/30 transition-colors"
                  >
                    <FiTrendingUp className="text-xs" />
                    <span>Simulate Bunks in Simulator ↓</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-5 sm:p-6 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-200 space-y-3">
                <div className="flex items-center gap-2">
                  <FiAlertTriangle className="text-rose-400 text-lg flex-shrink-0" />
                  <span className="text-xs uppercase tracking-wide font-bold text-rose-400">
                    Recovery Required
                  </span>
                </div>

                <div>
                  <div className="text-3xl sm:text-4xl font-extrabold font-mono text-white">
                    {overallRequiredClasses} {overallRequiredClasses === 1 ? 'Class' : 'Classes'}
                  </div>
                  <p className="text-xs text-rose-300/80 mt-1.5 leading-relaxed">
                    You must attend the next <strong className="text-rose-200 font-semibold">{overallRequiredClasses}</strong> consecutive classes without missing to reach your target attendance of <strong className="text-rose-200 font-semibold">{target}%</strong>.
                  </p>
                </div>

                <div className="pt-2">
                  <button
                    onClick={onScrollToSimulator}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-xs font-semibold border border-rose-500/30 transition-colors"
                  >
                    <FiTrendingUp className="text-xs" />
                    <span>Plan Recovery in Simulator ↓</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Bottom Category Status Pill Strip */}
        <div className="mt-6 pt-4 border-t border-[#1f2435] grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4 text-xs">
          <div className="flex items-center gap-2 text-gray-400">
            <FiBookOpen className="text-gray-500" />
            <span>Total Enrolled: <strong className="text-white font-mono">{counts.total}</strong></span>
          </div>
          <div className="flex items-center gap-2 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>Safe (≥{target}%): <strong className="text-white font-mono">{counts.safe}</strong></span>
          </div>
          <div className="flex items-center gap-2 text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>Warning (65-74%): <strong className="text-white font-mono">{counts.warning}</strong></span>
          </div>
          <div className="flex items-center gap-2 text-rose-400">
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            <span>Critical (&lt;65%): <strong className="text-white font-mono">{counts.critical}</strong></span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AttendanceOverview;
