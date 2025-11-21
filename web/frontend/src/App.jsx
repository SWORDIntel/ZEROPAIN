import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';

// Auth Context
const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        try {
          const { data } = await axios.post('/api/auth/refresh', { refresh_token: refresh });
          localStorage.setItem('token', data.access_token);
          error.config.headers.Authorization = `Bearer ${data.access_token}`;
          return axios(error.config);
        } catch { localStorage.clear(); window.location.href = '/login'; }
      }
    }
    return Promise.reject(error);
  }
);

// Auth Provider
function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      api.get('/auth/me').then(({ data }) => setUser(data)).catch(() => localStorage.clear()).finally(() => setLoading(false));
    } else setLoading(false);
  }, []);

  const login = async (username, password) => {
    const { data } = await api.post('/auth/login', { username, password });
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    const { data: userData } = await api.get('/auth/me');
    setUser(userData);
    return userData;
  };

  const logout = async () => {
    try { await api.post('/auth/logout', { refresh_token: localStorage.getItem('refresh_token') }); } catch {}
    localStorage.clear();
    setUser(null);
  };

  if (loading) return <div className="loading-screen"><div className="scanner"></div><span>INITIALIZING ZEROPAIN...</span></div>;
  return <AuthContext.Provider value={{ user, login, logout, api }}>{children}</AuthContext.Provider>;
}

// Protected Route
const ProtectedRoute = ({ children }) => {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" />;
};

// Login Component
function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await login(username, password);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed');
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <div className="login-header">
          <div className="classification">TEMPEST CLASS C</div>
          <h1>ZEROPAIN</h1>
          <p>Molecular Analysis Platform</p>
        </div>
        <form onSubmit={handleSubmit}>
          {error && <div className="error-msg">{error}</div>}
          <div className="input-group">
            <label>OPERATOR ID</label>
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div className="input-group">
            <label>ACCESS KEY</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button type="submit" className="btn-primary">AUTHENTICATE</button>
        </form>
      </div>
    </div>
  );
}

