import React, { useState } from 'react';
import { 
  FiAward, 
  FiCheckCircle, 
  FiClock, 
  FiFileText, 
  FiInfo, 
  FiDollarSign,
  FiAlertCircle
} from 'react-icons/fi';

const ScholarshipSummary = ({ scholarships }) => {
  const [activeTab, setActiveTab] = useState('received');

  if (!scholarships) {
    return (
      <div className="bg-[#121520] border border-[#1e2333] rounded-2xl p-6 text-center text-gray-400">
        <FiAward className="mx-auto text-3xl mb-2 text-gray-500" />
        <p>No scholarship scheme records available from institutional records.</p>
      </div>
    );
  }

  const {
    applied_count,
    received_count,
    applied,
    received
  } = scholarships;

  return (
    <div className="bg-[#121520] border border-[#1e2333] rounded-2xl overflow-hidden shadow-xl">
      {/* Header Banner */}
      <div className="p-6 sm:p-8 border-b border-[#1e2333] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <FiAward className="text-purple-400" /> Scholarships & Financial Schemes
            </h3>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 border border-purple-500/30 text-purple-400">
              {received_count + applied_count} Schemes Tracked
            </span>
          </div>
          <p className="text-sm text-gray-400">
            Institutional tracking for government welfare and scholarship assistance schemes.
          </p>
        </div>

        {/* Tab Toggle: Applied vs Received */}
        <div className="flex items-center p-1 rounded-xl bg-[#161a26] border border-[#21273a] flex-shrink-0">
          <button
            onClick={() => setActiveTab('received')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'received'
                ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <FiCheckCircle className="text-xs" /> Received / Disbursed ({received_count || 0})
          </button>
          <button
            onClick={() => setActiveTab('applied')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'applied'
                ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <FiClock className="text-xs" /> Applied Schemes ({applied_count || 0})
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="p-6 sm:p-8">
        {activeTab === 'received' ? (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-xs font-mono uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                <FiCheckCircle className="text-emerald-400" /> Received / Disbursed Schemes
              </h4>
              <span className="text-xs text-gray-400">
                Official verified sanction records
              </span>
            </div>

            {received && received.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {received.map((rec, idx) => (
                  <div 
                    key={idx}
                    className="p-5 rounded-xl bg-[#151926] border border-[#212638] flex flex-col justify-between hover:border-purple-500/30 transition-colors"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                          Status: {rec.disbursement_status || 'Received'}
                        </span>
                        <span className="text-xs font-mono text-gray-400">
                          AY: {rec.year || 'N/A'}
                        </span>
                      </div>
                      <h5 className="text-sm font-bold text-gray-200 mb-2">
                        {rec.scheme_name || 'Scholarship Scheme'}
                      </h5>
                    </div>

                    <div className="pt-3 border-t border-[#1e2333] flex items-center justify-between">
                      <span className="text-xs text-gray-400 font-mono">Disbursed Amount</span>
                      <span className="text-lg font-bold font-mono text-emerald-400">
                        ₹ {rec.amount ? rec.amount.toLocaleString('en-IN') : 'N/A'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-gray-400 bg-[#151926] rounded-xl border border-[#212638]">
                No received or disbursed scholarships recorded for this academic period.
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-xs font-mono uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                <FiClock className="text-amber-400" /> Applied Scholarship Applications
              </h4>
              <span className="text-xs text-gray-400">
                Source application records
              </span>
            </div>

            {applied && applied.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {applied.map((app, idx) => (
                  <div 
                    key={idx}
                    className="p-5 rounded-xl bg-[#151926] border border-[#212638] flex flex-col justify-between hover:border-amber-500/30 transition-colors"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-amber-500/10 border border-amber-500/30 text-amber-400">
                          Status: {app.application_status || 'Applied'}
                        </span>
                        <span className="text-xs font-mono text-gray-400">
                          AY: {app.year || 'N/A'}
                        </span>
                      </div>
                      <h5 className="text-sm font-bold text-gray-200 mb-2">
                        {app.scheme_name || 'Scholarship Scheme'}
                      </h5>
                      <div className="text-xs text-gray-400 font-mono space-y-1 mb-2">
                        {app.scholarship_id && (
                          <div>Scheme ID: <span className="text-purple-300 font-semibold">{app.scholarship_id}</span></div>
                        )}
                        {app.tutor_approval && (
                          <div>Tutor Verification: <span className="text-gray-300">{app.tutor_approval}</span></div>
                        )}
                      </div>
                    </div>

                    <div className="pt-3 border-t border-[#1e2333] flex items-center justify-between">
                      <span className="text-xs text-gray-400 font-mono">Applied Amount</span>
                      <span className="text-lg font-bold font-mono text-amber-400">
                        ₹ {app.amount ? app.amount.toLocaleString('en-IN') : 'N/A'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-gray-400 bg-[#151926] rounded-xl border border-[#212638]">
                No pending or applied scholarship records on file.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Neutral Policy Banner */}
      <div className="bg-[#0e111a] border-t border-[#1e2333] px-6 py-3 flex items-center justify-between text-xs text-gray-400">
        <span className="flex items-center gap-1.5 text-gray-400">
          <FiInfo className="text-purple-400 text-sm flex-shrink-0" /> Reflects raw StudZone portal status. Student Sync does not infer or predict scholarship approval.
        </span>
        <span className="font-mono text-[11px] text-gray-400">
          Source: StudZone 1 Welfare
        </span>
      </div>
    </div>
  );
};

export default ScholarshipSummary;
