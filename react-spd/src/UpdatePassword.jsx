import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { FiLock, FiEye, FiEyeOff, FiAlertCircle, FiCheckCircle, FiKey, FiMail } from 'react-icons/fi';

const UpdatePassword = () => {
  const { rollNo } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [verificationCode, setVerificationCode] = useState(searchParams.get('otp') || searchParams.get('token') || '');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [sendingOtp, setSendingOtp] = useState(false);
  const [otpSent, setOtpSent] = useState(false);

  // Check if student is already logged in with valid token
  const storedUser = React.useMemo(() => {
    try {
      const raw = localStorage.getItem('student_sync_user');
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }, []);

  const isCurrentStudentLoggedIn = storedUser && storedUser.rollNo?.toUpperCase() === rollNo?.toUpperCase() && storedUser.auth_token;

  const handleRequestOtp = async () => {
    setError('');
    setSuccess('');
    setSendingOtp(true);
    try {
      const resp = await fetch('/api/request-reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rollNo: rollNo?.toUpperCase() }),
      });
      const data = await resp.json();
      if (resp.status === 200) {
        setOtpSent(true);
        setSuccess(data.message || 'Verification code sent to your registered college email.');
        if (data.otp) {
          // In test/dev mode
          setVerificationCode(data.otp);
        }
      } else {
        setError(data.message || 'Failed to send verification code.');
      }
    } catch (err) {
      setError('Could not connect to the server to send verification code.');
    } finally {
      setSendingOtp(false);
    }
  };

  const handleUpdatePassword = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (!password.trim()) {
      setError('Please enter a valid new password');
      return;
    }

    if (!isCurrentStudentLoggedIn && !verificationCode.trim()) {
      setError('Please enter the 6-digit verification code sent to your email.');
      return;
    }

    try {
      setLoading(true);
      const headers = { 'Content-Type': 'application/json' };
      if (isCurrentStudentLoggedIn) {
        headers['Authorization'] = `Bearer ${storedUser.auth_token}`;
      }

      const payload = {
        rollno: rollNo?.toUpperCase(),
        password: password.trim(),
        current_password: currentPassword.trim() || undefined,
        otp: verificationCode.trim() || undefined,
        reset_token: verificationCode.trim() || undefined
      };

      const response = await fetch('/api/update', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      const responseData = await response.json();

      if (response.status === 200) {
        setSuccess(responseData.message || 'Password updated successfully!');
        setTimeout(() => {
          navigate('/login');
        }, 1500);
      } else {
        setError(responseData.message || responseData.detail || 'Failed to update password.');
      }
    } catch (err) {
      console.error('Error during password update:', err);
      setError('Could not connect to the server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] flex flex-col justify-center items-center px-4 pt-20 pb-12">
      <div className="w-full max-w-sm">
        
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-white">Update Password</h1>
          <p className="text-xs text-gray-400 mt-1 font-mono">Roll Number: {rollNo?.toUpperCase()}</p>
          {isCurrentStudentLoggedIn ? (
            <span className="inline-block mt-2 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Authenticated Session
            </span>
          ) : (
            <span className="inline-block mt-2 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
              Account Recovery
            </span>
          )}
        </div>

        {/* Form Card */}
        <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 sm:p-8 shadow-md">
          {error && (
            <div className="flex items-start gap-2.5 p-3.5 mb-5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
              <FiAlertCircle className="text-sm flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-start gap-2.5 p-3.5 mb-5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs">
              <FiCheckCircle className="text-sm flex-shrink-0 mt-0.5" />
              <span>{success}</span>
            </div>
          )}

          <form onSubmit={handleUpdatePassword} className="space-y-4">
            
            {/* If logged in: optional current password verification */}
            {isCurrentStudentLoggedIn ? (
              <div>
                <label htmlFor="currentPassword" className="block text-xs font-medium text-gray-300 mb-1.5">
                  Current StudZone Password (Optional)
                </label>
                <input
                  type="password"
                  id="currentPassword"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="Enter current password"
                  className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
                />
              </div>
            ) : (
              /* If logged out: require OTP or reset token */
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label htmlFor="verificationCode" className="block text-xs font-medium text-gray-300">
                    6-Digit Verification Code / OTP
                  </label>
                  <button
                    type="button"
                    onClick={handleRequestOtp}
                    disabled={sendingOtp}
                    className="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1 disabled:opacity-50"
                  >
                    <FiMail size={12} />
                    <span>{sendingOtp ? 'Sending...' : (otpSent ? 'Resend Code' : 'Send Code to Email')}</span>
                  </button>
                </div>
                <div className="relative">
                  <input
                    type="text"
                    id="verificationCode"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder="Enter code from college inbox"
                    className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 font-mono tracking-wider transition-colors"
                    required
                  />
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-gray-500">
                    <FiKey size={14} />
                  </div>
                </div>
              </div>
            )}

            <div>
              <label htmlFor="password" className="block text-xs font-medium text-gray-300 mb-1.5">
                New StudZone Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter updated portal password"
                  className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 pr-10 transition-colors"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-gray-300"
                  tabIndex={-1}
                >
                  {showPassword ? <FiEyeOff size={16} /> : <FiEye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 mt-2 rounded-lg bg-white hover:bg-gray-100 text-gray-950 font-semibold text-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-gray-950 border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <FiLock className="text-sm" />
                  <span>Update Password</span>
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-[#1f2333] text-center text-xs text-gray-400">
            <button
              onClick={() => navigate('/login')}
              className="text-purple-400 hover:text-purple-300 font-medium"
            >
              ← Back to Login
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};

export default UpdatePassword;