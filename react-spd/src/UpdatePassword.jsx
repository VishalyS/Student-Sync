import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FiLock, FiEye, FiEyeOff, FiAlertCircle, FiCheckCircle } from 'react-icons/fi';

const UpdatePassword = () => {
  const { rollNo } = useParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleUpdatePassword = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (!password.trim()) {
      setError('Please enter a valid password');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch('/api/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rollno: rollNo, password: password }),
      });

      const responseData = await response.json();

      if (response.status === 200) {
        setSuccess(responseData.message || 'Password updated successfully!');
        setTimeout(() => {
          navigate('/login');
        }, 1500);
      } else {
        setError(responseData.message || 'Failed to update password.');
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
          <p className="text-xs text-gray-400 mt-1 font-mono">Roll Number: {rollNo}</p>
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