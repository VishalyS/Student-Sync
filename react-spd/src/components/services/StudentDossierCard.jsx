import React from 'react';
import { 
  FiUser, 
  FiAward, 
  FiHome, 
  FiMail, 
  FiPhone, 
  FiCalendar, 
  FiShield, 
  FiCheckCircle,
  FiBookOpen
} from 'react-icons/fi';

const StudentDossierCard = ({ dossier }) => {
  if (!dossier || Object.keys(dossier).length === 0) {
    return (
      <div className="bg-[#121520] border border-[#1e2333] rounded-2xl p-6 text-center text-gray-400">
        <FiUser className="mx-auto text-3xl mb-2 text-gray-500" />
        <p>Student dossier records are not available from the institutional record.</p>
      </div>
    );
  }

  const {
    rollNo,
    name,
    degree,
    institution,
    semester,
    admission_type,
    resident_status,
    room_number,
    email,
    mobile,
    dob
  } = dossier;

  return (
    <div className="bg-[#121520] border border-[#1e2333] rounded-2xl overflow-hidden shadow-xl">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-purple-900/40 via-indigo-900/30 to-blue-900/20 border-b border-[#1e2333] p-6 sm:p-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start sm:items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400 shadow-inner flex-shrink-0">
            <FiUser className="text-3xl" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                {name || 'Student Record'}
              </h2>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                <FiCheckCircle className="text-[11px]" /> Verified Student Record
              </span>
            </div>
            <p className="text-sm text-gray-400 font-mono">
              Roll No: <span className="text-purple-300 font-semibold">{rollNo || 'N/A'}</span> • {degree || 'Degree Program'}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {institution || 'PSG College of Technology'}
            </p>
          </div>
        </div>

        {/* Quick Highlights */}
        <div className="flex flex-wrap gap-2.5 md:self-center">
          {semester && (
            <div className="px-3 py-1.5 rounded-xl bg-[#171b29] border border-[#23283c] text-xs">
              <span className="text-gray-400 block text-[10px] uppercase font-mono tracking-wider">Semester</span>
              <span className="text-white font-bold">{semester}</span>
            </div>
          )}
          {resident_status && (
            <div className="px-3 py-1.5 rounded-xl bg-[#171b29] border border-[#23283c] text-xs">
              <span className="text-gray-400 block text-[10px] uppercase font-mono tracking-wider">Resident Type</span>
              <span className="text-cyan-400 font-bold">{resident_status}</span>
            </div>
          )}
          {room_number && room_number !== 'N/A' && (
            <div className="px-3 py-1.5 rounded-xl bg-[#171b29] border border-[#23283c] text-xs">
              <span className="text-gray-400 block text-[10px] uppercase font-mono tracking-wider">Room No</span>
              <span className="text-purple-300 font-bold">{room_number}</span>
            </div>
          )}
        </div>
      </div>

      {/* Grid of Verified Identity Attributes */}
      <div className="p-6 sm:p-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Degree & Program */}
        <div className="p-4 rounded-xl bg-[#151926] border border-[#212638] flex items-start gap-3">
          <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 mt-0.5">
            <FiBookOpen className="text-base" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-mono text-gray-400 uppercase tracking-wider">Program & Degree</div>
            <div className="text-sm font-semibold text-gray-200 mt-0.5 break-words">
              {degree || 'Not available from institutional record.'}
            </div>
          </div>
        </div>

        {/* Admission Type */}
        <div className="p-4 rounded-xl bg-[#151926] border border-[#212638] flex items-start gap-3">
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 mt-0.5">
            <FiAward className="text-base" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-mono text-gray-400 uppercase tracking-wider">Admission Quota / Type</div>
            <div className="text-sm font-semibold text-gray-200 mt-0.5">
              {admission_type || 'Merit / Institutional'}
            </div>
          </div>
        </div>

        {/* Hostel & Room */}
        <div className="p-4 rounded-xl bg-[#151926] border border-[#212638] flex items-start gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 mt-0.5">
            <FiHome className="text-base" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-mono text-gray-400 uppercase tracking-wider">Campus Accommodation</div>
            <div className="text-sm font-semibold text-gray-200 mt-0.5">
              {resident_status === 'HOSTELLER' ? `Hostel (Room ${room_number || 'Assigned'})` : 'Day Scholar'}
            </div>
          </div>
        </div>

        {/* Official Email */}
        <div className="p-4 rounded-xl bg-[#151926] border border-[#212638] flex items-start gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 mt-0.5">
            <FiMail className="text-base" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-mono text-gray-400 uppercase tracking-wider">Campus Email</div>
            <div className="text-sm font-semibold text-gray-200 mt-0.5 truncate" title={email}>
              {email || 'Not available from institutional record.'}
            </div>
          </div>
        </div>

        {/* Mobile Contact */}
        <div className="p-4 rounded-xl bg-[#151926] border border-[#212638] flex items-start gap-3">
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 mt-0.5">
            <FiPhone className="text-base" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-mono text-gray-400 uppercase tracking-wider">Verified Contact</div>
            <div className="text-sm font-semibold text-gray-200 mt-0.5 font-mono">
              {mobile || 'Not available from institutional record.'}
            </div>
          </div>
        </div>

        {/* Date of Birth */}
        <div className="p-4 rounded-xl bg-[#151926] border border-[#212638] flex items-start gap-3">
          <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 mt-0.5">
            <FiCalendar className="text-base" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-mono text-gray-400 uppercase tracking-wider">Date of Birth</div>
            <div className="text-sm font-semibold text-gray-200 mt-0.5 font-mono">
              {dob || 'Not available from institutional record.'}
            </div>
          </div>
        </div>
      </div>

      {/* Security & Authenticity Footer */}
      <div className="bg-[#0e111a] border-t border-[#1e2333] px-6 py-3 flex items-center justify-between text-xs text-gray-400">
        <span className="flex items-center gap-1.5">
          <FiShield className="text-emerald-400 text-sm" /> Read-only institutional dossier authenticated via StudZone session.
        </span>
        <span className="font-mono text-[11px] hidden sm:inline text-gray-400">
          Source: StudZone 1 Portal
        </span>
      </div>
    </div>
  );
};

export default StudentDossierCard;