// Dashboard Component
function Dashboard() {
  const { user, api } = useAuth();
  const [stats, setStats] = useState({ compounds: 0, jobs: 0, dockings: 0 });
  const [recentJobs, setRecentJobs] = useState([]);

  useEffect(() => {
    api.get('/compounds').then(({ data }) => setStats(s => ({ ...s, compounds: data.length }))).catch(() => {});
    api.get('/jobs').then(({ data }) => { setRecentJobs(data.slice(0, 5)); setStats(s => ({ ...s, jobs: data.length })); }).catch(() => {});
  }, [api]);

  return (
    <div className="dashboard">
      <div className="stats-grid">
        <StatCard title="COMPOUNDS" value={stats.compounds} icon="molecule" />
        <StatCard title="ACTIVE JOBS" value={stats.jobs} icon="process" />
        <StatCard title="DOCKINGS" value={stats.dockings} icon="dock" />
        <StatCard title="SYSTEM" value="ONLINE" icon="status" status="active" />
      </div>
      <div className="dashboard-grid">
        <div className="panel">
          <h3>QUICK ACTIONS</h3>
          <div className="actions">
            <Link to="/compounds" className="action-btn">Browse Compounds</Link>
            <Link to="/docking" className="action-btn">New Docking</Link>
            <Link to="/admet" className="action-btn">ADMET Analysis</Link>
          </div>
        </div>
        <div className="panel">
          <h3>RECENT JOBS</h3>
          <div className="job-list">
            {recentJobs.length ? recentJobs.map((job, i) => (
              <div key={i} className={`job-item ${job.status}`}>
                <span>{job.type}</span>
                <span className="status">{job.status}</span>
              </div>
            )) : <p className="no-data">No recent jobs</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

const StatCard = ({ title, value, status }) => (
  <div className={`stat-card ${status || ''}`}>
    <div className="stat-value">{value}</div>
    <div className="stat-title">{title}</div>
  </div>
);

// Compounds Browser
function Compounds() {
  const { api } = useAuth();
  const [compounds, setCompounds] = useState([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    api.get('/compounds').then(({ data }) => setCompounds(data)).catch(() => {});
  }, [api]);

  const filtered = compounds.filter(c => c.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="compounds-page">
      <div className="compounds-header">
        <h2>COMPOUND DATABASE</h2>
        <input type="text" placeholder="Search compounds..." value={search} onChange={(e) => setSearch(e.target.value)} className="search-input" />
      </div>
      <div className="compounds-grid">
        {filtered.map((c, i) => (
          <div key={i} className={`compound-card ${selected?.name === c.name ? 'selected' : ''}`} onClick={() => setSelected(c)}>
            <h4>{c.name}</h4>
            <div className="compound-meta">
              <span>Ki: {c.ki_orthosteric?.toFixed(2) || 'N/A'} nM</span>
              <span>Safety: {(c.safety_score * 100).toFixed(0)}%</span>
            </div>
          </div>
        ))}
      </div>
      {selected && (
        <div className="compound-detail">
          <h3>{selected.name}</h3>
          <div className="detail-grid">
            <div><label>SMILES</label><code>{selected.smiles}</code></div>
            <div><label>MW</label><span>{selected.molecular_weight?.toFixed(2)} g/mol</span></div>
            <div><label>Ki (MOR)</label><span>{selected.ki_orthosteric?.toFixed(2)} nM</span></div>
            <div><label>G-Protein Bias</label><span>{selected.g_protein_bias?.toFixed(2)}</span></div>
          </div>
          <div className="actions">
            <Link to={`/docking?compound=${selected.name}`} className="btn-primary">DOCK</Link>
            <Link to={`/admet?compound=${selected.name}`} className="btn-secondary">ADMET</Link>
          </div>
        </div>
      )}
    </div>
  );
}

// Docking Interface
function Docking() {
  const { api } = useAuth();
  const [smiles, setSmiles] = useState('');
  const [receptor, setReceptor] = useState('MOR');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const runDocking = async () => {
    setRunning(true);
    setError('');
    setResult(null);
    try {
      const { data } = await api.post('/dock', { smiles, receptor, exhaustiveness: 8 });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Docking failed');
    }
    setRunning(false);
  };

  return (
    <div className="docking-page">
      <h2>MOLECULAR DOCKING</h2>
      <div className="docking-form">
        <div className="input-group">
          <label>SMILES STRING</label>
          <input type="text" value={smiles} onChange={(e) => setSmiles(e.target.value)} placeholder="Enter SMILES..." />
        </div>
        <div className="input-group">
          <label>TARGET RECEPTOR</label>
          <select value={receptor} onChange={(e) => setReceptor(e.target.value)}>
            <option value="MOR">MOR (Mu Opioid)</option>
            <option value="DOR">DOR (Delta Opioid)</option>
            <option value="KOR">KOR (Kappa Opioid)</option>
          </select>
        </div>
        <button onClick={runDocking} disabled={running || !smiles} className="btn-primary">
          {running ? 'DOCKING...' : 'RUN DOCKING'}
        </button>
      </div>
      {error && <div className="error-msg">{error}</div>}
      {result && (
        <div className="docking-result">
          <h3>DOCKING RESULTS</h3>
          <div className="result-grid">
            <div><label>Binding Affinity</label><span>{result.binding_affinity?.toFixed(2)} kcal/mol</span></div>
            <div><label>Predicted Ki</label><span>{result.ki_predicted?.toFixed(2)} nM</span></div>
            <div><label>Receptor</label><span>{result.receptor}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}

// ADMET Analysis
function ADMET() {
  const { api } = useAuth();
  const [smiles, setSmiles] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  const runAnalysis = async () => {
    setRunning(true);
    try {
      const { data } = await api.post('/admet', { smiles });
      setResult(data);
    } catch {}
    setRunning(false);
  };

  return (
    <div className="admet-page">
      <h2>ADMET PREDICTION</h2>
      <div className="admet-form">
        <div className="input-group">
          <label>SMILES STRING</label>
          <input type="text" value={smiles} onChange={(e) => setSmiles(e.target.value)} placeholder="Enter SMILES..." />
        </div>
        <button onClick={runAnalysis} disabled={running || !smiles} className="btn-primary">
          {running ? 'ANALYZING...' : 'RUN ADMET'}
        </button>
      </div>
      {result && (
        <div className="admet-results">
          <h3>ADMET PROFILE</h3>
          <div className="admet-grid">
            {Object.entries(result).map(([key, val]) => (
              <div key={key} className="admet-item">
                <label>{key.replace(/_/g, ' ').toUpperCase()}</label>
                <span>{typeof val === 'number' ? val.toFixed(3) : String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Header
function Header() {
  const { user, logout } = useAuth();
  return (
    <header className="app-header">
      <div className="header-left">
        <Link to="/" className="logo">ZEROPAIN</Link>
        <span className="classification">TEMPEST CLASS C</span>
      </div>
      <nav>
        <Link to="/">Dashboard</Link>
        <Link to="/compounds">Compounds</Link>
        <Link to="/docking">Docking</Link>
        <Link to="/admet">ADMET</Link>
      </nav>
      <div className="header-right">
        <span className="user">{user?.username}</span>
        <button onClick={logout} className="btn-logout">LOGOUT</button>
      </div>
    </header>
  );
}

// Layout
function Layout({ children }) {
  return (
    <div className="app-layout">
      <Header />
      <main className="app-main">{children}</main>
    </div>
  );
}

// App
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/compounds" element={<Compounds />} />
                  <Route path="/docking" element={<Docking />} />
                  <Route path="/admet" element={<ADMET />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
