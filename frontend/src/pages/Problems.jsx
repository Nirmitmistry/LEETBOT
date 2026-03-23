import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getAllProblems } from '../api/problems';
import './Problems.css';

export default function Problems() {
  const { API } = useAuth();
  const navigate = useNavigate();
  const [problems, setProblems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProblems = async () => {
      try {
        const res = await getAllProblems(API);
        setProblems(res.data.results || []);
      } catch (err) {
        setError('Failed to load problems. Please try again.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchProblems();
  }, [API]);

  const handleRowClick = (problem) => {
    // Navigate to Chat, passing problem context
    navigate('/chat', { state: { problemContext: problem } });
  };

  const getDifficultyClass = (difficulty) => {
    switch (difficulty?.toLowerCase()) {
      case 'easy': return 'diff-easy';
      case 'medium': return 'diff-medium';
      case 'hard': return 'diff-hard';
      default: return '';
    }
  };

  return (
    <div className="problems-container">
      <div className="problems-content">
        <div className="problems-header">
          <h1>Problem Set</h1>
          <p>Select a problem to start resolving it with our AI Assistant.</p>
        </div>

        {error && (
          <div className="error-state">
            <p>{error}</p>
          </div>
        )}

        <div className="problems-table-container">
          {loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Loading problems...</p>
            </div>
          ) : (
            <table className="problems-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Difficulty</th>
                  <th>Acceptance</th>
                </tr>
              </thead>
              <tbody>
                {problems.length > 0 ? (
                  problems.map((prob) => (
                    <tr 
                      key={prob.slug || prob.title} 
                      className="problem-row"
                      onClick={() => handleRowClick(prob)}
                    >
                      <td>
                        <div className="problem-title">{prob.title}</div>
                      </td>
                      <td>
                        <span className={`diff-badge ${getDifficultyClass(prob.difficulty)}`}>
                          {prob.difficulty || 'Unknown'}
                        </span>
                      </td>
                      <td>
                        <span className="acceptance-rate">
                          {prob.acceptance_rate ? `${prob.acceptance_rate.toFixed(1)}%` : 'N/A'}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="3" style={{ textAlign: 'center', padding: '2rem', color: '#9ca3af' }}>
                      No problems found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
