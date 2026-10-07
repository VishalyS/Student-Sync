import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { FiLogIn, FiEye, FiEyeOff, FiAlertCircle } from 'react-icons/fi';

const Login = () => {
  const [rollNo, setRollNo] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (event) => {
    event.preventDefault();
    setError('');

    try {
      setLoading(true);
      const response = await fetch('http://127.0.0.1:5000/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rollNo, password }),
      });

      if (response.status === 200) {
        const userData = await response.json();
        localStorage.setItem('student_sync_user', JSON.stringify(userData));
        navigate('/dashboard', { state: userData });
      } else if (response.status === 403) {
        const responseData = await response.json();
        if (responseData.needsPasswordUpdate && responseData.redirectUrl) {
          setError(responseData.message || 'Please update your password to continue.');
          setTimeout(() => {
            window.location.href = responseData.redirectUrl;
          }, 2000);
        } else {
          setError(responseData.message || 'Authentication required.');
        }
      } else {
        const errorData = await response.json();
        setError(errorData.message || 'Invalid credentials. Please check your roll number and password.');
      }
    } catch (err) {
      console.error('Error during login:', err);
      setError('Could not connect to the Student Sync backend server. Please ensure it is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] flex flex-col justify-center items-center px-4 pt-20 pb-12">
      <div className="w-full max-w-sm">
        
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-white">Sign In</h1>
          <p className="text-sm text-gray-400 mt-1">Access your Student Sync academic dashboard</p>
        </div>

        {/* Login Form Card */}
        <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 sm:p-8 shadow-md">
          {error && (
            <div className="flex items-start gap-2.5 p-3.5 mb-5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
              <FiAlertCircle className="text-sm flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
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
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label htmlFor="password" className="block text-xs font-medium text-gray-300">
                  StudZone Password
                </label>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter portal password"
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
                  <FiLogIn className="text-sm" />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-[#1f2333] text-center text-xs text-gray-400">
            Don't have an account?{' '}
            <Link to="/register" className="text-purple-400 hover:text-purple-300 font-medium">
              Create an account
            </Link>
          </div>
        </div>

        {/* Support link */}
        <p className="text-center text-xs text-gray-500 mt-6">
          Need help? <a href="mailto:student.sync12@gmail.com" className="text-gray-400 hover:text-gray-300 underline">Contact support</a>
        </p>

      </div>
    </div>
  );
};

export default Login;
