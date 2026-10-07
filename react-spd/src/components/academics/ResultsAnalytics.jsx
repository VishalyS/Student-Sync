import React from 'react';
import { 
  FiAward, 
  FiCheckCircle, 
  FiAlertCircle, 
  FiBookOpen, 
  FiTrendingUp, 
  FiHash,
  FiCheck
} from 'react-icons/fi';

const ResultsAnalytics = ({ resultsData }) => {
  if (!resultsData || !resultsData.courses || resultsData.courses.length === 0) {
    return (
      <div className="py-16 text-center text-xs text-gray-500 rounded-xl bg-[#131620] border border-[#232738]">
        No historical examination results found on StudZone 2.
      </div>
    );
  }

  const {
    courses = [],
    total_credits = 0,
    total_grade_points = 0,
    calculated_cgpa = 0,
    stored_cgpa = 0,
    cgpa_verified = false,
    grade_distribution = {},
    semester_breakdown = [],
    arrears_count = 0,
    all_cleared = true
  } = resultsData;

  const gradeColors = {
    'O': 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    'A+': 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    'A': 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    'B+': 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    'B': 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
    'C+': 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    'C': 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
    'RA': 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    'F': 'bg-rose-500/15 text-rose-300 border-rose-500/30'
  };

  return (
    <div className="space-y-5">
      {/* CGPA Verification Banner */}
      <div className="p-6 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#1c202e]">
          <div>
            <h2 className="text-base font-semibold text-white">Cumulative Grade Point Average (CGPA)</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Weighted academic index across published semester examinations
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono font-medium border ${
              cgpa_verified 
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                : 'bg-purple-500/10 text-purple-400 border-purple-500/20'
            }`}>
              <FiCheckCircle size={13} />
              <span>{cgpa_verified ? 'Verified with Portal Records' : 'Calculated'}</span>
            </span>
          </div>
        </div>

        {/* Big Numbers Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold tracking-wider">Official CGPA</div>
            <div className="text-3xl font-extrabold text-white mt-1">
              {stored_cgpa || calculated_cgpa}
            </div>
            <div className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
              <FiCheck size={12} />
              <span>Accredited Scale (10.0)</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold tracking-wider">Earned Credits</div>
            <div className="text-3xl font-extrabold text-purple-300 mt-1">
              {total_credits}
            </div>
            <div className="text-[11px] text-gray-400 mt-1">
              {courses.length} courses completed
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold tracking-wider">Total Grade Points</div>
            <div className="text-3xl font-extrabold text-white mt-1">
              {total_grade_points}
            </div>
            <div className="text-[11px] text-gray-400 mt-1 font-mono">
              Σ (Credits × GP)
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold tracking-wider">Arrears / Reappearances</div>
            <div className={`text-3xl font-extrabold mt-1 ${arrears_count === 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {arrears_count}
            </div>
            <div className="text-[11px] text-gray-400 mt-1">
              {all_cleared ? 'Nil standing arrears' : 'Arrears pending clearance'}
            </div>
          </div>
        </div>

        {/* Mathematical Proof Strip */}
        <div className="p-3 rounded-lg bg-[#0f111a] border border-[#1e2333] flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-gray-400">
          <div className="flex items-center gap-2">
            <span className="text-purple-400 font-semibold">Formula:</span>
            <span className="text-gray-300">CGPA = Total Points / Total Credits = {total_grade_points} / {total_credits} = </span>
            <span className="text-emerald-400 font-bold">{calculated_cgpa}</span>
          </div>
          <span className="text-[10px] text-gray-500">Source: StudZone 2 Official Records</span>
        </div>
      </div>

      {/* Grade Distribution & Semester Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Grade Distribution */}
        <div className="p-5 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-[#1c202e]">
            <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Grade Distribution</h3>
            <span className="text-[11px] text-gray-400">{courses.length} Graded Units</span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {Object.keys(grade_distribution).length > 0 ? (
              Object.entries(grade_distribution).map(([gr, cnt]) => (
                <div 
                  key={gr}
                  className={`px-3 py-2 rounded-lg border flex items-center gap-2 ${gradeColors[gr] || 'bg-[#181c2b] text-white border-[#282e42]'}`}
                >
                  <span className="font-bold font-mono text-sm">{gr}</span>
                  <span className="text-xs opacity-80">× {cnt}</span>
                </div>
              ))
            ) : (
              <span className="text-xs text-gray-500">No grades recorded.</span>
            )}
          </div>
        </div>

        {/* Semester SGPA Breakdown */}
        <div className="p-5 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-[#1c202e]">
            <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Semester SGPA Breakdown</h3>
            <span className="text-[11px] text-gray-400">{semester_breakdown.length} Semesters</span>
          </div>
          <div className="space-y-2">
            {semester_breakdown.map((sem, sIdx) => (
              <div 
                key={sIdx}
                className="p-3 rounded-lg bg-[#171b28] border border-[#24293c] flex items-center justify-between"
              >
                <div>
                  <div className="text-xs font-semibold text-white">Semester {sem.semester}</div>
                  <div className="text-[11px] text-gray-400">{sem.courses_count} courses • {sem.credits} credits</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold text-purple-300 font-mono">SGPA: {sem.sgpa}</div>
                  <div className="text-[10px] text-gray-500 font-mono">{sem.points} points</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Complete Published Results Table */}
      <div className="p-5 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#1c202e]">
          <div>
            <h3 className="text-sm font-semibold text-white">Course Grade Records</h3>
            <p className="text-xs text-gray-400">Detailed course grades and credit weights as published</p>
          </div>
          <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2.5 py-0.5 rounded border border-purple-500/20">
            {courses.length} Recorded Courses
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#1f2436] text-[11px] uppercase tracking-wider text-gray-400 font-semibold bg-[#10121a]">
                <th className="py-2.5 px-3">Sem</th>
                <th className="py-2.5 px-3">Course Code</th>
                <th className="py-2.5 px-3">Course Title</th>
                <th className="py-2.5 px-3 text-center">Credits</th>
                <th className="py-2.5 px-3 text-center">Grade</th>
                <th className="py-2.5 px-3 text-center">Grade Point</th>
                <th className="py-2.5 px-3 text-center">Points Earned</th>
                <th className="py-2.5 px-3 text-right">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#181c2b]">
              {courses.map((c, i) => {
                const grStyle = gradeColors[c.grade] || 'text-white';
                return (
                  <tr key={i} className="hover:bg-[#161a27] transition-colors">
                    <td className="py-3 px-3 text-gray-400 font-mono">{c.sem || '—'}</td>
                    <td className="py-3 px-3 font-mono font-semibold text-purple-300">{c.code}</td>
                    <td className="py-3 px-3 text-gray-200 font-medium">{c.title}</td>
                    <td className="py-3 px-3 text-center font-mono text-gray-300">{c.credits}</td>
                    <td className="py-3 px-3 text-center">
                      <span className={`px-2 py-0.5 rounded font-mono font-bold text-xs border ${grStyle}`}>
                        {c.grade}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center font-mono text-gray-300">{c.grade_point}</td>
                    <td className="py-3 px-3 text-center font-mono text-purple-400">{c.points_earned}</td>
                    <td className="py-3 px-3 text-right">
                      <span className={`inline-flex items-center gap-1 text-[11px] font-medium ${
                        c.result_status.toLowerCase() === 'pass' ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        {c.result_status.toLowerCase() === 'pass' && <FiCheck size={11} />}
                        {c.result_status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ResultsAnalytics;
