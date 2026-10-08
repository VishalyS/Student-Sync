import React, { useState } from 'react';
import { 
  FiClock, 
  FiCalendar, 
  FiBookOpen, 
  FiCheckCircle, 
  FiAlertTriangle, 
  FiCoffee,
  FiGrid,
  FiList
} from 'react-icons/fi';

const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

const WeeklyTimetableGrid = ({ weeklySchedule, unifiedCourses = [] }) => {
  // Determine today's day name to auto-select
  const currentDayIndex = new Date().getDay(); // 0 is Sunday, 1 is Monday ... 5 is Friday
  const currentDayName = DAYS_OF_WEEK[currentDayIndex - 1] || 'Monday';

  const [selectedDay, setSelectedDay] = useState(currentDayName);
  const [viewMode, setViewMode] = useState('day'); // 'day' or 'full'

  if (!weeklySchedule || !weeklySchedule.days || weeklySchedule.days.length === 0) {
    return (
      <div className="py-16 text-center text-xs text-gray-500 rounded-xl bg-[#131620] border border-[#232738]">
        No weekly class schedule available from StudZone 1 records.
      </div>
    );
  }

  // Create attendance lookup for subject quick-metrics
  const attLookup = {};
  if (Array.isArray(unifiedCourses)) {
    unifiedCourses.forEach(c => {
      if (c && c.code) {
        attLookup[c.code.toUpperCase()] = c.attendance;
      }
    });
  }

  const activeDaySchedule = weeklySchedule.days.find(
    d => d.day.toLowerCase() === selectedDay.toLowerCase()
  ) || weeklySchedule.days[0];

  return (
    <div className="space-y-5">
      {/* View Switcher & Day Navigation Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-[#131620] border border-[#232738]">
        {/* Day Selector Buttons */}
        <div className="flex flex-wrap items-center gap-1.5">
          {DAYS_OF_WEEK.map((dayName) => {
            const isToday = currentDayName.toLowerCase() === dayName.toLowerCase();
            const isSelected = selectedDay.toLowerCase() === dayName.toLowerCase() && viewMode === 'day';
            const dayObj = weeklySchedule.days.find(d => d.day.toLowerCase() === dayName.toLowerCase());
            const scheduledCount = dayObj ? dayObj.scheduled_classes : 0;

            return (
              <button
                key={dayName}
                onClick={() => {
                  setSelectedDay(dayName);
                  setViewMode('day');
                }}
                className={`relative px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
                  isSelected
                    ? 'bg-purple-600 text-white shadow-md shadow-purple-600/25 border border-purple-500'
                    : 'bg-[#181c2b] text-gray-400 hover:text-gray-200 hover:bg-[#22273a] border border-[#24293c]'
                }`}
              >
                <span>{dayName}</span>
                {isToday && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" title="Today" />
                )}
                <span className={`text-[10px] font-mono px-1 rounded ${
                  isSelected ? 'bg-purple-800 text-purple-200' : 'bg-[#121520] text-gray-400'
                }`}>
                  {scheduledCount}h
                </span>
              </button>
            );
          })}
        </div>

        {/* View Toggle (Single Day vs Full Week Grid) */}
        <div className="flex items-center gap-1 self-start sm:self-auto bg-[#181c2b] p-1 rounded-lg border border-[#24293c]">
          <button
            onClick={() => setViewMode('day')}
            className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1.5 transition-colors ${
              viewMode === 'day' ? 'bg-[#22273a] text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <FiList size={13} />
            <span>Day View</span>
          </button>
          <button
            onClick={() => setViewMode('full')}
            className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1.5 transition-colors ${
              viewMode === 'full' ? 'bg-[#22273a] text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <FiGrid size={13} />
            <span>Full Week Grid</span>
          </button>
        </div>
      </div>

      {/* SINGLE DAY VIEW */}
      {viewMode === 'day' && activeDaySchedule && (
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span>{activeDaySchedule.day}'s Timetable</span>
              {currentDayName.toLowerCase() === activeDaySchedule.day.toLowerCase() && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Active Day
                </span>
              )}
            </h3>
            <span className="text-xs text-gray-400 font-mono">
              {activeDaySchedule.scheduled_classes} {activeDaySchedule.scheduled_classes === 1 ? 'class' : 'classes'} • {activeDaySchedule.free_periods === 0 ? 'No free slots' : `${activeDaySchedule.free_periods} free ${activeDaySchedule.free_periods === 1 ? 'slot' : 'slots'}`}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {activeDaySchedule.periods.map((p) => {
              const isFree = p.is_free || p.code === 'FREE';
              const attInfo = !isFree ? attLookup[p.code.toUpperCase()] : null;

              return (
                <div
                  key={p.period}
                  className={`p-4 rounded-xl border transition-all flex flex-col justify-between ${
                    isFree
                      ? 'bg-[#10131d]/60 border-[#1d2232] text-gray-500'
                      : 'bg-[#131620] border-[#232738] hover:border-[#32394e]'
                  }`}
                >
                  <div className="space-y-2">
                    {/* Period Number & Timing Badge */}
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-[#181c2b] text-purple-300 border border-[#262c3e]">
                        Period {p.period}
                      </span>
                      <span className="font-mono text-[11px] text-gray-400 flex items-center gap-1">
                        <FiClock size={11} className="text-gray-400" />
                        <span>{p.time}</span>
                      </span>
                    </div>

                    {/* Course Code & Name */}
                    {isFree ? (
                      <div className="py-4 text-center space-y-1">
                        <FiCoffee className="mx-auto text-gray-600 text-lg" />
                        <div className="text-xs font-medium text-gray-400">Free Period</div>
                        <div className="text-[11px] text-gray-400 font-mono">No lecture scheduled</div>
                      </div>
                    ) : (
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-white bg-purple-500/15 border border-purple-500/25 px-2 py-0.5 rounded">
                            {p.code}
                          </span>
                          {p.section && (
                            <span className="text-[10px] font-mono text-gray-400">
                              {p.section}
                            </span>
                          )}
                        </div>
                        <h4 className="text-xs font-semibold text-gray-200 mt-2 line-clamp-2 leading-relaxed">
                          {p.name}
                        </h4>
                      </div>
                    )}
                  </div>

                  {/* Attendance Quick Metric (if not free) */}
                  {!isFree && attInfo && (
                    <div className="pt-3 mt-3 border-t border-[#1c202e] flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <span className="text-gray-400">Att:</span>
                        <span className={`font-mono font-bold ${
                          attInfo.percentage >= 75.0 ? 'text-emerald-400' : 'text-amber-400'
                        }`}>
                          {attInfo.percentage.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-gray-400">Safe:</span>
                        <span className="font-mono font-bold text-purple-300">
                          {attInfo.safe_bunks} bunks
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* FULL WEEK GRID VIEW */}
      {viewMode === 'full' && (
        <div className="p-4 rounded-xl bg-[#131620] border border-[#232738] overflow-x-auto">
          <table className="w-full min-w-[700px] text-xs text-left border-collapse">
            <thead>
              <tr className="border-b border-[#232738] text-gray-400">
                <th className="py-2.5 px-3 font-semibold uppercase tracking-wider text-[10px] w-24">Day</th>
                {weeklySchedule.timing_slots.map(t => (
                  <th key={t.period} className="py-2.5 px-3 font-semibold text-[11px] text-center">
                    <div>P{t.period}</div>
                    <div className="text-[10px] text-gray-400 font-mono font-normal">{t.time}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1c202e]">
              {weeklySchedule.days.map((d) => {
                const isToday = currentDayName.toLowerCase() === d.day.toLowerCase();
                return (
                  <tr key={d.day} className={`hover:bg-[#181c2b]/50 transition-colors ${
                    isToday ? 'bg-purple-950/20' : ''
                  }`}>
                    <td className="py-3 px-3 font-bold text-white whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <span>{d.day}</span>
                        {isToday && (
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" title="Today" />
                        )}
                      </div>
                      <div className="text-[10px] font-mono text-gray-400 font-normal">
                        {d.scheduled_classes} classes
                      </div>
                    </td>
                    {d.periods.map((p) => {
                      const isFree = p.is_free || p.code === 'FREE';
                      return (
                        <td key={p.period} className="py-2 px-2 text-center align-top">
                          {isFree ? (
                            <div className="p-2 rounded bg-[#0f111a] border border-[#1b1f2e] text-gray-600 font-mono text-[10px]">
                              —
                            </div>
                          ) : (
                            <div className="p-2 rounded bg-[#171b28] border border-[#262c3e] space-y-1 hover:border-purple-500/50 transition-colors text-left">
                              <div className="font-mono font-bold text-purple-300 text-[10px]">
                                {p.code}
                              </div>
                              <div className="text-[10px] font-medium text-gray-300 truncate" title={p.name}>
                                {p.name}
                              </div>
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default WeeklyTimetableGrid;
