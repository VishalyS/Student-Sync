import React from 'react';
import { 
  FiHome, 
  FiCheckCircle, 
  FiFileText, 
  FiCalendar, 
  FiDollarSign, 
  FiInfo, 
  FiTag 
} from 'react-icons/fi';

const HostelStatusCard = ({ hostel }) => {
  if (!hostel) {
    return (
      <div className="bg-[#121520] border border-[#1e2333] rounded-2xl p-6 text-center text-gray-400">
        <FiHome className="mx-auto text-3xl mb-2 text-gray-500" />
        <p>No hostel accommodation record available.</p>
      </div>
    );
  }

  const {
    status,
    is_hosteller,
    resident_type,
    room_number,
    payment_count,
    total_paid,
    payments
  } = hostel;

  return (
    <div className="bg-[#121520] border border-[#1e2333] rounded-2xl overflow-hidden shadow-xl">
      {/* Header Banner */}
      <div className="p-6 sm:p-8 border-b border-[#1e2333] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <FiHome className="text-cyan-400" /> Hostel & Accommodation
            </h3>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
              is_hosteller 
                ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400' 
                : 'bg-gray-500/10 border-gray-500/30 text-gray-400'
            }`}>
              {resident_type || (is_hosteller ? 'Hosteller' : 'Day Scholar')}
            </span>
          </div>
          <p className="text-sm text-gray-400">
            Campus residency details, allocated room, and hostel fee transactions.
          </p>
        </div>

        {/* Accommodation Status Chips */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="px-4 py-2 rounded-xl bg-[#161a27] border border-[#23293e] text-xs">
            <span className="text-gray-400 block text-[10px] uppercase font-mono tracking-wider">Allocated Room</span>
            <span className="text-cyan-300 font-bold font-mono text-sm">
              {room_number && room_number !== 'N/A' ? room_number : (is_hosteller ? 'Assigned' : 'N/A (Day Scholar)')}
            </span>
          </div>
          {is_hosteller && total_paid > 0 && (
            <div className="px-4 py-2 rounded-xl bg-[#161a27] border border-[#23293e] text-xs">
              <span className="text-gray-400 block text-[10px] uppercase font-mono tracking-wider">Total Paid</span>
              <span className="text-emerald-400 font-bold font-mono text-sm">
                ₹ {total_paid.toLocaleString('en-IN')}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="p-6 sm:p-8">
        {!is_hosteller ? (
          <div className="py-8 px-4 text-center rounded-xl bg-[#151926] border border-[#212638]">
            <FiHome className="mx-auto text-3xl text-gray-500 mb-2" />
            <h4 className="text-base font-semibold text-gray-300 mb-1">Day Scholar Status</h4>
            <p className="text-xs text-gray-400 max-w-md mx-auto">
              Student is recorded as a Day Scholar in the institutional registry. No hostel accommodation or mess charges apply.
            </p>
          </div>
        ) : (
          <div>
            <h4 className="text-xs font-mono uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-1.5">
              <FiFileText className="text-cyan-400" /> Accommodation Transaction History ({payment_count})
            </h4>

            {payments && payments.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {payments.map((p, idx) => (
                  <div 
                    key={idx} 
                    className="p-5 rounded-xl bg-[#151926] border border-[#212638] flex flex-col justify-between hover:border-cyan-500/30 transition-colors"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                          <FiCheckCircle className="text-[11px]" /> {p.status || 'Success'}
                        </span>
                        <span className="text-xs text-gray-400 font-mono flex items-center gap-1">
                          <FiCalendar className="text-xs" /> {p.date || 'N/A'}
                        </span>
                      </div>
                      <div className="text-xl font-bold font-mono text-white mb-1">
                        ₹ {p.amount?.toLocaleString('en-IN')}
                      </div>
                      <div className="text-xs text-gray-400 font-mono">
                        Receipt / Txn ID: <span className="text-cyan-300 font-semibold">{p.receipt_id}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-gray-400 bg-[#151926] rounded-xl border border-[#212638]">
                Hostel registered, but no transaction records are currently published.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="bg-[#0e111a] border-t border-[#1e2333] px-6 py-3 flex items-center justify-between text-xs text-gray-400">
        <span className="flex items-center gap-1.5 text-gray-400">
          <FiInfo className="text-cyan-400 text-sm" /> Official PSG Tech Hostel Office Record.
        </span>
        <span className="font-mono text-[11px] text-gray-400">
          Status: {status}
        </span>
      </div>
    </div>
  );
};

export default HostelStatusCard;
