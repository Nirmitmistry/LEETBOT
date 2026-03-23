import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Sidebar.css';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Generate initials for avatar
  const initials = user?.username
    ? user.username.substring(0, 2).toUpperCase()
    : user?.email?.substring(0, 2).toUpperCase() || 'U';

  return (
    <div className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16.102 17.93l-2.697 2.607c-.466.467-1.111.662-1.823.662s-1.357-.195-1.824-.662l-4.332-4.363c-.467-.467-.702-1.15-.702-1.863s.235-1.357.702-1.824l4.319-4.38c.467-.467 1.125-.645 1.837-.645s1.357.195 1.823.662l2.697 2.606c.514.515 1.365.497 1.9-.038.535-.536.553-1.387.038-1.901l-2.609-2.636a5.055 5.055 0 00-3.849-1.593 5.073 5.073 0 00-3.849 1.593l-4.306 4.38C1.112 12.97.9 13.627.9 14.337s.195 1.394.662 1.86l4.332 4.364c1.07 1.07 2.496 1.593 3.849 1.593s2.779-.523 3.849-1.593l2.697-2.607c.514-.514.496-1.365-.039-1.9s-1.386-.553-1.9-.039l-.248-.085z" fill="#FFA116" />
            <path d="M20.437 11.662l-4.332-4.363c-1.07-1.07-2.496-1.593-3.849-1.593s-2.779.523-3.849 1.593L5.71 9.906c-.515.514-.497 1.365.038 1.9s1.387.553 1.9.038l2.697-2.607c.467-.467 1.111-.662 1.823-.662s1.357.195 1.824.662l4.332 4.363c.467.467.702 1.15.702 1.863s-.235 1.357-.702 1.824l-4.319 4.38c-.467.467-1.125.645-1.837.645s-1.357-.195-1.823-.662l-2.697-2.606c-.514-.515-1.365-.497-1.9.038-.536.536-.553 1.387-.039 1.901l2.609 2.636a5.055 5.055 0 003.849 1.593 5.073 5.073 0 003.849-1.593l4.306-4.38c.467-.466.679-1.122.679-1.832s-.195-1.394-.662-1.86z" fill="#B3B3B3" />
          </svg>
        </div>
        <span className="sidebar-brand-text">LeetBot</span>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <NavLink to="/dashboard" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="9"></rect>
            <rect x="14" y="3" width="7" height="5"></rect>
            <rect x="14" y="12" width="7" height="9"></rect>
            <rect x="3" y="16" width="7" height="5"></rect>
          </svg>
          Dashboard
        </NavLink>

        <NavLink to="/chat" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          Chat Assistant
        </NavLink>

        <NavLink to="/problems" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="16 18 22 12 16 6"></polyline>
            <polyline points="8 6 2 12 8 18"></polyline>
          </svg>
          Problems
        </NavLink>
      </nav>

      <div className="sidebar-spacer"></div>

      {/* User Section */}
      <div className="sidebar-user">
        <div className="user-profile">
          <div className="user-avatar">{initials}</div>
          <div className="user-info">
            <span className="user-name">{user?.username || 'User'}</span>
            <span className="user-email">{user?.email || ''}</span>
          </div>
        </div>
        <button onClick={handleLogout} className="logout-btn" title="Log Out">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
        </button>
      </div>
    </div>
  );
}
