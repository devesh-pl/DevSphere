import { useCallback, useEffect, useState } from 'react';
import {
  Activity, Box, Cloud, FolderPlus, Hammer, History,
  LogOut, RefreshCw, Rocket, ShieldCheck
} from 'lucide-react';

const API = {
  auth: '/api/auth',
  operations: '/api/orchestrator',
  builds: '/api/build',
  deployments: '/api/deployment'
};

async function request(url, token, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });

  const raw = await response.text();
  let data;

  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { detail: raw || 'Invalid server response' };
  }

  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map(error =>
            `${(error.loc || []).join('.')}: ${error.msg}`
          ).join('; ')
        : JSON.stringify(detail || data);

    throw new Error(
      `HTTP ${response.status}: ${message}`
    );
  }

  return data;
}

function Status({ value }) {
  return (
    <span className={`status ${value || 'unknown'}`}>
      <span className="status-dot" />
      {value || 'unknown'}
    </span>
  );
}

function AuthScreen({ onAuthenticated }) {
  const [register, setRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');

    try {
      if (register) {
        await request(`${API.auth}/register`, null, {
          method: 'POST',
          body: JSON.stringify({
            email,
            password,
            full_name: name
          })
        });
      }

      const login = await request(`${API.auth}/login`, null, {
        method: 'POST',
        body: JSON.stringify({ email, password })
      });

      const token = login.access_token;

      if (!token) throw new Error('Missing access token');

      const user = await request(`${API.auth}/me`, token);

      onAuthenticated(token, user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-brand">
        <div className="brand-icon"><Box size={26} /></div>
        <h1>DevSphere</h1>
        <p>One platform. From code to Kubernetes.</p>
      </div>

      <form className="auth-card" onSubmit={submit}>
        <h2>{register ? 'Create an account' : 'Welcome back'}</h2>
        <p className="muted">
          {register
            ? 'Get started with your developer workspace.'
            : 'Sign in to your developer workspace.'}
        </p>

        {register && (
          <label>
            Full name
            <input
              required
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Your name"
            />
          </label>
        )}

        <label>
          Email address
          <input
            type="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="developer@example.com"
          />
        </label>

        <label>
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
        </label>

        {error && <div className="error">{error}</div>}

        <button className="primary full" disabled={busy}>
          {busy ? 'Please wait...' : register ? 'Create account' : 'Sign in'}
        </button>

        <button
          type="button"
          className="text-button"
          onClick={() => {
            setRegister(!register);
            setError('');
          }}
        >
          {register
            ? 'Already have an account? Sign in'
            : 'New here? Create an account'}
        </button>
      </form>
    </div>
  );
}

function ProjectCreator({ token, onCreated }) {
  const [slug, setSlug] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage('');

    try {
      const operation = await request(
        `${API.operations}/operations`,
        token,
        {
          method: 'POST',
          body: JSON.stringify({
            operation_type: 'provision_project',
            project_slug: slug,
            template_id: 'fastapi-basic',
            repository_url: 'https://github.com/example/devsphere-generated'
          })
        }
      );

      setMessage(`Provisioning submitted: ${operation.id}`);
      setSlug('');
      onCreated(operation);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <FolderPlus size={20} />
        <h3>Create a project</h3>
      </div>

      <form onSubmit={submit} className="project-form">
        <label>
          Project slug
          <input
            required
            value={slug}
            onChange={e => setSlug(e.target.value.toLowerCase())}
            pattern="[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
            maxLength={40}
            placeholder="my-api-service"
          />
        </label>

        <label>
          Template
          <select value="fastapi-basic" disabled>
            <option value="fastapi-basic">FastAPI Basic</option>
          </select>
        </label>

        <button className="primary" disabled={busy}>
          <Rocket size={16} />
          {busy ? 'Submitting...' : 'Create project'}
        </button>
      </form>

      {message && <p className="message">{message}</p>}
    </section>
  );
}

function Operations({ token, operations, onBuild }) {
  const [busyId, setBusyId] = useState(null);

  async function startBuild(operation) {
    setBusyId(operation.id);

    try {
      await onBuild(operation);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <Activity size={20} />
        <h3>Provisioning operations</h3>
      </div>

      {operations.length === 0 ? (
        <p className="empty">Create your first project to get started.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Operation</th>
                <th>Type</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {operations.map(operation => (
                <tr key={operation.id}>
                  <td className="mono">{operation.id.slice(0, 12)}...</td>
                  <td>{operation.operation_type}</td>
                  <td><Status value={operation.status} /></td>
                  <td>
                    <button
                      className="small-button"
                      disabled={
                        operation.status !== 'completed'
                        || busyId === operation.id
                      }
                      onClick={() => startBuild(operation)}
                    >
                      <Hammer size={14} />
                      Build & deploy
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}


function Builds({ builds, token, onRefresh }) {
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function retry(build) {
    setBusyId(build.id);
    setError('');
    setMessage('');

    try {
      await request(
        `${API.builds}/builds/${build.id}/retry`,
        token,
        { method: 'POST' }
      );

      setMessage(`Build ${build.id.slice(0, 12)} queued for retry.`);
      await onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <Hammer size={20} />
        <h3>Build pipeline</h3>
      </div>

      {error && <div className="error">{error}</div>}
      {message && <p className="message">{message}</p>}

      {builds.length === 0 ? (
        <p className="empty">No builds submitted yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Build ID</th>
                <th>Project</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Deployment</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {builds.map(build => (
                <tr key={build.id}>
                  <td className="mono">{build.id.slice(0, 12)}...</td>
                  <td>{build.project_slug || '—'}</td>
                  <td>
                    <Status value={build.status} />
                    {build.error && (
                      <div className="build-error">{build.error}</div>
                    )}
                  </td>
                  <td>
                    {build.attempt_count ?? 0}
                    /{build.max_attempts ?? 3}
                  </td>
                  <td className="mono">
                    {build.deployment_id
                      ? build.deployment_id.slice(0, 12) + '...'
                      : '—'}
                  </td>
                  <td>
                    {build.status === 'failed' &&
                     (build.attempt_count ?? 0) <
                     (build.max_attempts ?? 3) ? (
                      <button
                        className="small-button"
                        disabled={busyId === build.id}
                        onClick={() => retry(build)}
                      >
                        <RefreshCw size={14} />
                        Retry
                      </button>
                    ) : (
                      <span className="muted small">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Deployments({ token, deployments, onRefresh }) {
  const [revisions, setRevisions] = useState({});
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');
  const [live, setLive] = useState({});

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      const active = deployments.filter(
        deployment => deployment.status !== 'deleted'
      );

      const results = await Promise.allSettled(
        active.map(deployment =>
          request(
            `${API.deployments}/deployments/${deployment.id}`,
            token
          )
        )
      );

      if (cancelled) return;

      const next = {};

      active.forEach((deployment, index) => {
        const result = results[index];

        if (result.status === 'fulfilled') {
          next[deployment.id] = result.value;
        } else {
          next[deployment.id] = {
            status: 'unavailable',
            ready_replicas: null,
            desired_replicas: null
          };
        }
      });

      setLive(next);
    }

    loadStatus();
    const timer = setInterval(loadStatus, 5000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [token, deployments.map(d => d.id).join(',')]);


  async function scale(deployment, replicas) {
    setBusy(deployment.id);
    setError('');

    try {
      await request(
        `${API.deployments}/deployments/${deployment.id}`,
        token,
        {
          method: 'PATCH',
          body: JSON.stringify({ replicas })
        }
      );

      await onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  async function history(deployment) {
    setError('');

    try {
      const items = await request(
        `${API.deployments}/deployments/${deployment.id}/revisions`,
        token
      );

      setRevisions(previous => ({
        ...previous,
        [deployment.id]: items
      }));
    } catch (err) {
      setError(err.message);
    }
  }

  async function rollback(deployment, revision) {
    setBusy(deployment.id);
    setError('');

    try {
      await request(
        `${API.deployments}/deployments/${deployment.id}/rollback`,
        token,
        {
          method: 'POST',
          body: JSON.stringify({ revision })
        }
      );

      await onRefresh();
      await history(deployment);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <Cloud size={20} />
        <h3>Kubernetes deployments</h3>
      </div>

      {error && <div className="error">{error}</div>}

      {deployments.length === 0 ? (
        <p className="empty">No applications deployed yet.</p>
      ) : (
        <div className="deployment-grid">
          {deployments.map(deployment => (
            <article className="deployment-card" key={deployment.id}>
              <div className="deployment-top">
                <div>
                  <h4>{deployment.name}</h4>
                  <span className="mono small">
                    {deployment.namespace}
                  </span>
                </div>
                <Status
                  value={live[deployment.id]?.status || deployment.status}
                />
              </div>

              <div className="image-name">{deployment.image}</div>

              <div className="deployment-meta">
                <span>
                  Ready: {live[deployment.id]?.ready_replicas ?? '—'}
                  /{live[deployment.id]?.desired_replicas ??
                    deployment.replicas}
                </span>
                <span>Port: {deployment.container_port}</span>
              </div>

              <div className="actions">
                <button
                  className="small-button"
                  disabled={busy === deployment.id}
                  onClick={() => scale(deployment, 1)}
                >
                  Scale 1
                </button>
                <button
                  className="small-button"
                  disabled={busy === deployment.id}
                  onClick={() => scale(deployment, 2)}
                >
                  Scale 2
                </button>
                <button
                  className="small-button"
                  onClick={() => history(deployment)}
                >
                  <History size={14} /> History
                </button>
              </div>

              {revisions[deployment.id] && (
                <div className="revision-list">
                  {revisions[deployment.id].length === 0 && (
                    <p className="muted small">No revisions recorded yet.</p>
                  )}

                  {revisions[deployment.id].map(revision => (
                    <div className="revision" key={revision.revision_number}>
                      <span>
                        Revision {revision.revision_number}
                        {' · '}
                        {revision.replicas} replica(s)
                      </span>
                      <button
                        className="small-button"
                        disabled={busy === deployment.id}
                        onClick={() => rollback(
                          deployment,
                          revision.revision_number
                        )}
                      >
                        Restore
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default function App() {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [section, setSection] = useState('overview');
  const [operations, setOperations] = useState([]);
  const [builds, setBuilds] = useState([]);
  const [deployments, setDeployments] = useState([]);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    if (!token) return;

    try {
      const [ops, jobs, apps] = await Promise.all([
        request(`${API.operations}/operations`, token),
        request(`${API.builds}/builds`, token),
        request(`${API.deployments}/deployments`, token)
      ]);

      setOperations(Array.isArray(ops) ? ops : ops.items || []);
      setBuilds(Array.isArray(jobs) ? jobs : jobs.items || []);
      setDeployments(Array.isArray(apps) ? apps : apps.items || []);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;

    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [token, refresh]);

  async function buildProject(operation) {
    try {
      await request(`${API.builds}/builds`, token, {
        method: 'POST',
        body: JSON.stringify({ operation_id: operation.id })
      });

      setSection('builds');
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!token) {
    return <AuthScreen onAuthenticated={(accessToken, account) => {
      setToken(accessToken);
      setUser(account);
    }} />;
  }

  const navigation = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'projects', label: 'Projects', icon: FolderPlus },
    { id: 'builds', label: 'Builds', icon: Hammer },
    { id: 'deployments', label: 'Deployments', icon: Cloud }
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon"><Box size={22} /></div>
          <span>DevSphere</span>
        </div>

        <p className="sidebar-label">WORKSPACE</p>

        <nav>
          {navigation.map(item => {
            const Icon = item.icon;

            return (
              <button
                key={item.id}
                className={`nav-link ${section === item.id ? 'active' : ''}`}
                onClick={() => setSection(item.id)}
              >
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="account">
            <ShieldCheck size={17} />
            <span>{user?.email || 'Developer'}</span>
          </div>
          <button className="nav-link" onClick={() => {
            setToken(null);
            setUser(null);
            setOperations([]);
            setBuilds([]);
            setDeployments([]);
            setSection('overview');
          }}>
            <LogOut size={17} /> Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">DEVELOPER WORKSPACE</p>
            <h1>{navigation.find(x => x.id === section)?.label}</h1>
          </div>
          <button className="small-button" onClick={refresh}>
            <RefreshCw size={16} /> Refresh
          </button>
        </header>

        {error && <div className="error">{error}</div>}

        {section === 'overview' && (
          <>
            <div className="stat-grid">
              <div className="stat">
                <p>Provisioning operations</p>
                <strong>{operations.length}</strong>
                <FolderPlus size={20} />
              </div>
              <div className="stat">
                <p>Completed builds</p>
                <strong>
                  {builds.filter(b => b.status === 'completed').length}
                </strong>
                <Hammer size={20} />
              </div>
              <div className="stat">
                <p>Active deployments</p>
                <strong>
                  {deployments.filter(d => d.status !== 'deleted').length}
                </strong>
                <Cloud size={20} />
              </div>
            </div>

            <ProjectCreator token={token} onCreated={refresh} />
            <Builds builds={builds.slice(0, 5)} token={token} onRefresh={refresh} />
          </>
        )}

        {section === 'projects' && (
          <>
            <ProjectCreator token={token} onCreated={refresh} />
            <Operations
              token={token}
              operations={operations}
              onBuild={buildProject}
            />
          </>
        )}

        {section === 'builds' && <Builds builds={builds} token={token} onRefresh={refresh} />}

        {section === 'deployments' && (
          <Deployments
            token={token}
            deployments={deployments.filter(d => d.status !== 'deleted')}
            onRefresh={refresh}
          />
        )}
      </main>
    </div>
  );
}
