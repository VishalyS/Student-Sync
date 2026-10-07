import React, { useState, useMemo } from 'react';
import { 
  FiSearch, 
  FiFilter, 
  FiAlertTriangle, 
  FiCheckCircle, 
  FiClock, 
  FiFileText,
  FiAward,
  FiBookOpen
} from 'react-icons/fi';

const SubjectRiskMatrix = ({ subjectMatrix = [] }) => {
  const [filterType, setFilterType] = useState('ALL'); // 'ALL' | 'ATTENTION' | 'SAFE'
  const [searchQuery, setSearchQuery] = useState('');

  const filteredSubjects = useMemo(() => {
    return subjectMatrix.filter((item) => {
      // Search matching
      const query = searchQuery.trim().toLowerCase();
      const matchesSearch = !query || 
        item.code?.toLowerCase().includes(query) || 
        item.name?.toLowerCase().includes(query);

      if (!matchesSearch) return false;

      // Filter category
      if (filterType === 'ATTENTION') {
        return item.attention_needed;
      }
      if (filterType === 'SAFE') {
        return !item.attention_needed;
      }
      return true;
    });
  }, [subjectMatrix, filterType, searchQuery]);

  const getPriorityBadge = (prio) => {
    const level = prio?.level || 'LOW';
    switch (level) {
      case 'HIGH':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20 whitespace-nowrap">
            High ({prio?.score})
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 whitespace-nowrap">
            Medium ({prio?.score})
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 whitespace-nowrap">
            Low ({prio?.score})
          </span>
        );
    }
  };

  return (
    <div className="bg-[#151922] border border-[#232938] rounded-2xl p-6 mb-8 shadow-sm">
      {/* Header & Filter Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-5 border-b border-[#232938]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase tracking-wider">
              Cross-Module Matrix
            </span>
            <span className="text-xs text-gray-400">8 Registered Subjects</span>
          </div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FiBookOpen className="text-blue-400" />
            Subject Intelligence & Risk Matrix
          </h2>
          <p className="text-xs sm:text-sm text-gray-400 mt-0.5">
            Unified view of attendance margins, safe bunks, CA progress, timetable load, and exam readiness.
          </p>
        </div>

        {/* Filter Pills & Search */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
          {/* Search Input */}
          <div className="relative">
            <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-xs" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search course..."
              className="w-full sm:w-44 pl-8 pr-3 py-1.5 rounded-lg bg-[#0e1118] border border-[#232938] text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
            />
          </div>

          {/* Filter Pills */}
          <div className="flex items-center bg-[#0e1118] p-1 rounded-lg border border-[#232938]">
            <button
              onClick={() => setFilterType('ALL')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                filterType === 'ALL'
                  ? 'bg-purple-600 text-white font-semibold'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              All ({subjectMatrix.length})
            </button>
            <button
              onClick={() => setFilterType('ATTENTION')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                filterType === 'ATTENTION'
                  ? 'bg-amber-600 text-white font-semibold'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Attention Needed
            </button>
            <button
              onClick={() => setFilterType('SAFE')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                filterType === 'SAFE'
                  ? 'bg-emerald-600 text-white font-semibold'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Stable
            </button>
          </div>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto mt-4 scrollbar-thin">
        <table className="w-full text-left text-xs border-collapse min-w-[760px]">
          <thead>
            <tr className="border-b border-[#232938] text-gray-400 font-semibold uppercase text-[11px]">
              <th className="py-3 px-3">Course</th>
              <th className="py-3 px-3">Category</th>
              <th className="py-3 px-3">Attendance</th>
              <th className="py-3 px-3">Safe Bunks</th>
              <th className="py-3 px-3">Weekly Hours</th>
              <th className="py-3 px-3">CA Progress</th>
              <th className="py-3 px-3">Exam Status</th>
              <th className="py-3 px-3 text-right">Academic Priority</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e2433]">
            {filteredSubjects.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-gray-500">
                  No courses match your filter criteria.
                </td>
              </tr>
            ) : (
              filteredSubjects.map((item) => {
                const att = item.attendance || {};
                const sched = item.schedule || {};
                const ca = item.ca_progress || {};
                const ex = item.exam || {};
                const prio = item.priority || {};
                const isBoundary = att.safe_bunks === 0 || att.percentage < 75.0;

                return (
                  <tr 
                    key={item.code} 
                    className="hover:bg-[#191f2c]/50 transition-colors"
                  >
                    {/* Course Code & Name */}
                    <td className="py-3 px-3">
                      <div className="font-mono font-bold text-white text-xs">{item.code}</div>
                      <div className="text-gray-400 text-[11px] max-w-[180px] truncate" title={item.name}>
                        {item.name}
                      </div>
                    </td>

                    {/* Category */}
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded text-[11px] bg-[#1a202d] text-gray-300 border border-[#262f43]">
                        {item.category || 'Theory'}
                      </span>
                    </td>

                    {/* Attendance */}
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5 font-bold">
                        <span className={att.percentage >= 75 ? 'text-emerald-400' : 'text-amber-400'}>
                          {att.percentage?.toFixed(2)}%
                        </span>
                      </div>
                      <div className="text-[11px] text-gray-500">
                        {att.attended}/{att.conducted} classes
                      </div>
                    </td>

                    {/* Safe Bunks */}
                    <td className="py-3 px-3">
                      {att.safe_bunks === 0 ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20 whitespace-nowrap">
                          0 safe bunks
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 whitespace-nowrap">
                          {att.safe_bunks} safe bunk{att.safe_bunks !== 1 ? 's' : ''}
                        </span>
                      )}
                    </td>

                    {/* Weekly Hours */}
                    <td className="py-3 px-3">
                      <div className="text-gray-300 font-medium">
                        {sched.weekly_periods} periods/wk
                      </div>
                      {sched.scheduled_today && (
                        <span className="text-[10px] text-purple-400 font-semibold">
                          Scheduled today
                        </span>
                      )}
                    </td>

                    {/* CA Progress */}
                    <td className="py-3 px-3">
                      <div className="text-gray-300 text-[11px]">
                        <span className="text-white font-medium">{ca.entered}</span> entered,{' '}
                        <span className="text-amber-400 font-medium">{ca.pending}</span> pending
                      </div>
                      <div className="w-20 bg-[#1e2330] rounded-full h-1 mt-1 overflow-hidden">
                        <div 
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${(ca.entered / (ca.total_components || 1)) * 100}%` }}
                        />
                      </div>
                    </td>

                    {/* Exam Status */}
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded text-[11px] bg-[#1a202d] text-gray-300 border border-[#262f43] block w-fit">
                        {ex.exam_date || 'Pending'}
                      </span>
                    </td>

                    {/* Academic Priority */}
                    <td className="py-3 px-3 text-right">
                      {getPriorityBadge(prio)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SubjectRiskMatrix;
