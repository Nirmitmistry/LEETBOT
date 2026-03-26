import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getAllProblems, searchProblems } from '../api/problems';
import './Problems.css';

export default function Problems() {
  const { API, user } = useAuth();
  const navigate = useNavigate();
  const [problems, setProblems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef(null);

  // Fetch all problems on mount
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

  // Debounced semantic search
  const handleSearch = useCallback((query) => {
    setSearchQuery(query);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query.trim() || query.trim().length < 3) {
      // Reset to full list
      setSearching(false);
      const refetch = async () => {
        try {
          const res = await getAllProblems(API);
          setProblems(res.data.results || []);
        } catch (err) {
          console.error(err);
        }
      };
      if (!loading) refetch();
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await searchProblems(API, query.trim());
        setProblems(res.data.results || []);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setSearching(false);
      }
    }, 400);
  }, [API, loading]);

  const handleRowClick = (problem) => {
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

  const solvedSet = new Set(user?.solved_problems || []);
  const attemptedSet = new Set(user?.attempted_problems || []);

  const getStatus = (slug) => {
    if (solvedSet.has(slug)) return 'solved';
    if (attemptedSet.has(slug)) return 'attempted';
    return null;
  };

  return (
    <div className="problems-container">
      <div className="problems-content">
        <div className="problems-header">
          <h1>Problem Set</h1>
          <p>Select a problem to start resolving it with our AI Assistant.</p>
        </div>

        {/* Semantic Search Bar */}
        <div className="search-bar-container">
          <div className="search-bar-wrapper">
            <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              className="search-input"
              placeholder="Semantic search — e.g. 'two pointer sliding window', 'binary tree traversal'..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
            />
            {searching && (
              <div className="search-spinner"></div>
            )}
            {searchQuery && !searching && (
              <button
                className="search-clear-btn"
                onClick={() => handleSearch('')}
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>
          {searchQuery.trim().length >= 3 && (
            <p className="search-hint">
              🔍 Showing semantic matches for "<strong>{searchQuery.trim()}</strong>"
            </p>
          )}
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
                  <th className="status-col">Status</th>
                  <th>Title</th>
                  <th>Difficulty</th>
                  <th>Acceptance</th>
                </tr>
              </thead>
              <tbody>
                {problems.length > 0 ? (
                  problems.map((prob) => {
                    const status = getStatus(prob.slug);
                    return (
                    <tr
                      key={prob.slug || prob.title}
                      className="problem-row"
                      onClick={() => handleRowClick(prob)}
                    >
                      <td className="status-col">
                        {status === 'solved' && (
                          <span className="status-icon status-solved" title="Solved">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>
                          </span>
                        )}
                        {status === 'attempted' && (
                          <span className="status-icon status-attempted" title="Attempted">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                          </span>
                        )}
                      </td>
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
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="4" style={{ textAlign: 'center', padding: '2rem', color: '#9ca3af' }}>
                      {searchQuery.trim().length >= 3 ? 'No matching problems found.' : 'No problems found.'}
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
