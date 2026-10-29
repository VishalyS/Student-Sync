import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { FiCheckCircle, FiArrowRight, FiMail, FiRefreshCw, FiEdit3, FiCheck, FiAlertCircle } from 'react-icons/fi';

const ThankYou = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const rollNo = location.state?.rollNo;
  const initialEmail = location.state?.email || (rollNo ? `${rollNo.toLowerCase()}@psgtech.ac.in` : '');

  const [currentEmail, setCurrentEmail] = useState(initialEmail);
  const [customEmail, setCustomEmail] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);

  const handleResend = async (emailToUse) => {
    if (!rollNo) return;
    setIsSending(true);
    setStatusMessage(null);
    try {
      const response = await fetch('/api/resend-welcome', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rollNo: rollNo,
          email: emailToUse || currentEmail
        })
      });
      const data = await response.json();
      if (response.ok) {
        const confirmedEmail = data.email || emailToUse || currentEmail;
        setCurrentEmail(confirmedEmail);
        setStatusMessage({
          type: 'success',
          text: `Welcome mail successfully delivered to ${confirmedEmail}!`
        });
        setShowCustomInput(false);
        setCustomEmail('');
      } else {
        setStatusMessage({
          type: 'error',
          text: data.error || 'Failed to dispatch welcome email. Please try again.'
        });
      }
    } catch (err) {
      setStatusMessage({
        type: 'error',
        text: 'Network connection failed while contacting mail server.'
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] flex flex-col justify-center items-center px-4 pt-20 pb-12">
      <div className="w-full max-w-md">
        
        <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 sm:p-8 text-center shadow-md space-y-6">
          <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto text-2xl">
            <FiCheckCircle />
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight text-white">Welcome to Student Sync 🎓</h1>
            <p className="text-xs text-gray-400 leading-relaxed">
              Your PSG Tech student account {rollNo ? <span className="font-mono text-purple-300 font-semibold">{rollNo}</span> : ''} is now linked and synchronized.
            </p>
          </div>

          {/* Email Confirmation Card */}
          <div className="p-4 rounded-lg bg-[#181c2b] border border-[#262c3e] text-left space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-semibold text-purple-300">
                <FiMail className="text-sm flex-shrink-0" />
                <span>Welcome Mail Dispatched</span>
              </div>
              <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-medium">
                Sent
              </span>
            </div>

            <p className="text-[12px] text-gray-300 leading-relaxed">
              We sent your onboarding guide and monitoring summary to:{' '}
              <span className="block mt-1 font-mono text-white text-xs bg-[#0f121d] px-2.5 py-1.5 rounded border border-[#23283a] break-all">
                {currentEmail || (rollNo ? `${rollNo.toLowerCase()}@psgtech.ac.in` : 'Registered student email')}
              </span>
            </p>

            <p className="text-[11px] text-gray-400">
              💡 <em>Note: If you don't see it in your Inbox, please check your <strong>Spam</strong> or <strong>Junk</strong> folder.</em>
            </p>

            {statusMessage && (
              <div className={`p-2.5 rounded text-xs flex items-center gap-2 ${
                statusMessage.type === 'success' 
                  ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300' 
                  : 'bg-red-500/10 border border-red-500/20 text-red-400'
              }`}>
                {statusMessage.type === 'success' ? <FiCheck className="text-sm flex-shrink-0" /> : <FiAlertCircle className="text-sm flex-shrink-0" />}
                <span>{statusMessage.text}</span>
              </div>
            )}

            {/* Custom Email Input or Actions */}
            {showCustomInput ? (
              <div className="pt-2 border-t border-[#23283a] space-y-2">
                <label className="text-[11px] font-medium text-gray-300 block">
                  Send welcome mail to a different address (e.g. personal Gmail):
                </label>
                <div className="flex gap-2">
                  <input
                    type="email"
                    value={customEmail}
                    onChange={(e) => setCustomEmail(e.target.value)}
                    placeholder="e.g. yourname@gmail.com"
                    className="flex-1 px-2.5 py-1.5 bg-[#0b0d13] border border-[#2e344a] rounded text-xs text-white placeholder:text-gray-600 focus:border-purple-500 focus:outline-none"
                  />
                  <button
                    onClick={() => handleResend(customEmail)}
                    disabled={isSending || !customEmail || !customEmail.includes('@')}
                    className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors"
                  >
                    {isSending ? 'Sending...' : 'Send'}
                  </button>
                  <button
                    onClick={() => setShowCustomInput(false)}
                    className="px-2 py-1.5 bg-[#23283a] hover:bg-[#2e344a] text-gray-400 rounded text-xs transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="pt-2 border-t border-[#23283a] flex items-center justify-between text-xs">
                <button
                  onClick={() => handleResend(currentEmail)}
                  disabled={isSending}
                  className="text-purple-400 hover:text-purple-300 flex items-center gap-1.5 disabled:opacity-50 transition-colors"
                >
                  <FiRefreshCw className={`text-xs ${isSending ? 'animate-spin' : ''}`} />
                  <span>{isSending ? 'Resending...' : 'Resend Email'}</span>
                </button>
                <button
                  onClick={() => setShowCustomInput(true)}
                  className="text-gray-400 hover:text-gray-200 flex items-center gap-1 transition-colors"
                >
                  <FiEdit3 className="text-xs" />
                  <span>Send to personal Gmail</span>
                </button>
              </div>
            )}
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
