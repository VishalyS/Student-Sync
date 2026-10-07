import React from 'react';
import { 
  FiFileText, 
  FiExternalLink, 
  FiDownload, 
  FiShield, 
  FiInfo 
} from 'react-icons/fi';

const CircularsViewer = ({ circulars = [] }) => {
  if (!circulars || circulars.length === 0) {
    return (
      <div className="py-16 text-center text-xs text-gray-500 rounded-xl bg-[#131620] border border-[#232738]">
        No examination circulars currently published on StudZone 2 records.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header Banner */}
      <div className="p-6 rounded-xl bg-[#131620] border border-[#232738] shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-white">Official Examination Circulars &amp; Guidelines</h2>
              <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono">
                Verified CoE Source
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Official institutional notifications, exam guidelines, and standard operating procedures
            </p>
          </div>
          <span className="text-xs font-mono text-purple-300 bg-purple-500/10 px-2.5 py-1 rounded-md border border-purple-500/20 self-start sm:self-auto">
            {circulars.length} Official Documents
          </span>
        </div>

        <div className="p-3 rounded-lg bg-[#171b28] border border-[#24293c] text-xs text-gray-400 flex items-start gap-2.5">
          <FiShield className="text-emerald-400 text-sm flex-shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="text-gray-200 font-semibold">Verified Source Integrity: </span>
            <span>
              All document URLs link directly to authorized Controller of Examinations PDF repositories hosted on 
              <code className="text-purple-300 bg-[#0f111a] px-1.5 py-0.5 rounded mx-1 font-mono">ecampus.psgtech.ac.in</code>.
            </span>
          </div>
        </div>
      </div>

      {/* Circular Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {circulars.map((item, idx) => (
          <div
            key={idx}
            className="p-5 rounded-xl bg-[#131620] border border-[#232738] hover:border-purple-500/40 transition-all flex flex-col justify-between space-y-4 group"
          >
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#181c2b] text-gray-400 border border-[#262c3e]">
                  Circular #{idx + 1}
                </span>
                <span className="text-[10px] text-emerald-400 font-mono flex items-center gap-1">
                  <FiFileText size={11} />
                  <span>PDF Document</span>
                </span>
              </div>

              <h3 className="text-xs font-bold text-white group-hover:text-purple-300 transition-colors leading-relaxed line-clamp-3">
                {item.title}
              </h3>
            </div>

            <div className="pt-3 border-t border-[#1c202e] flex items-center justify-between">
              <span className="text-[10px] font-mono text-gray-500">
                Official CoE Link
              </span>

              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600/15 hover:bg-purple-600 text-purple-300 hover:text-white border border-purple-500/30 text-xs font-semibold transition-all shadow-sm"
                >
                  <span>Open PDF</span>
                  <FiExternalLink size={12} />
                </a>
              ) : (
                <span className="text-xs text-gray-600 font-mono">Link unavailable</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CircularsViewer;
