import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { getAllProblems } from '../api/problems';
import './Dashboard.css';

export default function Dashboard() {
  const { user, API } = useAuth();
  const [problems, setProblems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProblems = async () => {
      try {
        const res = await getAllProblems(API);
        setProblems(res.data || []);
      } catch (err) {
        console.error('Failed to fetch problems', err);
      } finally {
        setLoading(false);
      }
    };
    fetchProblems();
  }, [API]);

  // Derived stats
  const solvedSet = new Set(user?.solved_problems || []);
  const attemptedSet = new Set(user?.attempted_problems || []);
  
  const totalSolved = solvedSet.size;
  const totalAttempted = attemptedSet.size;
  const solveRate = totalAttempted > 0 ? Math.round((totalSolved / totalAttempted) * 100) : 0;

  // Difficulty breakdown logic
  const diffStats = {
    Easy: { solved: 0, total: 0 },
    Medium: { solved: 0, total: 0 },
    Hard: { solved: 0, total: 0 }
  };

  problems.forEach(p => {
    const diff = p.difficulty || 'Medium';
    if (diffStats[diff]) {
      diffStats[diff].total += 1;
      if (solvedSet.has(p.slug)) {
        diffStats[diff].solved += 1;
      }
    }
  });

  const recentActivity = [...(user?.solved_problems || [])].reverse().slice(0, 5);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="w-8 h-8 border-4 border-[var(--border)] border-t-[var(--accent)] rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Welcome back, {user?.username || 'Coder'}!</h1>
        <p className="dashboard-subtitle">Here's an overview of your progress.</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card green">
          <div className="stat-header">
            <span className="stat-label">Solved</span>
            <svg className="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
          </div>
          <div className="stat-value">{totalSolved}</div>
        </div>

        <div className="stat-card orange">
          <div className="stat-header">
            <span className="stat-label">Attempted</span>
            <svg className="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
            </svg>
          </div>
          <div className="stat-value">{totalAttempted}</div>
        </div>

        <div className="stat-card blue">
          <div className="stat-header">
            <span className="stat-label">Solve Rate</span>
            <svg className="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="20" x2="18" y2="10"></line>
              <line x1="12" y1="20" x2="12" y2="4"></line>
              <line x1="6" y1="20" x2="6" y2="14"></line>
            </svg>
          </div>
          <div className="stat-value">{solveRate}%</div>
        </div>
      </div>

      <div className="dashboard-row">
        {/* Difficulty Breakdown */}
        <div className="dashboard-panel">
          <h2 className="panel-title">Difficulty Breakdown</h2>
          <div className="difficulty-list">
            {['Easy', 'Medium', 'Hard'].map((diff) => {
              const { solved, total } = diffStats[diff] || { solved: 0, total: 0 };
              const percent = total > 0 ? (solved / total) * 100 : 0;
              const diffLower = diff.toLowerCase();
              return (
                <div key={diff} className="diff-item">
                  <div className="diff-header">
                    <span className={`diff-label ${diffLower}`}>{diff}</span>
                    <div className="diff-stats">
                      <span>{solved}</span> / {total || '-'}
                    </div>
                  </div>
                  <div className="progress-track">
                    <div 
                      className={`progress-fill ${diffLower}`} 
                      style={{ width: `${percent}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="dashboard-panel">
          <h2 className="panel-title">Recent Solves</h2>
          {recentActivity.length > 0 ? (
            <div className="activity-list">
              {recentActivity.map((slug, idx) => (
                <div key={idx} className="activity-item">
                  <div className="activity-icon solved">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </div>
                  <div className="activity-details">
                    <span className="activity-title">
                      {slug.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
                    </span>
                    <span className="activity-time">Solved</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="activity-empty">
              No recent activity. Start solving problems!
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
