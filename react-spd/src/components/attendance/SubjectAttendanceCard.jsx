import React from 'react';
import { 
  FiCheckCircle, 
  FiAlertTriangle, 
  FiAlertCircle, 
  FiSliders,
  FiTrendingUp,
  FiTrendingDown
} from 'react-icons/fi';

const SubjectAttendanceCard = ({ subject, target = 75, isSelected, onSelect }) => {
  if (!subject) return null;

  const code = subject.code || '';
  const name = subject.name || code;
  const attended = subject.attended ?? 0;
  const conducted = subject.conducted ?? 0;
  const absent = subject.absent ?? Math.max(0, conducted - attended);
  const exemptHr = subject.exempt_hr ?? 0;
  const percentage = subject.percentage ?? 0;
  const status = subject.status ?? (percentage >= target ? 'SAFE' : percentage >= 65 ? 'WARNING' : 'CRITICAL');
  const safeBunks = subject.safe_bunks ?? 0;
  const requiredClasses = subject.required_classes ?? 0;

  const getStatusBadge = () => {
    switch (status) {
      case 'SAFE':
        return {
          badge: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
          dot: 'bg-emerald-400',
          bar: 'bg-emerald-500',
          bunkText: 'text-emerald-400',
          bunkBg: 'bg-emerald-950/20 border-emerald-500/30'
        };
      case 'WARNING':
        return {
          badge: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
          dot: 'bg-amber-400',
          bar: 'bg-amber-500',
          bunkText: 'text-amber-400',
          bunkBg: 'bg-amber-950/20 border-amber-500/30'
        };
      case 'CRITICAL':
      default:
        return {
          badge: 'bg-rose-500/10 border-rose-500/20 text-rose-400',
          dot: 'bg-rose-400',
          bar: 'bg-rose-500',
          bunkText: 'text-rose-400',
          bunkBg: 'bg-rose-950/20 border-rose-500/30'
        };
    }
  };

  const styling = getStatusBadge();

  return (
    <div 
      className={`rounded-xl p-5 bg-[#131620] border transition-all duration-200 flex flex-col justify-between space-y-4 shadow-sm hover:shadow-md ${
        isSelected 
          ? 'border-purple-500 ring-1 ring-purple-500/50 bg-[#161a27]' 
          : 'border-[#232738] hover:border-[#2f354b]'
      }`}
    >
      {/* Top Header */}
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#1c2132] border border-[#282f45] text-purple-300">
            {code}
          </span>
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${styling.badge}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${styling.dot}`} />
            {status}
          </span>
        </div>

        <h3 className="text-sm font-semibold text-white line-clamp-2 leading-snug">
          {name}
        </h3>
      </div>

      {/* Percentage & Progress Bar */}
      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-gray-400 font-medium">Attendance</span>
          <span className="text-xl font-bold font-mono text-white">
            {percentage.toFixed(2)}%
          </span>
        </div>

        <div className="w-full bg-[#1b1f2e] h-2 rounded-full overflow-hidden border border-[#252a3b] p-0.5">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${styling.bar}`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>

        <div className="flex justify-between items-center text-[10px] text-gray-500 font-mono">
          <span>Attended: {attended} / {conducted}</span>
          <span>Target: {target}%</span>
        </div>
      </div>

      {/* Grid of Course Counts */}
      <div className="grid grid-cols-3 gap-2 p-2.5 rounded-lg bg-[#181c2b] border border-[#222738] text-[11px]">
        <div>
          <div className="text-gray-400 text-[10px]">Attended</div>
          <div className="font-bold text-white font-mono mt-0.5">{attended}</div>
        </div>
        <div>
          <div className="text-gray-400 text-[10px]">Absent</div>
          <div className="font-bold text-rose-400 font-mono mt-0.5">{absent}</div>
        </div>
        <div>
          <div className="text-gray-400 text-[10px]">Exempt</div>
          <div className="font-bold text-purple-300 font-mono mt-0.5">{exemptHr}</div>
        </div>
      </div>

      {/* Safe Bunk or Recovery Status Box */}
      <div className={`p-3 rounded-lg border text-xs ${styling.bunkBg}`}>
        {percentage >= target ? (
          <div className="flex items-center justify-between">
            <span className="text-gray-300">Safe Bunks:</span>
            <span className="font-bold font-mono text-emerald-400">
              {safeBunks} {safeBunks === 1 ? 'class' : 'classes'}
            </span>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <span className="text-gray-300">Need to attend:</span>
            <span className="font-bold font-mono text-rose-400">
              {requiredClasses} {requiredClasses === 1 ? 'class' : 'classes'}
            </span>
          </div>
        )}
      </div>

      {/* Quick Action Button */}
      <button
        onClick={() => onSelect && onSelect(code)}
        className={`w-full py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
          isSelected
            ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20'
            : 'bg-[#1a1f2e] text-purple-300 hover:bg-[#22283b] hover:text-white border border-[#272e42]'
        }`}
      >
        <FiSliders size={12} />
        <span>{isSelected ? 'Selected in Simulator' : 'Simulate & Plan'}</span>
      </button>
    </div>
  );
};

export default SubjectAttendanceCard;
