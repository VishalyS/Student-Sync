import React, { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { FiUserPlus, FiEye, FiEyeOff, FiAlertCircle, FiInfo } from 'react-icons/fi';

const Registration = () => {
  const [rollNo, setRollNo] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const submissionInProgress = useRef(false);
  const lastSubmissionTime = useRef(0);
  const abortControllerRef = useRef(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    const now = Date.now();
    if (loading || submissionInProgress.current || (now - lastSubmissionTime.current < 2000)) {
      return;
    }

    try {
      setLoading(true);
      submissionInProgress.current = true;
      lastSubmissionTime.current = now;
      
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();
      
      const payload = {
        rollNo: rollNo.trim().toUpperCase(),
        password: password.trim()
      };
      if (email.trim()) {
        payload.email = email.trim();
      }

      const response = await fetch('http://127.0.0.1:5000/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: abortControllerRef.current.signal,
      });

      const data = await response.json();

      if (response.status === 200 || response.status === 201) {
        const confirmedEmail = data.email || (email.trim() || `${rollNo.trim().toLowerCase()}@psgtech.ac.in`);
        navigate('/thank-you', {
          state: {
            rollNo: rollNo.trim().toUpperCase(),
            email: confirmedEmail
          }
        });
      } else if (response.status === 401) {
        setError('Invalid credentials. Please check your roll number and StudZone password.');
      } else if (response.status === 409) {
        setError(data.detail || data.message || 'Already registered. Please Login.');
      } else {
        setError(data.message || 'Registration failed. Please check your information and try again.');
      }
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.error('Error during registration:', err);
      setError('Unable to connect to the Student Sync server. Please ensure the backend is running.');
    } finally {
      setLoading(false);
      submissionInProgress.current = false;
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] flex flex-col justify-center items-center px-4 pt-20 pb-12">
      <div className="w-full max-w-sm">
        
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-white">Create Account</h1>
          <p className="text-sm text-gray-400 mt-1">Connect your PSG Tech student portal</p>
        </div>

        {/* Registration Card */}
        <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 sm:p-8 shadow-md">
          {error && (
            <div className="flex items-start gap-2.5 p-3.5 mb-5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
              <FiAlertCircle className="text-sm flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="rollNo" className="block text-xs font-medium text-gray-300 mb-1.5">
                Roll Number
              </label>
              <input
                type="text"
                id="rollNo"
                value={rollNo}
                onChange={(e) => setRollNo(e.target.value.toUpperCase())}
                placeholder="e.g. 25MX232"
                className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-medium text-gray-300 mb-1.5">
                StudZone Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your StudZone password"
                  className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 pr-10 transition-colors"
                  required
                  disabled={loading}
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

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="email" className="block text-xs font-medium text-gray-300">
                  Notification Email <span className="text-gray-500 font-normal">(Optional)</span>
                </label>
              </div>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. personal Gmail or college email"
                className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
                disabled={loading}
              />
              <p className="text-[11px] text-gray-500 mt-1">
                Your welcome email and portal change alerts will be sent here. Defaults to {rollNo ? `${rollNo.toLowerCase()}@psgtech.ac.in` : 'your college email'}.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-[#181c2b] border border-[#262c3e] text-xs text-gray-400 flex items-start gap-2">
              <FiInfo className="text-purple-400 text-sm flex-shrink-0 mt-0.5" />
              <span>Use your regular student StudZone password. Student Sync will automatically sync your academic record.</span>
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
                  <FiUserPlus className="text-sm" />
                  <span>Register Account</span>
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-[#1f2333] text-center text-xs text-gray-400">
            Already have an account?{' '}
            <Link to="/login" className="text-purple-400 hover:text-purple-300 font-medium">
              Login
            </Link>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Registration;
