import React, { useState, useEffect, useRef } from 'react';
import { 
  FiSliders, 
  FiRotateCcw, 
  FiPlus, 
  FiMinus, 
  FiTrendingUp, 
  FiTrendingDown,
  FiCheckCircle,
  FiAlertTriangle,
  FiAlertCircle,
  FiActivity
} from 'react-icons/fi';

const AttendanceSimulator = ({ 
  subjects = [], 
  selectedSubjectCode, 
  onSubjectChange, 
  target = 75,
  authToken 
}) => {
  const activeSubject = subjects.find(s => s.code === selectedSubjectCode) || subjects[0] || null;
  const [attendedAdd, setAttendedAdd] = useState(0);
  const [bunkedAdd, setBunkedAdd] = useState(0);
  const [simulationResult, setSimulationResult] = useState(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState('');
  const debounceTimer = useRef(null);

  // Reset counters when selected subject changes
  useEffect(() => {
    setAttendedAdd(0);
    setBunkedAdd(0);
  }, [selectedSubjectCode]);

  // Execute simulation API call (POST /api/attendance/simulate)
  const runSimulation = async (subjCode, addAtt, addBunk, tgt) => {
    if (!subjCode) return;
    
    // Provide instant client-side preview while network call runs
    const origSubj = subjects.find(s => s.code === subjCode);
    const origAtt = origSubj ? origSubj.attended : 0;
    const origCond = origSubj ? origSubj.conducted : 0;
    const newAtt = origAtt + addAtt;
    const newCond = origCond + addAtt + addBunk;
    const newPct = newCond > 0 ? (newAtt / newCond) * 100 : 0;
    const origPct = origCond > 0 ? (origAtt / origCond) * 100 : 0;

    // Instant optimistic baseline
    setSimulationResult({
      subject_code: subjCode,
      subject_name: origSubj?.name || subjCode,
      target: tgt,
      original_attendance: {
        attended: origAtt,
        conducted: origCond,
        percentage: origPct,
        status: origPct >= tgt ? 'SAFE' : origPct >= 65 ? 'WARNING' : 'CRITICAL',
        safe_bunks: origSubj?.safe_bunks ?? 0,
        required_classes: origSubj?.required_classes ?? 0
      },
      simulated_attended: newAtt,
      simulated_conducted: newCond,
      simulated_percentage: newPct,
      simulated_status: newPct >= tgt ? 'SAFE' : newPct >= 65 ? 'WARNING' : 'CRITICAL',
      simulated_safe_bunks: Math.max(0, Math.floor((newAtt - (tgt / 100) * newCond) / (tgt / 100))),
      simulated_required_classes: Math.max(0, Math.ceil(((tgt / 100) * newCond - newAtt) / (1 - tgt / 100))),
      simulated: {
        additional_attended: addAtt,
        additional_bunked: addBunk,
        percentage_change: Number((newPct - origPct).toFixed(2))
      }
    });

    try {
      setSimLoading(true);
      setSimError('');

      const headers = { 'Content-Type': 'application/json' };
      let effectiveToken = authToken;
      if (!effectiveToken && typeof window !== 'undefined') {
        try {
          const raw = localStorage.getItem('student_sync_user');
          if (raw) effectiveToken = JSON.parse(raw).auth_token;
        } catch (e) {}
      }

      if (effectiveToken) {
        headers['Authorization'] = `Bearer ${effectiveToken}`;
      }

      const response = await fetch('/api/attendance/simulate', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          subject_code: subjCode,
          additional_attended: addAtt,
          additional_bunked: addBunk,
          target: tgt
        })
      });

      if (response.ok) {
        const data = await response.json();
        setSimulationResult(data);
      } else {
        const errJson = await response.json().catch(() => ({}));
        if (response.status === 401) {
          setSimError('Session expired. Please log in again.');
        } else if (response.status === 403) {
          setSimError('Access forbidden.');
        } else {
          setSimError(errJson.error || 'Simulation calculation error.');
        }
      }
    } catch (err) {
      console.warn('Network simulation fallback to in-memory calculation:', err);
    } finally {
      setSimLoading(false);
    }
  };

  // Debounced API trigger on counter changes
  useEffect(() => {
    if (!activeSubject) return;

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    debounceTimer.current = setTimeout(() => {
      runSimulation(activeSubject.code, attendedAdd, bunkedAdd, target);
    }, 150);

    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [activeSubject?.code, attendedAdd, bunkedAdd, target]);

  const handleReset = () => {
    setAttendedAdd(0);
    setBunkedAdd(0);
  };

  if (!activeSubject) return null;

  const origPct = simulationResult?.original_attendance?.percentage ?? activeSubject.percentage;
  const simPct = simulationResult?.simulated_percentage ?? origPct;
  const pctDiff = Number((simPct - origPct).toFixed(2));
  const simStatus = simulationResult?.simulated_status ?? (simPct >= target ? 'SAFE' : simPct >= 65 ? 'WARNING' : 'CRITICAL');
  const simSafeBunks = simulationResult?.simulated_safe_bunks ?? 0;
  const simReqClasses = simulationResult?.simulated_required_classes ?? 0;

  const getStatusColor = (status) => {
    switch (status) {
      case 'SAFE':
        return {
          badge: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
          dot: 'bg-emerald-400',
          text: 'text-emerald-400'
        };
      case 'WARNING':
        return {
          badge: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
          dot: 'bg-amber-400',
          text: 'text-amber-400'
        };
      case 'CRITICAL':
      default:
        return {
          badge: 'bg-rose-500/10 border-rose-500/20 text-rose-400',
          dot: 'bg-rose-400',
          text: 'text-rose-400'
        };
    }
  };

  const statusStyle = getStatusColor(simStatus);

  return (
    <div id="attendance-simulator-section" className="bg-[#131620] border border-[#232738] rounded-xl p-5 sm:p-7 shadow-sm space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#1f2434]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <FiSliders className="text-sm" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-semibold text-white">Attendance Simulator</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1c2132] text-purple-300 border border-[#2b334d]">
                In-Memory
              </span>
            </div>
            <p className="text-xs text-gray-400">
              Hypothetical projection model • Zero writes to MongoDB or baselines
            </p>
          </div>
        </div>

        <button
          onClick={handleReset}
          disabled={attendedAdd === 0 && bunkedAdd === 0}
          className={`self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
            attendedAdd > 0 || bunkedAdd > 0
              ? 'bg-[#1c2133] hover:bg-[#252c42] text-purple-300 border-[#2f3750] shadow-sm'
              : 'bg-[#151824] text-gray-600 border-[#1f2436] cursor-not-allowed'
          }`}
        >
          <FiRotateCcw className="text-xs" />
          <span>Reset Simulation</span>
        </button>
      </div>

      {simError && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <FiAlertCircle className="flex-shrink-0" />
          <span>{simError}</span>
        </div>
      )}

      {/* Select Subject */}
      <div className="space-y-1.5">
        <label htmlFor="simulator-subject-select" className="block text-xs font-medium text-gray-300">
          Target Subject:
        </label>
        <select
          id="simulator-subject-select"
          value={activeSubject.code}
          onChange={(e) => onSubjectChange && onSubjectChange(e.target.value)}
          className="w-full px-3.5 py-2.5 bg-[#0e111a] border border-[#282e42] rounded-lg text-sm text-white focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
        >
          {subjects.map((s) => (
            <option key={s.code} value={s.code} className="bg-[#131620] text-white">
              {s.name} ({s.code}) — Current: {s.percentage.toFixed(1)}%
            </option>
          ))}
        </select>
      </div>

      {/* Interactive Dual Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Classes to Attend Counter */}
        <div className="p-4 rounded-xl bg-[#181c2b] border border-[#23283a] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wide">
              Classes to Attend (+)
            </span>
            <span className="text-[10px] text-gray-400 font-mono">Present</span>
          </div>

          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => setAttendedAdd(prev => Math.max(0, prev - 1))}
              disabled={attendedAdd === 0}
              className={`w-11 h-11 rounded-lg flex items-center justify-center text-base transition-colors ${
                attendedAdd > 0
                  ? 'bg-[#22283a] text-white hover:bg-emerald-600 border border-[#2d354d]'
                  : 'bg-[#151824] text-gray-600 border border-[#1f2436] cursor-not-allowed'
              }`}
              aria-label="Decrease attended classes"
            >
              <FiMinus />
            </button>

            <div className="flex-1 text-center">
              <span className="text-3xl font-extrabold font-mono text-white">
                {attendedAdd}
              </span>
              <div className="text-[10px] text-gray-400">added sessions</div>
            </div>

            <button
              onClick={() => setAttendedAdd(prev => prev + 1)}
              className="w-11 h-11 rounded-lg bg-[#22283a] text-white hover:bg-emerald-600 border border-[#2d354d] flex items-center justify-center text-base transition-colors"
              aria-label="Increase attended classes"
            >
              <FiPlus />
            </button>
          </div>
        </div>

        {/* Classes to Bunk Counter */}
        <div className="p-4 rounded-xl bg-[#181c2b] border border-[#23283a] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-400 uppercase tracking-wide">
              Classes to Bunk (-)
            </span>
            <span className="text-[10px] text-gray-400 font-mono">Absent</span>
          </div>

          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => setBunkedAdd(prev => Math.max(0, prev - 1))}
              disabled={bunkedAdd === 0}
              className={`w-11 h-11 rounded-lg flex items-center justify-center text-base transition-colors ${
                bunkedAdd > 0
                  ? 'bg-[#22283a] text-white hover:bg-rose-600 border border-[#2d354d]'
                  : 'bg-[#151824] text-gray-600 border border-[#1f2436] cursor-not-allowed'
              }`}
              aria-label="Decrease bunked classes"
            >
              <FiMinus />
            </button>

            <div className="flex-1 text-center">
              <span className="text-3xl font-extrabold font-mono text-white">
                {bunkedAdd}
              </span>
              <div className="text-[10px] text-gray-400">missed sessions</div>
            </div>

            <button
              onClick={() => setBunkedAdd(prev => prev + 1)}
              className="w-11 h-11 rounded-lg bg-[#22283a] text-white hover:bg-rose-600 border border-[#2d354d] flex items-center justify-center text-base transition-colors"
              aria-label="Increase bunked classes"
            >
              <FiPlus />
            </button>
          </div>
        </div>
      </div>

      {/* Projection Comparison Card */}
      <div className="p-5 sm:p-6 rounded-xl bg-[#171b29] border border-[#24293c] space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#212638]">
          <span className="text-xs font-bold text-gray-300 uppercase tracking-wider">
            Simulated Outcome Projection
          </span>
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusStyle.badge}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${statusStyle.dot}`} />
            Projected: {simStatus}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-center">
          {/* Current */}
          <div className="p-3 rounded-lg bg-[#121520] border border-[#1e2334] text-center">
            <div className="text-[10px] uppercase tracking-wide text-gray-400">Current Attendance</div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {origPct.toFixed(2)}%
            </div>
            <div className="text-[10px] text-gray-500 font-mono mt-0.5">
              {activeSubject.attended} / {activeSubject.conducted}
            </div>
          </div>

          {/* Change Indicator */}
          <div className="text-center space-y-1">
            <div className="text-[10px] uppercase tracking-wide text-gray-400">Difference</div>
            <div className={`text-xl font-extrabold font-mono inline-flex items-center gap-1 ${
              pctDiff > 0 ? 'text-emerald-400' : pctDiff < 0 ? 'text-rose-400' : 'text-gray-400'
            }`}>
              {pctDiff > 0 ? (
                <>
                  <FiTrendingUp className="text-sm" />
                  <span>+{pctDiff.toFixed(2)}%</span>
                </>
              ) : pctDiff < 0 ? (
                <>
                  <FiTrendingDown className="text-sm" />
                  <span>{pctDiff.toFixed(2)}%</span>
                </>
              ) : (
                <span>0.00%</span>
              )}
            </div>
            <div className="text-[10px] text-gray-500">
              {attendedAdd} attended, {bunkedAdd} bunked
            </div>
          </div>

          {/* Projected */}
          <div className="p-3 rounded-lg bg-[#121520] border border-[#1e2334] text-center">
            <div className="text-[10px] uppercase tracking-wide text-gray-400">Projected Attendance</div>
            <div className={`text-2xl font-bold font-mono mt-1 ${statusStyle.text}`}>
              {simPct.toFixed(2)}%
            </div>
            <div className="text-[10px] text-gray-500 font-mono mt-0.5">
              {simulationResult?.simulated_attended ?? (activeSubject.attended + attendedAdd)} / {simulationResult?.simulated_conducted ?? (activeSubject.conducted + attendedAdd + bunkedAdd)}
            </div>
          </div>
        </div>

        {/* Projected Safe Bunks / Recovery Banner */}
        <div className="pt-2 text-xs">
          {simPct >= target ? (
            <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/20 text-emerald-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <FiCheckCircle className="text-emerald-400 flex-shrink-0" />
                <span>Projected Safe Bunks after this simulation:</span>
              </span>
              <span className="font-bold font-mono text-emerald-200">
                {simSafeBunks} {simSafeBunks === 1 ? 'class' : 'classes'}
              </span>
            </div>
          ) : (
            <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-500/20 text-rose-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <FiAlertTriangle className="text-rose-400 flex-shrink-0" />
                <span>Consecutive classes needed to reach {target}%:</span>
              </span>
              <span className="font-bold font-mono text-rose-200">
                {simReqClasses} {simReqClasses === 1 ? 'class' : 'classes'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AttendanceSimulator;
