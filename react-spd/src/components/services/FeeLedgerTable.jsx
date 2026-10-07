import React, { useState } from 'react';
import { 
  FiDollarSign, 
  FiTag, 
  FiCheckCircle, 
  FiInfo, 
  FiFilter, 
  FiSearch,
  FiPieChart
} from 'react-icons/fi';

const FeeLedgerTable = ({ fees }) => {
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  if (!fees || !fees.items || fees.items.length === 0) {
    return (
      <div className="bg-[#121520] border border-[#1e2333] rounded-2xl p-6 text-center text-gray-400">
        <FiDollarSign className="mx-auto text-3xl mb-2 text-gray-500" />
        <p>No institutional fee ledger records are available from the portal.</p>
      </div>
    );
  }

  const {
    status,
    total_amount,
    currency,
    items,
    breakdown_by_category
  } = fees;

  const categories = ['ALL', ...Object.keys(breakdown_by_category || {})];

  // Filtering
  const filteredItems = items.filter(item => {
    const matchesCategory = selectedCategory === 'ALL' || item.category === selectedCategory;
    const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const getCategoryColor = (cat) => {
    switch (cat) {
      case 'Academic':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
      case 'Examinations':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
      case 'Institutional':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'University':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'Department':
        return 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
      case 'Sports':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      default:
        return 'bg-gray-500/10 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div className="bg-[#121520] border border-[#1e2333] rounded-2xl overflow-hidden shadow-xl">
      {/* Header Banner */}
      <div className="p-6 sm:p-8 border-b border-[#1e2333] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <FiDollarSign className="text-emerald-400" /> Institutional Fee Ledger
            </h3>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              {status || 'Active / Available'}
            </span>
          </div>
          <p className="text-sm text-gray-400">
            Verified breakdown of semester institutional fees and department levies.
          </p>
        </div>

        {/* Total Metric Card */}
        <div className="px-5 py-3 rounded-2xl bg-[#161a27] border border-[#23293e] flex items-center gap-4 flex-shrink-0">
          <div>
            <div className="text-[10px] uppercase font-mono tracking-wider text-gray-400">Total Semester Dues</div>
            <div className="text-2xl font-extrabold text-emerald-400 font-mono tracking-tight">
              ₹ {total_amount?.toLocaleString('en-IN') || '0'}
            </div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <FiCheckCircle className="text-lg" />
          </div>
        </div>
      </div>

      {/* Category Breakdown Chips */}
      {breakdown_by_category && Object.keys(breakdown_by_category).length > 0 && (
        <div className="bg-[#10131e] px-6 py-4 border-b border-[#1e2333] flex flex-wrap items-center gap-3">
          <span className="text-xs text-gray-400 font-mono flex items-center gap-1.5 mr-1">
            <FiPieChart className="text-sm text-purple-400" /> Categories:
          </span>
          {Object.entries(breakdown_by_category).map(([cat, amt]) => (
            <div 
              key={cat} 
              className={`px-3 py-1 rounded-xl text-xs font-medium border flex items-center gap-1.5 ${getCategoryColor(cat)}`}
            >
              <span>{cat}:</span>
              <span className="font-mono font-bold">₹ {amt.toLocaleString('en-IN')}</span>
            </div>
          ))}
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="p-4 sm:p-6 border-b border-[#1e2333] flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Category Tabs */}
        <div className="flex flex-wrap items-center gap-1.5">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedCategory === cat
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20'
                  : 'bg-[#161a26] text-gray-400 hover:text-gray-200 hover:bg-[#1c2132] border border-[#21273a]'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative min-w-[200px]">
          <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs" />
          <input
            type="text"
            placeholder="Search fee items..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#161a26] border border-[#21273a] rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
          />
        </div>
      </div>

      {/* Items Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-[#10131e] text-[11px] font-mono uppercase tracking-wider text-gray-400 border-b border-[#1e2333]">
              <th className="py-3 px-6">S.No</th>
              <th className="py-3 px-6">Fee Component Description</th>
              <th className="py-3 px-6">Category</th>
              <th className="py-3 px-6 text-right">Amount (INR)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1b2030]">
            {filteredItems.map((item, idx) => (
              <tr key={idx} className="hover:bg-[#161a28]/60 transition-colors">
                <td className="py-3 px-6 font-mono text-xs text-gray-400">
                  {idx + 1}
                </td>
                <td className="py-3 px-6 font-medium text-gray-200">
                  {item.name}
                </td>
                <td className="py-3 px-6">
                  <span className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${getCategoryColor(item.category)}`}>
                    {item.category}
                  </span>
                </td>
                <td className="py-3 px-6 text-right font-mono font-bold text-emerald-400 text-sm">
                  ₹ {item.amount.toLocaleString('en-IN')}
                </td>
              </tr>
            ))}
            {filteredItems.length === 0 && (
              <tr>
                <td colSpan="4" className="py-8 text-center text-gray-400 text-xs">
                  No fee items match the selected filter or search query.
                </td>
              </tr>
            )}
          </tbody>
          {filteredItems.length > 0 && (
            <tfoot>
              <tr className="bg-[#10131e] font-semibold border-t border-[#1e2333] text-gray-200">
                <td colSpan="3" className="py-3.5 px-6 text-right font-mono text-xs uppercase tracking-wider">
                  Total Allocated Dues:
                </td>
                <td className="py-3.5 px-6 text-right font-mono font-extrabold text-emerald-400 text-base">
                  ₹ {total_amount?.toLocaleString('en-IN')}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* Read-Only Disclaimer Banner */}
      <div className="bg-[#0e111a] border-t border-[#1e2333] px-6 py-3 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-gray-400">
        <span className="flex items-center gap-1.5 text-amber-400/90 font-medium">
          <FiInfo className="text-sm flex-shrink-0" /> Read-only institutional fee record. Online payments are handled through official bank challans or college portal.
        </span>
        <span className="text-[11px] font-mono text-gray-400">
          Source: StudZone 1 Accounts
        </span>
      </div>
    </div>
  );
};

export default FeeLedgerTable;
