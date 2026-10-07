import React from 'react';
import { 
  FiCalendar, 
  FiClock, 
  FiAlertCircle, 
  FiCheckCircle, 
  FiFileText,
  FiExternalLink,
  FiSun,
  FiMoon
} from 'react-icons/fi';

const ExamScheduleList = ({ examsData }) => {
  if (!examsData || !examsData.exams || examsData.exams.length === 0) {
    return (
      <div className="py-16 text-center text-xs text-gray-500 rounded-xl bg-[#131620] border border-[#232738]">
        No examination schedule published on StudZone 2 records yet.
      </div>
    );
  }

  const { exams, total_exams, pending_count, scheduled_count } = examsData;

  return (
    <div className="space-y-5">
      {/* Overview Status Banner */}
      <div className="p-6 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#1c202e]">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-white">End-Semester Examination Schedule</h2>
              <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-300 font-mono">
                Source: StudZone 2
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Official timetable records published by the Controller of Examinations (CoE)
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono font-medium border ${
              pending_count > 0 
                ? 'bg-amber-500/10 text-amber-300 border-amber-500/20' 
                : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
            }`}>
              <FiCalendar size={13} />
              <span>{pending_count > 0 ? `${pending_count} Dates Awaiting CoE Publication` : 'Fully Scheduled'}</span>
            </span>
          </div>
        </div>

        {/* Quick Numbers */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold">Total Examination Courses</div>
            <div className="text-2xl font-extrabold text-white mt-1">{total_exams}</div>
            <div className="text-[11px] text-gray-400 mt-0.5">Autonomous Semester Session</div>
          </div>

          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold">Scheduled Exam Dates</div>
            <div className="text-2xl font-extrabold text-emerald-400 mt-1">{scheduled_count}</div>
            <div className="text-[11px] text-gray-400 mt-0.5">Confirmed exam dates</div>
          </div>

          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold">Dates Pending Release</div>
            <div className="text-2xl font-extrabold text-amber-400 mt-1">{pending_count}</div>
            <div className="text-[11px] text-gray-400 mt-0.5">Subject to official CoE circular</div>
          </div>
        </div>

        {/* Institutional Safety Disclaimer */}
        <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/15 text-xs text-blue-300/80 leading-relaxed">
          <span className="font-semibold text-blue-200">PSG Tech Examination Policy: </span>
          All dates and timings displayed are fetched directly from Controller of Examinations records. 
          When marked as <span className="font-mono font-bold text-amber-300">Schedule Pending</span>, official test dates will be populated as soon as the autonomous examination circular is released.
        </div>
      </div>

      {/* Courses Examination Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {exams.map((ex, i) => {
          const isPending = ex.is_pending || ex.status === 'PENDING';
          const isFN = ex.session === 'FN';
          const isAN = ex.session === 'AN';

          return (
            <div 
              key={i}
              className="p-5 rounded-xl bg-[#131620] border border-[#232738] hover:border-[#32394e] transition-all space-y-4 flex flex-col justify-between"
            >
              <div className="space-y-3">
                {/* Header: Code & Session */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-purple-500/15 border border-purple-500/25 text-purple-300">
                      {ex.course_code}
                    </span>
                    {ex.sem && (
                      <span className="ml-2 text-[10px] font-mono text-gray-500">
                        Sem {ex.sem}
                      </span>
                    )}
                    <h3 className="text-sm font-semibold text-white mt-2 line-clamp-2 leading-relaxed">
                      {ex.course_title}
                    </h3>
                  </div>

                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold flex-shrink-0 ${
                    isPending
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  }`}>
                    {isPending ? 'SCHEDULE PENDING' : 'CONFIRMED'}
                  </span>
                </div>

                {/* Date & Timing Details */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#1c202e] text-xs">
                  <div className="p-2.5 rounded-lg bg-[#171b28] border border-[#24293c]">
                    <div className="text-[10px] text-gray-500 font-semibold uppercase flex items-center gap-1">
                      <FiCalendar size={10} />
                      <span>Exam Date</span>
                    </div>
                    <div className={`mt-1 font-mono font-bold text-xs ${
                      isPending ? 'text-amber-300' : 'text-white'
                    }`}>
                      {ex.exam_date}
                    </div>
                  </div>

                  <div className="p-2.5 rounded-lg bg-[#171b28] border border-[#24293c]">
                    <div className="text-[10px] text-gray-500 font-semibold uppercase flex items-center gap-1">
                      <FiClock size={10} />
                      <span>Session &amp; Slot</span>
                    </div>
                    <div className="mt-1 font-mono font-bold text-xs text-white flex items-center gap-1">
                      {isFN && <FiSun size={11} className="text-amber-400" />}
                      {isAN && <FiMoon size={11} className="text-indigo-400" />}
                      <span>{ex.session} • {ex.timing}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Status Note */}
              <div className="text-[11px] text-gray-500 flex items-center justify-between pt-1 font-mono">
                <span>Controller of Examinations</span>
                <span>{isPending ? 'Awaiting slot release' : 'Confirmed'}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ExamScheduleList;
