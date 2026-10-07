import React, { useState, useEffect } from 'react';
import { 
  FiClock, 
  FiSave, 
  FiRotateCcw, 
  FiCheck, 
  FiShield, 
  FiZap,
  FiSliders,
  FiBookOpen
} from 'react-icons/fi';

const StudyGoalAllocator = ({ subjectMatrix = [], rollNo }) => {
  const storageKey = `student_sync_study_goals_${rollNo || 'guest'}`;

  // State: course code -> target study hours per week (0 to 10)
  const [goals, setGoals] = useState({});
  const [savedFeedback, setSavedFeedback] = useState(false);

  // Load from localStorage on mount or when rollNo changes
  useEffect(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (typeof parsed === 'object' && parsed !== null) {
          setGoals(parsed);
          return;
        }
      }
    } catch (e) {
      console.warn('Could not read study goals from localStorage:', e);
    }

    // Default initialization: 0 hours per subject
    const initial = {};
    subjectMatrix.forEach((s) => {
      initial[s.code] = 0;
    });
    setGoals(initial);
  }, [storageKey, subjectMatrix]);

  const handleHoursChange = (code, val) => {
    const num = Math.max(0, Math.min(10, parseInt(val) || 0));
    setGoals((prev) => ({
      ...prev,
      [code]: num
    }));
  };

  const handleSave = () => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(goals));
      setSavedFeedback(true);
      setTimeout(() => setSavedFeedback(false), 3000);
    } catch (e) {
      console.error('Failed to save study goals:', e);
    }
  };

  const handleReset = () => {
    const reset = {};
    subjectMatrix.forEach((s) => {
      reset[s.code] = 0;
    });
    setGoals(reset);
    try {
      localStorage.removeItem(storageKey);
    } catch (e) {
      // ignore
    }
    setSavedFeedback(false);
  };

  const handleAutoSuggest = () => {
    // Automatically suggest hours based on priority score (purely in-browser client helper)
    const suggested = {};
    subjectMatrix.forEach((s) => {
      const score = s.priority?.score || 0;
      if (score >= 60) {
        suggested[s.code] = 4; // High priority: 4 hrs
      } else if (score >= 35) {
        suggested[s.code] = 2; // Medium priority: 2 hrs
      } else {
        suggested[s.code] = 1; // Routine: 1 hr
      }
    });
    setGoals(suggested);
  };

  const totalWeeklyHours = Object.values(goals).reduce((acc, curr) => acc + (curr || 0), 0);

  return (
    <div className="bg-[#151922] border border-[#232938] rounded-2xl p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-[#232938]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase tracking-wider">
              Interactive Planner
            </span>
            <span className="text-xs text-gray-400">Zero-Write Local Storage</span>
          </div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FiSliders className="text-emerald-400" />
            Weekly Study Goal Allocator
          </h2>
          <p className="text-xs sm:text-sm text-gray-400 mt-0.5">
            Plan your target weekly study hours for each subject based on current priorities.
          </p>
        </div>

        {/* Total Target Indicator */}
        <div className="flex items-center gap-3">
          <div className="bg-[#0e1118] px-4 py-2 rounded-xl border border-[#232938] text-right">
            <span className="text-[11px] text-gray-400 block uppercase font-medium">Target Weekly Study</span>
            <span className="text-lg font-bold text-emerald-400 font-mono">
              {totalWeeklyHours} <span className="text-xs text-gray-400 font-normal">hrs / week</span>
            </span>
          </div>
        </div>
      </div>

      {/* Action Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 py-3 px-4 bg-[#0e1118]/60 border border-[#1e2330] rounded-xl my-4 text-xs">
        <div className="flex items-center gap-2">
          <button
            onClick={handleAutoSuggest}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a202d] hover:bg-[#252e42] text-gray-300 hover:text-white border border-[#2d374d] transition-all font-medium"
          >
            <FiZap className="text-amber-400" />
            Auto-Suggest by Priority
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-transparent hover:bg-[#1a202d] text-gray-400 hover:text-gray-200 transition-all font-medium"
          >
            <FiRotateCcw className="text-xs" />
            Reset All
          </button>
        </div>

        <div className="flex items-center gap-2">
          {savedFeedback && (
            <span className="text-emerald-400 text-xs font-medium flex items-center gap-1 animate-fade-in">
              <FiCheck className="text-sm" />
              Saved to device
            </span>
          )}
          <button
            onClick={handleSave}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-all shadow-sm"
          >
            <FiSave className="text-sm" />
            Save Goals
          </button>
        </div>
      </div>

      {/* Sliders Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        {subjectMatrix.map((item) => {
          const currentHours = goals[item.code] ?? 0;
          const prio = item.priority || {};
          const isHighPrio = prio.level === 'HIGH';

          return (
            <div 
              key={item.code}
              className={`p-4 rounded-xl bg-[#0e1118] border transition-all ${
                isHighPrio ? 'border-purple-500/30 bg-[#0e1118]/90' : 'border-[#232938]'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="font-mono text-xs font-bold text-purple-400 mr-2">
                    {item.code}
                  </span>
                  <span className="text-xs font-semibold text-white truncate max-w-[200px] inline-block align-bottom" title={item.name}>
                    {item.name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-sm font-bold text-emerald-400">
                    {currentHours}
                  </span>
                  <span className="text-[11px] text-gray-500">hrs</span>
                </div>
              </div>

              {/* Slider Control */}
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="1"
                  value={currentHours}
                  onChange={(e) => handleHoursChange(item.code, e.target.value)}
                  className="w-full accent-emerald-500 bg-[#1e2433] h-1.5 rounded-lg cursor-pointer"
                />
              </div>

              {/* Sub-info */}
              <div className="flex items-center justify-between text-[11px] text-gray-500 mt-2">
                <span>Attendance: {item.attendance?.percentage?.toFixed(1)}%</span>
                <span className={isHighPrio ? 'text-purple-400 font-medium' : 'text-gray-500'}>
                  Priority: {prio.level}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Privacy Notice Banner */}
      <div className="flex items-center gap-2 mt-6 p-3 rounded-xl bg-[#111622] border border-[#202737] text-xs text-gray-400">
        <FiShield className="text-emerald-400 text-sm shrink-0" />
        <span>
          <strong className="text-gray-300">Privacy Notice:</strong> Study goals are stored privately on this device. Official academic records remain untouched.
        </span>
      </div>
    </div>
  );
};

export default StudyGoalAllocator;
