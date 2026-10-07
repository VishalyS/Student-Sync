import React, { useState, useEffect } from 'react';
import { 
  FiPlus, 
  FiTrash2, 
  FiRotateCcw, 
  FiTrendingUp, 
  FiTrendingDown, 
  FiInfo, 
  FiCheck,
  FiSliders,
  FiBookOpen,
  FiZap
} from 'react-icons/fi';

const GRADE_OPTIONS = [
  { grade: 'O', point: 10.0, label: 'O (Outstanding • 10.0)' },
  { grade: 'A+', point: 9.0, label: 'A+ (Excellent • 9.0)' },
  { grade: 'A', point: 8.0, label: 'A (Very Good • 8.0)' },
  { grade: 'B+', point: 7.0, label: 'B+ (Good • 7.0)' },
  { grade: 'B', point: 6.5, label: 'B (Average • 6.5)' },
  { grade: 'C+', point: 6.0, label: 'C+ (Satisfactory • 6.0)' },
  { grade: 'C', point: 5.0, label: 'C (Pass • 5.0)' },
  { grade: 'RA', point: 0.0, label: 'RA (Reappearance • 0.0)' }
];

const CgpaSimulator = ({ baseCredits = 24.0, baseCgpa = 7.96, onSimulateRemote }) => {
  // Configurable base state
  const [creditsBase, setCreditsBase] = useState(baseCredits);
  const [cgpaBase, setCgpaBase] = useState(baseCgpa);

  // New course input form state (no hardcoded default 3.0 credits)
  const [newCourseName, setNewCourseName] = useState('');
  const [newCourseCredits, setNewCourseCredits] = useState('');
  const [newCourseGrade, setNewCourseGrade] = useState('A+');
  const [formError, setFormError] = useState('');

  // Simulated courses list
  const [simulatedCourses, setSimulatedCourses] = useState([]);

  // Sync initial props
  useEffect(() => {
    if (baseCredits > 0) setCreditsBase(baseCredits);
    if (baseCgpa > 0) setCgpaBase(baseCgpa);
  }, [baseCredits, baseCgpa]);

  // Handle adding a course
  const handleAddCourse = (e) => {
    e.preventDefault();
    setFormError('');

    const cr = parseFloat(newCourseCredits);
    if (isNaN(cr) || cr <= 0 || cr > 12) {
      setFormError('Please enter a valid credit value between 0.5 and 12.0.');
      return;
    }

    const matched = GRADE_OPTIONS.find(g => g.grade === newCourseGrade);
    const gp = matched ? matched.point : 8.0;

    const courseItem = {
      id: Date.now() + Math.random(),
      course_name: newCourseName.trim() || `Course ${simulatedCourses.length + 1}`,
      credits: cr,
      grade: newCourseGrade,
      grade_point: gp,
      points: Math.round(cr * gp * 100) / 100
    };

    const updated = [...simulatedCourses, courseItem];
    setSimulatedCourses(updated);
    setNewCourseName('');
    setNewCourseCredits('');
  };

  // Handle removing a course
  const handleRemoveCourse = (id) => {
    setSimulatedCourses(simulatedCourses.filter(c => c.id !== id));
  };

  // Reset simulation
  const handleReset = () => {
    setSimulatedCourses([]);
    setCreditsBase(baseCredits);
    setCgpaBase(baseCgpa);
    setFormError('');
  };

  // Quick preset: Add current semester course bundle with custom credits
  const handleAddQuickBundle = () => {
    const bundle = [
      { id: Date.now() + 1, course_name: 'Theory Core I', credits: 4.0, grade: 'A+', grade_point: 9.0, points: 36.0 },
      { id: Date.now() + 2, course_name: 'Theory Core II', credits: 4.0, grade: 'A', grade_point: 8.0, points: 32.0 },
      { id: Date.now() + 3, course_name: 'Professional Elective', credits: 3.0, grade: 'A', grade_point: 8.0, points: 24.0 },
      { id: Date.now() + 4, course_name: 'Computing Laboratory', credits: 2.0, grade: 'O', grade_point: 10.0, points: 20.0 }
    ];
    setSimulatedCourses([...simulatedCourses, ...bundle]);
  };

  // Calculate projected CGPA locally (in-memory)
  const simCreditsTot = simulatedCourses.reduce((sum, c) => sum + c.credits, 0);
  const simPointsTot = simulatedCourses.reduce((sum, c) => sum + (c.credits * c.grade_point), 0);
  const totalCredits = creditsBase + simCreditsTot;
  
  let projectedCgpa = cgpaBase;
  if (totalCredits > 0) {
    const totalPoints = (creditsBase * cgpaBase) + simPointsTot;
    projectedCgpa = Math.round((totalPoints / totalCredits) * 100) / 100;
  }
  const delta = Math.round((projectedCgpa - cgpaBase) * 100) / 100;

  return (
    <div className="space-y-5">
      {/* Simulation Result Header Card */}
      <div className="p-6 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#1c202e]">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-white">Interactive What-If CGPA Simulator</h2>
              <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300 font-mono">
                100% In-Memory
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Simulate upcoming course grades to explore potential changes to your cumulative GPA
            </p>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#181c2b] hover:bg-[#23283b] border border-[#2b3145] text-xs font-medium text-gray-300 hover:text-white transition-all"
            >
              <FiRotateCcw size={12} className="text-purple-400" />
              <span>Reset</span>
            </button>
          </div>
        </div>

        {/* Projected CGPA Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold tracking-wider">Base CGPA</div>
            <div className="text-3xl font-extrabold text-white mt-1">
              {cgpaBase.toFixed(2)}
            </div>
            <div className="text-[11px] text-gray-400 mt-1">
              {creditsBase} verified credits
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold tracking-wider">Projected CGPA</div>
            <div className="text-3xl font-extrabold text-purple-300 mt-1">
              {projectedCgpa.toFixed(2)}
            </div>
            <div className="text-[11px] mt-1 flex items-center gap-1">
              {delta > 0 ? (
                <span className="text-emerald-400 font-mono font-semibold flex items-center gap-1">
                  <FiTrendingUp size={12} /> +{delta.toFixed(2)}
                </span>
              ) : delta < 0 ? (
                <span className="text-rose-400 font-mono font-semibold flex items-center gap-1">
                  <FiTrendingDown size={12} /> {delta.toFixed(2)}
                </span>
              ) : (
                <span className="text-gray-400 font-mono">0.00 (Neutral)</span>
              )}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold tracking-wider">Simulated Credits</div>
            <div className="text-3xl font-extrabold text-white mt-1">
              +{simCreditsTot}
            </div>
            <div className="text-[11px] text-gray-400 mt-1">
              {simulatedCourses.length} simulated courses
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#171b28] border border-[#24293c]">
            <div className="text-[10px] text-gray-400 uppercase font-semibold tracking-wider">Total Projected Credits</div>
            <div className="text-3xl font-extrabold text-white mt-1">
              {totalCredits}
            </div>
            <div className="text-[11px] text-purple-300 mt-1 font-mono">
              Base + Simulated
            </div>
          </div>
        </div>

        {/* Calculation Formula Transparency */}
        <div className="p-3 rounded-lg bg-[#0f111a] border border-[#1e2333] text-xs font-mono text-gray-400 flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="text-purple-400 font-semibold">Formula: </span>
            <span>(({creditsBase} × {cgpaBase.toFixed(2)}) + {simPointsTot.toFixed(1)}) / {totalCredits} = </span>
            <span className="text-purple-300 font-bold">{projectedCgpa.toFixed(2)}</span>
          </div>
          <span className="text-[10px] text-gray-500">Zero database writes</span>
        </div>
      </div>

      {/* Add Course Form & Preset Buttons */}
      <div className="p-5 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#1c202e]">
          <div>
            <h3 className="text-sm font-semibold text-white">Add Course to Simulation</h3>
            <p className="text-xs text-gray-400">Specify hypothetical credits and grade target</p>
          </div>
          <button
            type="button"
            onClick={handleAddQuickBundle}
            className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/25 text-xs font-medium text-purple-300 transition-all"
          >
            <FiZap size={12} />
            <span>Load Typical Semester Template (+13 credits)</span>
          </button>
        </div>

        <form onSubmit={handleAddCourse} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
            {/* Course Title */}
            <div className="sm:col-span-5">
              <label className="block text-[11px] font-medium text-gray-400 mb-1">
                Course Title / Code (Optional)
              </label>
              <input
                type="text"
                value={newCourseName}
                onChange={(e) => setNewCourseName(e.target.value)}
                placeholder="e.g. Cloud Computing Architecture"
                className="w-full px-3 py-2 rounded-lg bg-[#171b28] border border-[#2b3145] text-white text-xs placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
              />
            </div>

            {/* Explicit Credits Input */}
            <div className="sm:col-span-3">
              <label className="block text-[11px] font-medium text-gray-400 mb-1">
                Course Credits <span className="text-purple-400">*</span>
              </label>
              <input
                type="number"
                step="0.5"
                min="0.5"
                max="12"
                value={newCourseCredits}
                onChange={(e) => setNewCourseCredits(e.target.value)}
                placeholder="e.g. 4.0 or 3.0"
                className="w-full px-3 py-2 rounded-lg bg-[#171b28] border border-[#2b3145] text-white text-xs placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
                required
              />
            </div>

            {/* Grade Selector */}
            <div className="sm:col-span-4">
              <label className="block text-[11px] font-medium text-gray-400 mb-1">
                Target Grade <span className="text-purple-400">*</span>
              </label>
              <select
                value={newCourseGrade}
                onChange={(e) => setNewCourseGrade(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-[#171b28] border border-[#2b3145] text-white text-xs focus:outline-none focus:border-purple-500 transition-colors"
              >
                {GRADE_OPTIONS.map((g) => (
                  <option key={g.grade} value={g.grade}>
                    {g.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {formError && (
            <div className="text-xs text-rose-400 flex items-center gap-1.5 pt-1">
              <FiInfo size={12} />
              <span>{formError}</span>
            </div>
          )}

          <div className="pt-2 flex justify-end">
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-purple-500/20 transition-all"
            >
              <FiPlus size={14} />
              <span>Add Course to Simulation</span>
            </button>
          </div>
        </form>
      </div>

      {/* Simulated Courses Table */}
      {simulatedCourses.length > 0 && (
        <div className="p-5 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#1c202e]">
            <h3 className="text-sm font-semibold text-white">Simulated Course Basket</h3>
            <span className="text-xs font-mono text-purple-300">
              {simulatedCourses.length} Courses • {simCreditsTot} Credits
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#1f2436] text-[11px] uppercase tracking-wider text-gray-400 font-semibold bg-[#10121a]">
                  <th className="py-2.5 px-3">#</th>
                  <th className="py-2.5 px-3">Course Name</th>
                  <th className="py-2.5 px-3 text-center">Credits</th>
                  <th className="py-2.5 px-3 text-center">Grade</th>
                  <th className="py-2.5 px-3 text-center">Grade Point</th>
                  <th className="py-2.5 px-3 text-center">Points (C × GP)</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#181c2b]">
                {simulatedCourses.map((c, idx) => (
                  <tr key={c.id} className="hover:bg-[#161a27] transition-colors">
                    <td className="py-3 px-3 text-gray-500 font-mono">{idx + 1}</td>
                    <td className="py-3 px-3 text-white font-medium">{c.course_name}</td>
                    <td className="py-3 px-3 text-center font-mono text-gray-300">{c.credits}</td>
                    <td className="py-3 px-3 text-center">
                      <span className="px-2 py-0.5 rounded font-mono font-bold text-xs bg-purple-500/15 text-purple-300 border border-purple-500/25">
                        {c.grade}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center font-mono text-gray-300">{c.grade_point}</td>
                    <td className="py-3 px-3 text-center font-mono text-purple-400">{c.points}</td>
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={() => handleRemoveCourse(c.id)}
                        className="p-1.5 rounded-md hover:bg-rose-500/15 text-gray-400 hover:text-rose-400 transition-colors"
                        title="Remove course"
                      >
                        <FiTrash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Official Academic Disclaimer */}
      <div className="p-4 rounded-xl bg-[#141724] border border-[#232738] flex items-start gap-3">
        <FiInfo className="text-purple-400 flex-shrink-0 mt-0.5" size={16} />
        <div className="text-xs text-gray-300 space-y-1">
          <span className="font-semibold text-white">Mathematical Model Notice: </span>
          <span>
            This What-If simulator is strictly an in-memory decision tool. No simulated credits, grades, 
            or projected indices are written to MongoDB Atlas or official institutional records. 
            Official PSG Tech degree grades are governed solely by authorized Controller of Examinations result publications.
          </span>
        </div>
      </div>
    </div>
  );
};

export default CgpaSimulator;
