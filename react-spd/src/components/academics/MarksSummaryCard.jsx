import React from 'react';
import { 
  FiFileText, 
  FiClock, 
  FiCheckCircle, 
  FiLayers, 
  FiInfo,
  FiAward
} from 'react-icons/fi';

const MarksSummaryCard = ({ caData, resultsData }) => {
  if (!caData) return null;

  const totalCourses = caData.total_courses ?? 0;
  const enteredEvaluations = caData.entered_evaluations ?? 0;
  const pendingEvaluations = caData.pending_evaluations ?? 0;
  const totalEvaluations = enteredEvaluations + pendingEvaluations;
  const completionPct = totalEvaluations > 0 ? Math.round((enteredEvaluations / totalEvaluations) * 100) : 0;

  const totalCredits = resultsData?.total_credits ?? 0;
  const currentCgpa = resultsData?.calculated_cgpa ?? resultsData?.stored_cgpa ?? '—';

  return (
    <div className="space-y-4">
      {/* Top Academic Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        
        {/* Metric 1: Verified CGPA */}
        <div className="p-4 rounded-xl bg-[#131620] border border-[#232738] shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-purple-400">Current CGPA</span>
            <span className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400">
              <FiAward size={14} />
            </span>
          </div>
          <div className="my-2">
            <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {currentCgpa}
            </div>
          </div>
          <div className="text-[11px] text-gray-400 flex items-center justify-between pt-2 border-t border-[#1c202e]">
            <span>{totalCredits} Earned Credits</span>
            <span className="text-emerald-400 font-mono text-[10px]">Verified</span>
          </div>
        </div>

        {/* Metric 2: Registered Subjects */}
        <div className="p-4 rounded-xl bg-[#131620] border border-[#232738] shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-400">Semester Subjects</span>
            <span className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
              <FiLayers size={14} />
            </span>
          </div>
          <div className="my-2">
            <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {totalCourses}
            </div>
          </div>
          <div className="text-[11px] text-gray-400 flex items-center justify-between pt-2 border-t border-[#1c202e]">
            <span>Theory & Labs</span>
            <span className="text-blue-400 font-mono text-[10px]">StudZone 1</span>
          </div>
        </div>

        {/* Metric 3: Published Evaluations */}
        <div className="p-4 rounded-xl bg-[#131620] border border-[#232738] shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">Evaluations Recorded</span>
            <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
              <FiCheckCircle size={14} />
            </span>
          </div>
          <div className="my-2">
            <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {enteredEvaluations}
            </div>
          </div>
          <div className="text-[11px] text-gray-400 flex items-center justify-between pt-2 border-t border-[#1c202e]">
            <span>Tests & Assignments</span>
            <span className="text-emerald-400 font-mono text-[10px]">{completionPct}% Entered</span>
          </div>
        </div>

        {/* Metric 4: Pending Evaluations */}
        <div className="p-4 rounded-xl bg-[#131620] border border-[#232738] shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">Pending Marks</span>
            <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400">
              <FiClock size={14} />
            </span>
          </div>
          <div className="my-2">
            <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {pendingEvaluations}
            </div>
          </div>
          <div className="text-[11px] text-gray-400 flex items-center justify-between pt-2 border-t border-[#1c202e]">
            <span>Marked as (*)</span>
            <span className="text-amber-400 font-mono text-[10px]">Awaiting Entry</span>
          </div>
        </div>

      </div>

      {/* Institutional Context Banner */}
      <div className="p-3.5 rounded-xl bg-[#141824] border border-[#23283c] flex items-start gap-3">
        <FiInfo className="text-purple-400 flex-shrink-0 mt-0.5" size={16} />
        <div className="text-xs text-gray-300 space-y-1">
          <span className="font-semibold text-white">PSG College of Technology Assessment Regulations: </span>
          <span>
            Theory subject internals contribute 40 marks (40% weightage) towards final grades, practical laboratories contribute 60 marks, 
            and project/ethics subjects are 100% continuous assessment. Under autonomous regulations, theory subjects follow 
            <strong className="text-purple-300"> Relative Grading</strong> based on class cohort statistical parameters.
          </span>
        </div>
      </div>
    </div>
  );
};

export default MarksSummaryCard;
