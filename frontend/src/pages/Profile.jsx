import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { updateMe } from '../api/users';
import toast from 'react-hot-toast';
import './Profile.css';

export default function Profile() {
  const { user, API, refreshUser } = useAuth();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    username: user?.username || '',
    preferred_difficulty: user?.preferred_difficulty || '',
  });
  const [saving, setSaving] = useState(false);

  const solvedCount = user?.solved_problems?.length || 0;
  const attemptedCount = user?.attempted_problems?.length || 0;
  const solveRate = attemptedCount > 0 ? Math.round((solvedCount / attemptedCount) * 100) : 0;

  const initials = user?.username
    ? user.username.substring(0, 2).toUpperCase()
    : user?.email?.substring(0, 2).toUpperCase() || 'U';

  const handleSave = async () => {
    setSaving(true);
    try {
      const updates = {};
      if (form.username !== user?.username) updates.username = form.username;
      if (form.preferred_difficulty !== (user?.preferred_difficulty || '')) {
        updates.preferred_difficulty = form.preferred_difficulty || null;
      }
      if (Object.keys(updates).length === 0) {
        toast.error('No changes to save');
        setSaving(false);
        return;
      }
      await updateMe(API, updates);
      await refreshUser();
      toast.success('Profile updated!');
      setEditing(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="profile-container">
      <div className="profile-content">
        <div className="profile-header">
          <h1>Profile</h1>
          <p>Manage your account and track your progress.</p>
        </div>

        <div className="profile-card">
          <div className="profile-avatar-section">
            <div className="profile-avatar">{initials}</div>
            <div className="profile-identity">
              <h2>{user?.username || 'User'}</h2>
              <p>{user?.email || ''}</p>
            </div>
          </div>
        </div>

        <div className="profile-stats-grid">
          <div className="profile-stat">
            <span className="profile-stat-value green">{solvedCount}</span>
            <span className="profile-stat-label">Solved</span>
          </div>
          <div className="profile-stat">
            <span className="profile-stat-value orange">{attemptedCount}</span>
            <span className="profile-stat-label">Attempted</span>
          </div>
          <div className="profile-stat">
            <span className="profile-stat-value blue">{solveRate}%</span>
            <span className="profile-stat-label">Solve Rate</span>
          </div>
        </div>

        <div className="profile-card">
          <div className="profile-card-header">
            <h3>Account Settings</h3>
            {!editing && (
              <button className="profile-edit-btn" onClick={() => setEditing(true)}>Edit</button>
            )}
          </div>

          <div className="profile-fields">
            <div className="profile-field">
              <label>Username</label>
              {editing ? (
                <input
                  type="text"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  className="profile-input"
                />
              ) : (
                <span className="profile-field-value">{user?.username}</span>
              )}
            </div>

            <div className="profile-field">
              <label>Email</label>
              <span className="profile-field-value">{user?.email}</span>
            </div>

            <div className="profile-field">
              <label>Preferred Difficulty</label>
              {editing ? (
                <select
                  value={form.preferred_difficulty}
                  onChange={(e) => setForm({ ...form, preferred_difficulty: e.target.value })}
                  className="profile-input"
                >
                  <option value="">Any</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              ) : (
                <span className="profile-field-value">
                  {user?.preferred_difficulty
                    ? user.preferred_difficulty.charAt(0).toUpperCase() + user.preferred_difficulty.slice(1)
                    : 'Any'}
                </span>
              )}
            </div>
          </div>

          {editing && (
            <div className="profile-actions">
              <button className="profile-save-btn" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
              <button className="profile-cancel-btn" onClick={() => { setEditing(false); setForm({ username: user?.username || '', preferred_difficulty: user?.preferred_difficulty || '' }); }}>
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
