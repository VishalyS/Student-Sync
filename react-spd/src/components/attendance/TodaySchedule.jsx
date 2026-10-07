import React from 'react';
import { Link } from 'react-router-dom';
import { FiClock, FiCalendar, FiBookOpen } from 'react-icons/fi';

const TodaySchedule = ({ schedule, onSelectSubject }) => {
  const dayName = schedule?.day || 'Today';
  const periods = schedule?.classes || schedule?.periods || [];

  return (
    <div className="bg-[#131620] border border-[#232738] rounded-xl p-5 sm:p-6 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#1f2434]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <FiClock className="text-sm" />
          </div>
          <div>
            <h2 className="text-sm sm:text-base font-semibold text-white">Today's Class Schedule</h2>
            <p className="text-[11px] text-gray-400 font-mono">
              {dayName} • PSG College of Technology Timetable
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/schedule"
            className="text-xs text-purple-400 hover:text-purple-300 font-medium inline-flex items-center gap-1 transition-colors"
          >
            <span>Open Full Weekly Timetable &amp; Day Planner →</span>
          </Link>
          <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded bg-[#181c2b] border border-[#262c3e] text-purple-300 font-mono">
            {periods.length} {periods.length === 1 ? 'Period' : 'Periods'}
          </span>
        </div>
      </div>

      {/* Schedule Items */}
      {periods.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {periods.map((slot, idx) => {
            const subjectCode = slot.code || slot.subject_code || '';
            const subjectName = slot.name || slot.subject_name || subjectCode;
            const periodLabel = typeof slot.period === 'number' ? `Period ${slot.period}` : (slot.period || `Period ${idx + 1}`);

            return (
              <div 
                key={idx}
                className="p-3.5 rounded-lg bg-[#181c2b] border border-[#23283a] hover:border-purple-500/40 transition-all flex flex-col justify-between space-y-2 group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-400">
                    {periodLabel}
                  </span>
                  <span className="text-[11px] text-gray-400 font-mono flex items-center gap-1">
                    <FiClock size={10} />
                    {slot.time || 'Class Hour'}
                  </span>
                </div>

                <div>
                  <div className="text-xs font-bold text-white group-hover:text-purple-300 transition-colors line-clamp-1">
                    {subjectName}
                  </div>
                  <div className="text-[10px] text-gray-400 font-mono mt-0.5">
                    {subjectCode}
                  </div>
                </div>

                {onSelectSubject && subjectCode && (
                  <button
                    onClick={() => onSelectSubject(subjectCode)}
                    className="w-full text-left text-[10px] text-purple-400 hover:text-purple-300 pt-1 font-medium transition-colors"
                  >
                    View Attendance / Simulate →
                  </button>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-8 text-center space-y-2">
          <FiCalendar className="mx-auto text-3xl text-gray-600" />
          <h4 className="text-xs font-semibold text-gray-300">No classes scheduled today.</h4>
          <p className="text-[11px] text-gray-500 max-w-sm mx-auto">
            Enjoy your day off or review your registered subject attendance below.
          </p>
        </div>
      )}
    </div>
  );
};

export default TodaySchedule;
