import React from 'react';
import { 
  FiMessageSquare, 
  FiClock, 
  FiCheckCircle, 
  FiInfo, 
  FiAlertCircle 
} from 'react-icons/fi';

const FeedbackCycleAlert = ({ feedback }) => {
  if (!feedback) {
    return (
      <div className="bg-[#121520] border border-[#1e2333] rounded-2xl p-6 text-center text-gray-400">
        <FiMessageSquare className="mx-auto text-3xl mb-2 text-gray-500" />
        <p>No feedback survey schedules published from institutional records.</p>
      </div>
    );
  }

  const {
    active_count,
    total_cycles,
    cycles
  } = feedback;

  return (
    <div className="bg-[#121520] border border-[#1e2333] rounded-2xl overflow-hidden shadow-xl">
      {/* Header Banner */}
      <div className="p-6 sm:p-8 border-b border-[#1e2333] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <FiMessageSquare className="text-blue-400" /> Institutional Course Feedback
            </h3>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
              active_count > 0 
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' 
                : 'bg-gray-500/10 border-gray-500/30 text-gray-400'
            }`}>
              {active_count > 0 ? `${active_count} Active Window(s)` : 'Feedback Not Scheduled'}
            </span>
          </div>
          <p className="text-sm text-gray-400">
            Mandatory institutional curriculum, teacher evaluation, and course feedback monitoring.
          </p>
        </div>

        <div className="px-4 py-2 rounded-xl bg-[#161a27] border border-[#23293e] text-xs self-start sm:self-center">
          <span className="text-gray-400 block text-[10px] uppercase font-mono tracking-wider">Evaluation Cycles</span>
          <span className="text-white font-bold font-mono text-sm">
            {total_cycles || 0} Tracked Cycles
          </span>
        </div>
      </div>

      {/* Main List */}
      <div className="p-6 sm:p-8">
        {cycles && cycles.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cycles.map((cycle, idx) => (
              <div 
                key={idx}
                className={`p-5 rounded-xl border flex flex-col justify-between transition-colors ${
                  cycle.is_active 
                    ? 'bg-amber-950/10 border-amber-500/30 hover:border-amber-500/50' 
                    : 'bg-[#151926] border-[#212638] hover:border-[#2d344d]'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold text-gray-200">
                      {cycle.type || 'Course Feedback'}
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium border ${
                      cycle.is_active
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                        : 'bg-gray-500/10 text-gray-400 border-gray-500/30'
                    }`}>
                      {cycle.status || 'Not Scheduled'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed mt-1">
                    {cycle.description || 'Feedback is currently not scheduled for this session.'}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-[#1e2333] flex items-center justify-between text-xs font-mono text-gray-400">
                  <span className="flex items-center gap-1">
                    {cycle.is_active ? (
                      <span className="text-amber-400 flex items-center gap-1 font-semibold">
                        <FiClock className="text-xs" /> Submission Open on StudZone 1
                      </span>
                    ) : (
                      <span className="text-gray-400 flex items-center gap-1">
                        <FiCheckCircle className="text-xs text-gray-400" /> Currently Inactive
                      </span>
                    )}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-gray-400 bg-[#151926] rounded-xl border border-[#212638]">
            No feedback cycles recorded in student portal.
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="bg-[#0e111a] border-t border-[#1e2333] px-6 py-3 flex items-center justify-between text-xs text-gray-400">
        <span className="flex items-center gap-1.5 text-gray-400">
          <FiInfo className="text-blue-400 text-sm flex-shrink-0" /> Student Sync monitors feedback windows. Submission occurs securely within the official PSG Tech portal.
        </span>
        <span className="font-mono text-[11px] text-gray-400">
          Source: StudZone 1
        </span>
      </div>
    </div>
  );
};

export default FeedbackCycleAlert;
