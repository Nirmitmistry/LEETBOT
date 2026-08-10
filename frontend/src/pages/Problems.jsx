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
  const requestIdRef = useRef(0);
  const allProblemsRef = useRef([]);

  // Fetch ALL problems on mount (paginated)
  useEffect(() => {
    const fetchAllProblems = async () => {
      const PAGE_SIZE = 200;
      let skip = 0;
      let all = [];
      try {
        while (true) {
          const res = await getAllProblems(API, skip, PAGE_SIZE);
          const batch = res.data.results || [];
          all = all.concat(batch);
          if (batch.length < PAGE_SIZE) break;  // last page
          skip += PAGE_SIZE;
        }
        allProblemsRef.current = all;
        setProblems(all);
      } catch (err) {
        setError('Failed to load problems. Please try again.');
        console.error(err);
        // If we got partial data, still show it
        if (all.length > 0) {
          allProblemsRef.current = all;
          setProblems(all);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchAllProblems();
  }, [API]);

  // Client-side text filter fallback
  const filterLocally = useCallback((query) => {
    const q = query.toLowerCase();
    return allProblemsRef.current.filter((p) => {
      const titleMatch = p.title?.toLowerCase().includes(q);
      const slugMatch = p.slug?.toLowerCase().includes(q);
      const tagMatch = (p.tags || []).some((t) => t.toLowerCase().includes(q));
      const diffMatch = p.difficulty?.toLowerCase().includes(q);
      return titleMatch || slugMatch || tagMatch || diffMatch;
    });
  }, []);

  // Debounced search — tries semantic search first, falls back to local filter
  const handleSearch = useCallback((query) => {
    setSearchQuery(query);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query.trim() || query.trim().length < 3) {
      // Restore full list instantly from cache
      setSearching(false);
      if (query.trim().length > 0) {
        // 1-2 character partial query: quick local filter
        setProblems(filterLocally(query.trim()));
      } else {
        setProblems(allProblemsRef.current);
      }
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      const currentRequestId = ++requestIdRef.current;
      try {
        const res = await searchProblems(API, query.trim());
        if (currentRequestId === requestIdRef.current) {
          const results = res.data.results || [];
          if (results.length > 0) {
            setProblems(results);
          } else {
            // Semantic search returned nothing — try local filter
            setProblems(filterLocally(query.trim()));
          }
        }
      } catch (err) {
        console.error('Search failed:', err);
        // Backend search failed — fall back to client-side filter
        if (currentRequestId === requestIdRef.current) {
          setProblems(filterLocally(query.trim()));
        }
      } finally {
        if (currentRequestId === requestIdRef.current) {
          setSearching(false);
        }
      }
    }, 400);
  }, [API, filterLocally]);

  const handleRowClick = (problem) => {
    sessionStorage.setItem('leetbot_active_problem', JSON.stringify(problem));
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
                aria-label="Clear search"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            )}
          </div>
          {searchQuery.trim().length >= 3 && (
            <p className="search-hint">
              Showing semantic matches for "<strong>{searchQuery.trim()}</strong>"
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
