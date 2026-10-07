import React from 'react';
import { FiGithub, FiLinkedin, FiMail } from 'react-icons/fi';

const AboutUs = () => {
  const developers = [
    {
      name: "Vishaly S",
      role: "Developer",
    },
    {
      name: "Miruna M V",
      role: "Developer",
    }
  ];

  return (
    <div className="min-h-screen bg-[#0b0d13] text-[#f3f4f6] px-4 sm:px-6 lg:px-8 pt-32 pb-20">
      <div className="max-w-4xl mx-auto space-y-16">
        
        {/* About Section */}
        <div className="text-center space-y-4 max-w-2xl mx-auto">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white">
            About Student Sync
          </h1>
          <p className="text-sm sm:text-base text-gray-400 font-normal leading-relaxed">
            Student Sync brings important academic information together in one place and helps students stay informed about attendance, marks, examinations, and academic updates.
          </p>
        </div>

        {/* Team Section */}
        <div className="space-y-8">
          <div className="text-center space-y-1.5">
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Meet Our Team
            </h2>
            <p className="text-xs sm:text-sm text-gray-400">
              The developers behind Student Sync
            </p>
          </div>

          {/* Centered 2-Developer Card Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 max-w-2xl mx-auto">
            {developers.map((dev) => (
              <div 
                key={dev.name}
                className="bg-[#131620] border border-[#232738] rounded-xl p-6 sm:p-8 text-center space-y-4 hover:border-[#333a4f] transition-all shadow-sm"
              >
                <div className="w-16 h-16 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 font-bold text-xl flex items-center justify-center mx-auto">
                  {dev.name.charAt(0)}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white tracking-tight">{dev.name}</h3>
                  <p className="text-xs font-medium text-purple-400 mt-0.5">{dev.role}</p>
                </div>

                {/* Social Placeholders (Visual Only) */}
                <div className="flex justify-center items-center gap-3 pt-2">
                  <div 
                    className="w-8 h-8 rounded-lg bg-[#1a1e2c] border border-[#272d3e] flex items-center justify-center text-gray-400 hover:text-white cursor-default select-none transition-colors"
                    title="GitHub"
                  >
                    <FiGithub size={14} />
                  </div>
                  <div 
                    className="w-8 h-8 rounded-lg bg-[#1a1e2c] border border-[#272d3e] flex items-center justify-center text-gray-400 hover:text-white cursor-default select-none transition-colors"
                    title="LinkedIn"
                  >
                    <FiLinkedin size={14} />
                  </div>
                  <div 
                    className="w-8 h-8 rounded-lg bg-[#1a1e2c] border border-[#272d3e] flex items-center justify-center text-gray-400 hover:text-white cursor-default select-none transition-colors"
                    title="Email"
                  >
                    <FiMail size={14} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Contact Note */}
        <div className="pt-8 border-t border-[#1c202e] text-center text-xs text-gray-500 space-y-1">
          <p>For inquiries or suggestions, contact:</p>
          <a href="mailto:student.sync12@gmail.com" className="text-purple-400 hover:text-purple-300 font-medium">
            student.sync12@gmail.com
          </a>
          <p className="pt-4 text-gray-600">© 2026 Student Sync | All rights reserved.</p>
        </div>

      </div>
    </div>
  );
};

export default AboutUs;
