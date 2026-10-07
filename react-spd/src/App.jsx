import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './Login';
import Registration from './temp';
import ThankYou from './ThankYou';
import Welcome from './Welcome';
import Dashboard from './Dashboard';
import Home from "./Home";
import Navbar from './components/Navbar';
import About from './About';
import Contact from './Contact';
import UpdatePassword from './UpdatePassword';
import AttendanceDashboard from './AttendanceDashboard';
import AcademicPlannerDashboard from './AcademicPlannerDashboard';
import ScheduleDashboard from './ScheduleDashboard';
import PersonalizedPlannerDashboard from './PersonalizedPlannerDashboard';
import CampusServicesDashboard from './CampusServicesDashboard';

function App() {
  return (
    <Router>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Registration />} />
        <Route path="/thank-you" element={<ThankYou />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/profile" element={<Dashboard />} />
        <Route path="/attendance" element={<AttendanceDashboard />} />
        <Route path="/grades" element={<AcademicPlannerDashboard />} />
        <Route path="/schedule" element={<ScheduleDashboard />} />
        <Route path="/planner" element={<PersonalizedPlannerDashboard />} />
        <Route path="/services" element={<CampusServicesDashboard />} />
        <Route path="/welcome" element={<Welcome />} />
        <Route path="/about" element={<About />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/update/:rollNo" element={<UpdatePassword />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
