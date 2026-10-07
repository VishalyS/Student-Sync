import React from 'react';
import { 
  FiCheckCircle, 
  FiAlertTriangle, 
  FiTarget, 
  FiBookOpen, 
  FiTrendingUp,
  FiTrendingDown,
  FiSliders
} from 'react-icons/fi';

const BunkPlanner = ({ 
  subjects = [], 
  selectedSubjectCode, 
  onSubjectChange, 
  target = 75, 
  onTargetChange,
  onOpenSimulator 
}) => {
  const activeSubject = subjects.find(s => s.code === selectedSubjectCode) || subjects[0] || null;
  const targetOptions = [75, 80, 85, 90];

  if (!activeSubject) {
    return null;
  }

  const percentage = activeSubject.percentage ?? 0;
  const isAboveTarget = percentage >= target;
  const safeBunks = activeSubject.safe_bunks ?? 0;
  const requiredClasses = activeSubject.required_classes ?? 0;

  return (
    <div className="bg-[#131620] border border-[#232738] rounded-xl p-5 sm:p-7 shadow-sm space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#1f2434]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <FiTarget className="text-sm" />
          </div>
          <div>
            <h2 className="text-base sm:text-lg font-semibold text-white">Bunk Planner & Attendance Recovery</h2>
            <p className="text-xs text-gray-400">
              Calculate exact permissible bunks or classes needed to hit target percentage
            </p>
          </div>
        </div>

        {/* Target Selector Buttons */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto">
          <span className="text-xs text-gray-400 mr-1 font-mono">Target:</span>
          {targetOptions.map((tgt) => (
            <button
              key={tgt}
              onClick={() => onTargetChange && onTargetChange(tgt)}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold font-mono transition-all ${
                target === tgt
                  ? 'bg-purple-600 text-white border border-purple-500'
                  : 'bg-[#181c2b] text-gray-300 hover:text-white border border-[#262c3d]'
              }`}
            >
              {tgt}%
            </button>
          ))}
        </div>
      </div>

      {/* Subject Dropdown & Quick Selector */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
        <div className="md:col-span-8 space-y-1.5">
          <label htmlFor="planner-subject-select" className="block text-xs font-medium text-gray-300">
            Select Enrolled Subject:
          </label>
          <div className="relative">
            <select
              id="planner-subject-select"
              value={activeSubject.code}
              onChange={(e) => onSubjectChange && onSubjectChange(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-[#0e111a] border border-[#282e42] rounded-lg text-sm text-white focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
            >
              {subjects.map((s) => (
                <option key={s.code} value={s.code} className="bg-[#131620] text-white">
                  {s.name} ({s.code}) — {s.percentage.toFixed(1)}%
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Current Attendance Display */}
        <div className="md:col-span-4 p-3.5 rounded-lg bg-[#181c2b] border border-[#23283b] flex items-center justify-between">
          <div>
            <div className="text-[11px] text-gray-400 uppercase tracking-wide">Current Attendance</div>
            <div className="text-xl font-bold font-mono text-white mt-0.5">
              {percentage.toFixed(2)}%
            </div>
          </div>
          <span className={`text-[11px] font-bold px-2 py-0.5 rounded border ${
            isAboveTarget 
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
              : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
          }`}>
            {isAboveTarget ? 'Above Target' : 'Below Target'}
          </span>
        </div>
      </div>

      {/* Outcome Presentation Card */}
      {isAboveTarget ? (
        <div className="p-5 sm:p-6 rounded-xl bg-emerald-950/20 border border-emerald-500/30 text-emerald-200 space-y-3">
          <div className="flex items-center gap-2">
            <FiCheckCircle className="text-emerald-400 text-lg flex-shrink-0" />
            <span className="text-xs font-bold uppercase tracking-wide text-emerald-400">
              Safe Bunk Allowance
            </span>
          </div>

          <div className="text-xl sm:text-2xl font-bold text-white leading-relaxed">
            You can safely bunk: <span className="font-extrabold font-mono text-emerald-400 text-2xl sm:text-3xl">{safeBunks}</span> {safeBunks === 1 ? 'class' : 'classes'}
          </div>

          <p className="text-xs text-emerald-300/80 leading-relaxed">
            Missing {safeBunks} classes will keep your attendance at or above your target threshold of <strong className="text-white font-mono">{target}%</strong>.
            You are comfortably above the target with {activeSubject.attended} attended out of {activeSubject.conducted} conducted.
          </p>

          <div className="pt-1 flex flex-wrap items-center gap-3">
            <button
              onClick={() => onOpenSimulator && onOpenSimulator(activeSubject.code)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-xs font-semibold border border-emerald-500/30 transition-colors"
            >
              <FiSliders className="text-xs" />
              <span>Simulate what happens if you bunk →</span>
            </button>
            <span className="text-[11px] text-emerald-400/80">You are above the target.</span>
          </div>
        </div>
      ) : (
        <div className="p-5 sm:p-6 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-200 space-y-3">
          <div className="flex items-center gap-2">
            <FiAlertTriangle className="text-rose-400 text-lg flex-shrink-0" />
            <span className="text-xs font-bold uppercase tracking-wide text-rose-400">
              Attendance Recovery Roadmap
            </span>
          </div>

          <div className="text-xl sm:text-2xl font-bold text-white leading-relaxed">
            You need to attend: <span className="font-extrabold font-mono text-rose-400 text-2xl sm:text-3xl">{requiredClasses}</span> consecutive {requiredClasses === 1 ? 'class' : 'classes'}
          </div>

          <p className="text-xs text-rose-300/80 leading-relaxed">
            Current attendance is <strong className="text-white font-mono">{percentage.toFixed(2)}%</strong> (Target: <strong className="text-white font-mono">{target}%</strong>). 
            Attending the next {requiredClasses} classes without missing any will restore your attendance to the required threshold.
          </p>

          <div className="pt-1">
            <button
              onClick={() => onOpenSimulator && onOpenSimulator(activeSubject.code)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-xs font-semibold border border-rose-500/30 transition-colors"
            >
              <FiSliders className="text-xs" />
              <span>Simulate recovery attendance →</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default BunkPlanner;
