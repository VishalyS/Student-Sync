import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { FiCheckCircle, FiArrowRight } from 'react-icons/fi';

const ThankYou = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] flex flex-col justify-center items-center px-4 pt-20 pb-12">
      <div className="w-full max-w-sm">
        
        <div className="bg-[#131620] border border-[#232738] rounded-xl p-8 text-center shadow-md space-y-6">
          <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto text-2xl">
            <FiCheckCircle />
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight text-white">Registration Complete</h1>
            <p className="text-xs text-gray-400 leading-relaxed">
              Your PSG Tech student account is now linked. You can log in to view your academic dashboard.
            </p>
          </div>

          <button
            onClick={() => navigate('/login')}
            className="w-full py-2.5 px-4 rounded-lg bg-white hover:bg-gray-100 text-gray-950 font-semibold text-sm transition-colors flex items-center justify-center gap-2"
          >
            <span>Proceed to Login</span>
            <FiArrowRight className="text-sm" />
          </button>
        </div>

      </div>
    </div>
  );
};

export default ThankYou;
