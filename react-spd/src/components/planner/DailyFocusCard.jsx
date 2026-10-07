import React from 'react';
import { 
  FiClock, 
  FiAlertCircle, 
  FiCheckCircle, 
  FiCalendar, 
  FiTrendingUp,
  FiBookOpen,
  FiInfo,
  FiTag
} from 'react-icons/fi';

const DailyFocusCard = ({ 
  todayContext, 
  selectedDay, 
  onSelectDay, 
  loadingDay 
}) => {
  const dayName = selectedDay || todayContext?.day_name || 'Friday';
  const weekdays = todayContext?.available_weekdays || ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  const recommendedFocus = todayContext?.recommended_focus || [];
  const scheduledCount = todayContext?.scheduled_subjects_count || 0;
  const periodsCount = todayContext?.scheduled_periods_count || 0;
  const hasClasses = todayContext?.has_classes_today ?? (scheduledCount > 0);

  const getPriorityBadge = (level) => {
    switch (level) {
      case 'HIGH':
        return (
          <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
            High Priority
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Medium Priority
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Routine Focus
          </span>
        );
    }
  };

  return (
    <div className="bg-[#151922] border border-[#232938] rounded-2xl p-6 mb-8 shadow-sm">
      {/* Header with Title & Day Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-[#232938]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20 uppercase tracking-wider">
              Daily Intelligence
            </span>
            <span className="text-xs text-gray-400">Contextual Schedule Synthesis</span>
          </div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FiCalendar className="text-purple-400" />
            What Should I Study & Focus On Today?
          </h2>
          <p className="text-xs sm:text-sm text-gray-400 mt-0.5">
            Prioritizes today's timetable periods using your current attendance margins, safe bunks, and CA workload.
          </p>
        </div>

        {/* Day Selector Pills */}
        <div className="flex items-center gap-1.5 bg-[#0e1118] p-1.5 rounded-xl border border-[#1f2433] overflow-x-auto scrollbar-none">
          {weekdays.map((day) => {
            const isSelected = day === dayName;
            return (
              <button
                key={day}
                onClick={() => onSelectDay(day)}
                disabled={loadingDay}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                  isSelected
                    ? 'bg-purple-600 text-white shadow-sm font-semibold'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a202c]'
                }`}
              >
                {day}
              </button>
            );
          })}
        </div>
      </div>

      {/* Day Overview Strip */}
      <div className="flex items-center justify-between py-3 px-4 bg-[#0e1118]/60 border border-[#1e2330] rounded-xl my-4 text-xs">
        <div className="flex items-center gap-2 text-gray-300">
          <span className="font-semibold text-white">{dayName}'s Schedule:</span>
          {hasClasses ? (
            <span>{scheduledCount} course{scheduledCount !== 1 ? 's' : ''} ({periodsCount} active period{periodsCount !== 1 ? 's' : ''})</span>
          ) : (
            <span className="text-gray-400">No scheduled classes found</span>
          )}
        </div>
        <div className="text-gray-400 text-[11px] hidden sm:block">
          Scores derived deterministically • Zero grade guesswork
        </div>
      </div>

      {/* Recommended Focus List */}
      {recommendedFocus.length === 0 ? (
        <div className="text-center py-8 text-gray-400 text-sm bg-[#0e1118]/30 rounded-xl border border-[#1e2330]">
          <FiInfo className="mx-auto text-2xl text-gray-500 mb-2" />
          No classes scheduled for {dayName}. Enjoy your study break or review general coursework.
        </div>
      ) : (
        <div className="space-y-4">
          {recommendedFocus.map((item, idx) => {
            const prio = item.priority || {};
            const att = item.attendance || {};
            const sched = item.schedule || {};
            const ca = item.ca_progress || {};
            const ex = item.exam || {};
            const todaySlots = sched.today_slots || [];

            return (
              <div 
                key={item.code} 
                className="bg-[#0e1118] border border-[#232938] rounded-xl p-5 hover:border-[#384259] transition-all relative overflow-hidden"
              >
                {/* Top Row: Code, Name, Priority Badge & Score */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-[#1b202c] border border-[#2d3447] text-gray-400 text-xs font-bold flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                          {item.code}
                        </span>
                        <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                          {item.name}
                        </h3>
                      </div>
                      <span className="text-xs text-gray-500">{item.category || 'Theory'}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    {getPriorityBadge(prio.level)}
                    <span className="text-xs text-gray-400 font-mono bg-[#161a23] px-2 py-1 rounded border border-[#232938]">
                      Score: <span className="font-bold text-white">{prio.score}</span>/100
                    </span>
                  </div>
                </div>

                {/* Middle Row: Periods, Attendance & CA Status */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 py-2.5 px-3 bg-[#131722] rounded-lg border border-[#1f2535] text-xs mb-3">
                  {/* Periods Today */}
                  <div>
                    <span className="text-gray-400 block text-[11px] mb-0.5">Scheduled Periods Today:</span>
                    {todaySlots.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {todaySlots.map((s, sIdx) => (
                          <span key={sIdx} className="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[11px] font-medium border border-purple-500/30">
                            P{s.period} ({s.time})
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-gray-500">Not in timetable today</span>
                    )}
                  </div>

                  {/* Attendance Margin */}
                  <div>
                    <span className="text-gray-400 block text-[11px] mb-0.5">Attendance Margin:</span>
                    <div className="flex items-center gap-1.5 font-medium">
                      <span className={att.percentage >= 75 ? 'text-emerald-400' : 'text-amber-400'}>
                        {att.percentage?.toFixed(2)}%
                      </span>
                      <span className="text-gray-400">({att.attended}/{att.conducted})</span>
                      <span className={`px-1.5 py-0.2 rounded text-[10px] ${
                        att.safe_bunks === 0 
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' 
                          : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      }`}>
                        {att.safe_bunks} safe bunks
                      </span>
                    </div>
                  </div>

                  {/* CA & Exam Status */}
                  <div>
                    <span className="text-gray-400 block text-[11px] mb-0.5">Assessment & Exam:</span>
                    <span className="text-gray-300 font-medium">
                      {ca.pending > 0 ? `${ca.pending} pending CA` : 'CA up to date'} • {ex.exam_date || 'Pending'}
                    </span>
                  </div>
                </div>

                {/* Bottom Row: Transparent Rationale Explanations */}
                <div className="bg-[#0b0e14] rounded-lg p-3 border border-[#1b202e]">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 block mb-1.5 flex items-center gap-1">
                    <FiTrendingUp className="text-purple-400" />
                    Why this course is recommended for {dayName}:
                  </span>
                  <ul className="space-y-1">
                    {(prio.reasons || []).map((reason, rIdx) => (
                      <li key={rIdx} className="text-xs text-gray-300 flex items-start gap-1.5">
                        <span className="text-purple-400 mt-0.5">•</span>
                        <span>{reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default DailyFocusCard;
