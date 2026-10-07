import React, { useState, useEffect } from 'react';
import { 
  FiSliders, 
  FiAlertTriangle, 
  FiCheckCircle, 
  FiAlertCircle, 
  FiRotateCcw, 
  FiTrendingDown,
  FiZap,
  FiClock
} from 'react-icons/fi';

const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

const DayBunkSimulator = ({ weeklySchedule, onSimulateRemote, authToken, rollNo }) => {
  const [selectedDay, setSelectedDay] = useState('Friday');
  const [selectedPeriods, setSelectedPeriods] = useState([1, 3]);
  const [targetAttendance, setTargetAttendance] = useState(75.0);
  const [simResult, setSimResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Find periods for current selected day from weeklySchedule
  const daySchedule = weeklySchedule?.days?.find(
    d => d.day.toLowerCase() === selectedDay.toLowerCase()
  ) || weeklySchedule?.days?.[0];

  const scheduledPeriods = daySchedule?.periods?.filter(p => !p.is_free && p.code !== 'FREE') || [];

  // Handle toggling period checkbox
  const handleTogglePeriod = (pNum) => {
    if (selectedPeriods.includes(pNum)) {
      setSelectedPeriods(selectedPeriods.filter(p => p !== pNum));
    } else {
      setSelectedPeriods([...selectedPeriods, pNum].sort((a, b) => a - b));
    }
  };

  const handleSelectAllScheduled = () => {
    setSelectedPeriods(scheduledPeriods.map(p => p.period));
  };

  const handleClearSelection = () => {
    setSelectedPeriods([]);
    setSimResult(null);
  };

  const handleReset = () => {
    setSelectedDay('Friday');
    setSelectedPeriods([1, 3]);
    setTargetAttendance(75.0);
    setSimResult(null);
    setError('');
  };

  // Run simulation via API endpoint
  const runSimulation = async () => {
    if (selectedPeriods.length === 0) {
      setError('Please select at least one class period to simulate.');
      return;
    }

    setLoading(true);
    setError('');

    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const queryParams = new URLSearchParams();
    if (authToken) queryParams.set('auth_token', authToken);
    if (rollNo) queryParams.set('rollNo', rollNo);

    try {
      const resp = await fetch(`/api/schedule/day-bunk-simulate?${queryParams.toString()}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          day: selectedDay,
          periods: selectedPeriods,
          target: targetAttendance
        })
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        setError(errJson.error || `Simulation failed with HTTP ${resp.status}`);
        return;
      }

      const data = await resp.json();
      setSimResult(data);
    } catch (err) {
      setError(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Auto-run simulation on mount or day change
  useEffect(() => {
    if (authToken && selectedPeriods.length > 0) {
      runSimulation();
    }
  }, [selectedDay]);

  return (
    <div className="space-y-5">
      {/* Configuration Header Card */}
      <div className="p-6 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#1c202e]">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-white">Schedule-Aware Day-Bunk Simulator</h2>
              <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300 font-mono">
                100% In-Memory
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Select upcoming lecture periods to evaluate exact subject-level attendance drops and safe-bunk shifts
            </p>
          </div>

          <button
            onClick={handleReset}
            className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#181c2b] hover:bg-[#23283b] border border-[#2b3145] text-xs font-medium text-gray-300 hover:text-white transition-all"
          >
            <FiRotateCcw size={12} className="text-purple-400" />
            <span>Reset</span>
          </button>
        </div>

        {/* Step 1: Select Day of Week */}
        <div className="space-y-2">
          <label className="block text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
            1. Select Target Day
          </label>
          <div className="flex flex-wrap gap-2">
            {DAYS_OF_WEEK.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => {
                  setSelectedDay(d);
                  setSelectedPeriods([]);
                  setSimResult(null);
                }}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  selectedDay.toLowerCase() === d.toLowerCase()
                    ? 'bg-purple-600 text-white shadow-md shadow-purple-600/25 border border-purple-500'
                    : 'bg-[#181c2b] text-gray-400 hover:text-gray-200 border border-[#24293c]'
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        {/* Step 2: Select Periods on that day */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="block text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
              2. Select Periods to Bunk on {selectedDay}
            </label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSelectAllScheduled}
                className="text-[11px] text-purple-400 hover:text-purple-300 underline"
              >
                Select Full Day ({scheduledPeriods.length} classes)
              </button>
              <span className="text-gray-600">•</span>
              <button
                type="button"
                onClick={handleClearSelection}
                className="text-[11px] text-gray-500 hover:text-gray-300 underline"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {daySchedule?.periods?.map((p) => {
              const isFree = p.is_free || p.code === 'FREE';
              const isChecked = selectedPeriods.includes(p.period);

              return (
                <div
                  key={p.period}
                  onClick={() => !isFree && handleTogglePeriod(p.period)}
                  className={`p-3 rounded-lg border text-xs cursor-pointer transition-all flex items-center justify-between ${
                    isFree
                      ? 'bg-[#10131d]/40 border-[#1c202d] text-gray-600 cursor-not-allowed opacity-60'
                      : isChecked
                        ? 'bg-purple-950/30 border-purple-500/50 text-white shadow-sm'
                        : 'bg-[#171b28] border-[#24293c] text-gray-300 hover:border-[#32394e]'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={isFree}
                      onChange={() => !isFree && handleTogglePeriod(p.period)}
                      className="rounded border-gray-600 text-purple-600 focus:ring-purple-500 cursor-pointer"
                    />
                    <div>
                      <div className="font-bold font-mono text-[11px] flex items-center gap-1.5">
                        <span className="text-purple-300">P{p.period}</span>
                        <span className="text-gray-500">•</span>
                        <span>{p.code}</span>
                      </div>
                      <div className="text-[10px] text-gray-400 truncate max-w-[170px]" title={p.name}>
                        {p.name}
                      </div>
                    </div>
                  </div>
                  <span className="text-[10px] text-gray-400 font-mono flex-shrink-0">
                    {p.time.split('-')[0].trim()}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Step 3: Target Percentage & Action */}
        <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-[#1c202e]">
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">Target Attendance:</span>
            <div className="flex items-center gap-1.5">
              {[75.0, 80.0, 85.0].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTargetAttendance(t)}
                  className={`px-2.5 py-1 rounded text-xs font-mono font-medium transition-colors ${
                    targetAttendance === t
                      ? 'bg-purple-600 text-white'
                      : 'bg-[#181c2b] text-gray-400 hover:text-white'
                  }`}
                >
                  {t}%
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={runSimulation}
            disabled={loading || selectedPeriods.length === 0}
            className="inline-flex items-center justify-center gap-2 px-5 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs font-semibold shadow-md shadow-purple-600/20 hover:from-purple-500 hover:to-indigo-500 transition-all disabled:opacity-50"
          >
            <FiZap size={13} />
            <span>{loading ? 'Evaluating...' : `Calculate Impact (${selectedPeriods.length} selected)`}</span>
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
            <FiAlertCircle size={14} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* SIMULATION RESULTS VIEW */}
      {simResult && (
        <div className="space-y-5 animate-fadeIn">
          {/* Top Overall Impact Banner */}
          <div className="p-5 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#1c202e]">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white">Projected Day-Bunk Impact</h3>
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-medium border ${
                  simResult.is_safe_day_bunk
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                }`}>
                  {simResult.is_safe_day_bunk ? 'SAFE DAY BUNK' : 'WARNING: THRESHOLD BREACH'}
                </span>
              </div>
              <span className="text-xs text-gray-400 font-mono">
                {simResult.total_classes_missed} total classes missed on {simResult.day}
              </span>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="p-3.5 rounded-lg bg-[#171b28] border border-[#24293c]">
                <div className="text-[10px] text-gray-400 uppercase font-semibold">Current Overall Attendance</div>
                <div className="text-2xl font-extrabold text-white mt-1">
                  {simResult.overall.original.percentage.toFixed(2)}%
                </div>
                <div className="text-[11px] text-gray-400 mt-0.5">
                  {simResult.overall.original.attended} / {simResult.overall.original.conducted} classes
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-[#171b28] border border-[#24293c]">
                <div className="text-[10px] text-gray-400 uppercase font-semibold">Projected Overall Attendance</div>
                <div className="text-2xl font-extrabold text-purple-300 mt-1">
                  {simResult.overall.simulated.percentage.toFixed(2)}%
                </div>
                <div className="text-[11px] text-rose-400 font-mono mt-0.5 flex items-center gap-1 font-semibold">
                  <FiTrendingDown size={11} />
                  <span>{simResult.overall.simulated.percentage_change.toFixed(2)}%</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-[#171b28] border border-[#24293c]">
                <div className="text-[10px] text-gray-400 uppercase font-semibold">Overall Safe Bunks</div>
                <div className="text-2xl font-extrabold text-white mt-1">
                  {simResult.overall.simulated.safe_bunks} Classes
                </div>
                <div className="text-[11px] text-purple-300 mt-0.5 font-mono">
                  {simResult.overall.simulated.safe_bunk_change} from baseline
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-[#171b28] border border-[#24293c]">
                <div className="text-[10px] text-gray-400 uppercase font-semibold">Affected Subjects</div>
                <div className="text-2xl font-extrabold text-white mt-1">
                  {simResult.affected_subjects_count} Courses
                </div>
                <div className="text-[11px] text-gray-400 mt-0.5">
                  Scheduled in selected periods
                </div>
              </div>
            </div>
          </div>

          {/* Subject-by-Subject Impact Table */}
          <div className="p-5 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-3">
            <h4 className="text-xs font-semibold text-white uppercase tracking-wider">
              Subject-Level Breakdown &amp; Regulatory Shifts
            </h4>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[650px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#232738] text-gray-400 text-[10px] uppercase font-semibold">
                    <th className="py-2.5 px-3">Course</th>
                    <th className="py-2.5 px-3 text-center">Missed Today</th>
                    <th className="py-2.5 px-3 text-center">Current</th>
                    <th className="py-2.5 px-3 text-center">Projected</th>
                    <th className="py-2.5 px-3 text-center">Safe Bunks Shift</th>
                    <th className="py-2.5 px-3 text-center">Projected Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1c202e]">
                  {simResult.affected_subjects.map((sub) => {
                    const isWarning = sub.warning_flags.falls_below_75 || sub.warning_flags.in_condonation_zone;
                    const isCritical = sub.warning_flags.falls_below_65 || sub.warning_flags.in_redo_zone;

                    return (
                      <tr key={sub.code} className="hover:bg-[#181c2b]/50 transition-colors">
                        <td className="py-3 px-3">
                          <div className="font-mono font-bold text-white text-xs">{sub.code}</div>
                          <div className="text-[11px] text-gray-400 truncate max-w-[200px]" title={sub.name}>
                            {sub.name}
                          </div>
                        </td>

                        <td className="py-3 px-3 text-center font-mono font-bold text-rose-400">
                          +{sub.missed_classes_today} class
                        </td>

                        <td className="py-3 px-3 text-center">
                          <div className="font-mono font-bold text-gray-200">
                            {sub.original.percentage.toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-gray-500 font-mono">
                            {sub.original.attended}/{sub.original.conducted}
                          </div>
                        </td>

                        <td className="py-3 px-3 text-center">
                          <div className={`font-mono font-extrabold ${
                            isCritical ? 'text-rose-400' : isWarning ? 'text-amber-400' : 'text-purple-300'
                          }`}>
                            {sub.simulated.percentage.toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-rose-400 font-mono">
                            {sub.simulated.percentage_change.toFixed(1)}%
                          </div>
                        </td>

                        <td className="py-3 px-3 text-center">
                          <div className="font-mono font-bold text-white">
                            {sub.simulated.safe_bunks} bunks
                          </div>
                          <div className="text-[10px] text-rose-400 font-mono">
                            {sub.simulated.safe_bunk_change} change
                          </div>
                        </td>

                        <td className="py-3 px-3 text-center">
                          {isCritical ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 border border-rose-500/25 text-rose-300">
                              <FiAlertCircle size={10} /> CRITICAL
                            </span>
                          ) : isWarning ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 border border-amber-500/25 text-amber-300">
                              <FiAlertTriangle size={10} /> CONDONATION
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 border border-emerald-500/25 text-emerald-300">
                              <FiCheckCircle size={10} /> SAFE
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Calculation Transparency Notice */}
            <div className="p-3 rounded-lg bg-[#0f111a] border border-[#1e2333] text-[11px] font-mono text-gray-400 flex flex-wrap items-center justify-between gap-2 mt-2">
              <div>
                <span className="text-purple-400 font-semibold">Formula: </span>
                <span>Projected Attendance = (Attended / (Conducted + Missed)) × 100</span>
              </div>
              <span className="text-[10px] text-gray-500">Zero database writes • 100% In-memory</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DayBunkSimulator;
