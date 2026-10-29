import React, { useState } from 'react';
import { FiMail, FiSend, FiAlertCircle, FiCheckCircle } from 'react-icons/fi';

const Contact = () => {
  const [formData, setFormData] = useState({ name: '', email: '', message: '' });
  const [status, setStatus] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: '', text: '' });
    setLoading(true);

    try {
      const response = await fetch('/api/send-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      const result = await response.json();
      if (response.ok) {
        setStatus({ type: 'success', text: result.message || 'Message sent successfully.' });
        setFormData({ name: '', email: '', message: '' });
      } else {
        setStatus({ type: 'error', text: result.message || 'Failed to send message.' });
      }
    } catch (error) {
      setStatus({ type: 'error', text: 'Could not connect to the server.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] flex flex-col justify-center items-center px-4 pt-24 pb-16">
      <div className="w-full max-w-md">
        
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-white">Get in Touch</h1>
          <p className="text-sm text-gray-400 mt-1">Have questions or feedback? Send us a message.</p>
        </div>

        {/* Contact Form Card */}
        <div className="bg-[#131620] border border-[#232738] rounded-xl p-6 sm:p-8 shadow-md">
          {status.text && (
            <div className={`flex items-start gap-2.5 p-3.5 mb-5 rounded-lg text-xs ${
              status.type === 'success' 
                ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' 
                : 'bg-red-500/10 border border-red-500/20 text-red-400'
            }`}>
              {status.type === 'success' ? (
                <FiCheckCircle className="text-sm flex-shrink-0 mt-0.5" />
              ) : (
                <FiAlertCircle className="text-sm flex-shrink-0 mt-0.5" />
              )}
              <span>{status.text}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-xs font-medium text-gray-300 mb-1.5">
                Your Name
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="Enter your name"
                className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
                required
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-xs font-medium text-gray-300 mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="you@psgtech.ac.in"
                className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
                required
              />
            </div>

            <div>
              <label htmlFor="message" className="block text-xs font-medium text-gray-300 mb-1.5">
                Message
              </label>
              <textarea
                id="message"
                name="message"
                rows="4"
                value={formData.message}
                onChange={handleChange}
                placeholder="How can we help?"
                className="w-full px-3.5 py-2.5 bg-[#0b0d13] border border-[#272c3d] rounded-lg text-sm text-white placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
                required
              />
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
                  <FiSend className="text-sm" />
                  <span>Send Message</span>
                </>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-500 mt-6">
          Direct email: <a href="mailto:student.sync12@gmail.com" className="text-purple-400 hover:text-purple-300">student.sync12@gmail.com</a>
        </p>

      </div>
    </div>
  );
};

export default Contact;
