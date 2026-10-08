import React, { useState } from 'react';
import { 
  FiFileText, 
  FiCheck, 
  FiClock, 
  FiMinus, 
  FiLayers, 
  FiPercent,
  FiFilter
} from 'react-icons/fi';

const CAComponentBreakdown = ({ courses = [] }) => {
  const [filterCategory, setFilterCategory] = useState('ALL');

  if (!courses || courses.length === 0) {
    return (
      <div className="py-16 text-center text-xs text-gray-500 rounded-xl bg-[#131620] border border-[#232738]">
        No continuous assessment marks found for active semester subjects.
      </div>
    );
  }

  const categories = ['ALL', 'Theory', 'Laboratory', 'Project', 'Mandatory/Audit'];
  const filteredCourses = filterCategory === 'ALL'
    ? courses
    : courses.filter(c => c.category === filterCategory);

  const getCategoryBadge = (category) => {
    switch (category) {
      case 'Laboratory':
        return 'bg-blue-500/10 border-blue-500/20 text-blue-400';
      case 'Project':
        return 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400';
      case 'Mandatory/Audit':
        return 'bg-amber-500/10 border-amber-500/20 text-amber-400';
      case 'Theory':
      default:
        return 'bg-purple-500/10 border-purple-500/20 text-purple-400';
    }
  };

  return (
    <div className="space-y-4">
      {/* Category Filter Pills */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-1">
        <div className="flex items-center gap-2">
          <FiFilter size={14} className="text-gray-400" />
          <span className="text-xs font-medium text-gray-300">Subject Categories:</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {categories.map(cat => {
            const count = cat === 'ALL' ? courses.length : courses.filter(c => c.category === cat).length;
            if (cat !== 'ALL' && count === 0) return null;
            return (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  filterCategory === cat
                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                    : 'bg-[#141824] text-gray-400 hover:text-gray-200 border border-[#202538]'
                }`}
              >
                {cat} <span className="text-[10px] opacity-70">({count})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Courses List */}
      <div className="space-y-4">
        {filteredCourses.map((course, idx) => {
          const categoryStyle = getCategoryBadge(course.category);
          const convMax = course.converted_total_max;
          const enteredCount = course.entered_components ?? 0;
          const pendingCount = course.pending_components ?? 0;

          return (
            <div 
              key={course.code || idx} 
              className="p-5 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-4 hover:border-[#2f354a] transition-all"
            >
              {/* Course Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-3.5 border-b border-[#1c202e]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-purple-300 bg-purple-500/10 px-2.5 py-0.5 rounded border border-purple-500/20">
                      {course.code}
                    </span>
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded border ${categoryStyle}`}>
                      {course.category}
                    </span>
                    {convMax && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#181c2b] border border-[#282e42] text-gray-300">
                        CA Weight: {convMax} Marks
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-white mt-1.5">
                    {course.name}
                  </h3>
                </div>

                {/* Status Indicator */}
                <div className="flex items-center gap-2 self-start sm:self-auto">
                  <span className={`text-xs px-2.5 py-1 rounded-md font-mono flex items-center gap-1.5 ${
                    pendingCount > 0 
                      ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20' 
                      : 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                  }`}>
                    {pendingCount > 0 ? (
                      <>
                        <FiClock size={12} className="text-amber-400" />
                        <span>{enteredCount} Recorded • {pendingCount} Pending</span>
                      </>
                    ) : (
                      <>
                        <FiCheck size={12} className="text-emerald-400" />
                        <span>Evaluations Complete</span>
                      </>
                    )}
                  </span>
                </div>
              </div>

              {/* Components Evaluation Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
                {(course.components || []).map((comp, cIdx) => {
                  const isEntered = comp.status === 'entered';
                  const isPending = comp.status === 'pending';
                  const isNA = comp.status === 'not_applicable';

                  return (
                    <div 
                      key={cIdx}
                      className={`p-3 rounded-lg border flex flex-col justify-between ${
                        isEntered 
                          ? 'bg-[#171b28] border-[#2b3145]' 
                          : isPending 
                            ? 'bg-[#151822]/80 border-[#222736]' 
                            : 'bg-[#11131c] border-[#1a1d29] opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-between text-[11px] text-gray-400 font-medium">
                        <span className="font-mono text-purple-300">{comp.label}</span>
                        {comp.max_marks && (
                          <span className="text-[10px] text-gray-500 font-mono">Max {comp.max_marks}</span>
                        )}
                      </div>

                      <div className="my-2">
                        {isEntered ? (
                          <div>
                            <div className="text-lg font-bold text-white tracking-tight">
                              {comp.numeric_value}
                            </div>
                            {comp.percentage !== null && (
                              <div className="text-[10px] font-mono text-emerald-400 flex items-center gap-1 mt-0.5">
                                <span>{comp.percentage}%</span>
                              </div>
                            )}
                          </div>
                        ) : isPending ? (
                          <div className="text-xs font-mono font-medium text-amber-400/90 flex items-center gap-1">
                            <FiClock size={11} />
                            <span>Pending (*)</span>
                          </div>
                        ) : (
                          <div className="text-xs font-mono text-gray-600 flex items-center gap-1">
                            <FiMinus size={11} />
                            <span>N/A</span>
                          </div>
                        )}
                      </div>

                      <div className="text-[9px] text-gray-500 pt-1.5 border-t border-[#1e2333]">
                        {isEntered 
                          ? 'Recorded score' 
                          : isPending 
                            ? 'Faculty entry awaited' 
                            : 'Not attempted'}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Course Footer Note */}
              <div className="pt-2 border-t border-[#1a1d2a] text-[11px] text-gray-400 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <span>
                  {course.category === 'Theory' && 'Theory continuous evaluation includes periodical tests (T1/T2), tutorials, and assignments scaled to 40.'}
                  {course.category === 'Laboratory' && 'Laboratory continuous evaluation includes weekly experiments, observation, and internal lab tests scaled to 60.'}
                  {course.category === 'Project' && 'Project continuous evaluation covers periodic guide and committee reviews with viva-voce.'}
                  {course.category === 'Mandatory/Audit' && 'Audit/Mandatory subject evaluations are assessed continuously on a 100-mark internal scale.'}
                </span>
                <span className="font-mono text-[10px] text-gray-500">
                  StudZone 1 Sync
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CAComponentBreakdown;
