import { useCallback, useEffect, useState } from 'react';
import { API, request } from './api.js';
import { useDecisionDialog } from './useDecisionDialog.jsx';

const emptyProject = { name: '', slug: '', description: '', templateId: 'fastapi-basic', provisioningOperationId: null };
export function ProjectManager({ token, operations, onProvisioned }) {
  const { confirm, dialog } = useDecisionDialog();
  const [projects, setProjects] = useState([]);
  const [form, setForm] = useState(emptyProject);
  const [editing, setEditing] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState({});
  // READ: Load persisted Project Service records belonging to this developer.
  const refresh = useCallback(async () => {
    const items = await request(API.projects, token); setProjects(items);
  }, [token]);
  useEffect(() => {
    let active = true;
    request(API.projects, token).then(items => { if (active) setProjects(items); })
      .catch(err => { if (active) setError(err.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);
  async function action(work) {
    setBusy(true); setError(''); setMessage('');
    try { await work(); await refresh(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function save(event) {
    event.preventDefault();
    await action(async () => {
      const body = { ...form, provisioningOperationId: form.provisioningOperationId || null };
      // CREATE: Persist project metadata using the existing authenticated developer identity.
      // UPDATE: Save edited fields; the server verifies any completed provisioning link.
      const saved = await request(editing ? `${API.projects}/${editing}` : API.projects, token, { method: editing ? 'PUT' : 'POST', body: JSON.stringify(body) });
      setDetail(current => current?.id === saved.id ? saved : current);
      setEditing(null); setForm(emptyProject); setMessage('Project saved. Use Provision to generate its application archive.');
    });
  }
  // CREATE: Send the actual archive generation request to the existing Orchestrator.
  async function provision(project) {
    await action(async () => {
      const op = await request(`${API.operations}/operations`, token, { method: 'POST', body: JSON.stringify({ operation_type: 'provision_project', project_slug: project.slug, template_id: project.templateId, repository_url: 'https://github.com/example/devsphere-generated' }) });
      setPending(previous => ({ ...previous, [project.id]: op.id }));
      setMessage(`Provisioning submitted: ${op.id}. Link it after it completes.`); await onProvisioned();
    });
  }
  // UPDATE: Associate only a completed, owner-verified Orchestrator operation with this project.
  async function link(project, operationId) {
    await action(async () => {
      const { name, slug, description, templateId } = project;
      const saved = await request(`${API.projects}/${project.id}`, token, { method: 'PUT', body: JSON.stringify({ name, slug, description, templateId, provisioningOperationId: operationId }) });
      setDetail(current => current?.id === saved.id ? saved : current);
      setMessage('Completed application provisioning linked. Build & deploy is available below.');
    });
  }
  // READ: Fetch project details from the backend rather than relying on a stale list row.
  async function view(project) { await action(async () => setDetail(await request(`${API.projects}/${project.id}`, token))); }
  // DELETE: Require confirmation; deleting metadata preserves generated archives and workloads.
  async function remove(project) {
    if (!await confirm(`Delete project record ${project.name}? Generated archives and workloads remain available.`)) return;
    await action(async () => { await request(`${API.projects}/${project.id}`, token, { method: 'DELETE' }); setDetail(null); if (editing === project.id) { setEditing(null); setForm(emptyProject); } });
  }
  return <section className="panel">
    <h3>Project management · Spring Boot</h3>
    {dialog}
    {error && <div role="alert" className="error">{error}</div>}
    {message && <p role="status" className="message">{message}</p>}
    <form onSubmit={save} className="project-form">
      <label>Project name<input required maxLength={100} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
      <label>Project slug<input required minLength={3} maxLength={40} pattern="[a-z][a-z0-9]*(?:-[a-z0-9]+)*" disabled={!!form.provisioningOperationId} value={form.slug} onChange={e => setForm({ ...form, slug: e.target.value.toLowerCase() })} /></label>
      <label>Description<input maxLength={4000} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label>
      <label>Template<select disabled={!!form.provisioningOperationId} value={form.templateId} onChange={e => setForm({ ...form, templateId: e.target.value })}><option value="fastapi-basic">FastAPI Basic</option><option value="express-basic">Express Basic (archive only)</option></select></label>
      <button className="primary" disabled={busy}>{editing ? 'Save project' : 'Create project record'}</button>
      {editing && <button type="button" className="small-button" onClick={() => { setEditing(null); setForm(emptyProject); }}>Cancel edit</button>}
    </form>
    {loading ? <p role="status">Loading projects…</p> : projects.length === 0 ? <p className="empty">No project records yet.</p> : <div className="table-wrap"><table><thead><tr><th>Project</th><th>Status</th><th>Actions</th></tr></thead><tbody>{projects.map(project => {
      const candidates = operations.filter(op => {
        if (op.status !== 'completed' || op.operation_type !== 'provision_project') return false;
        try { const result = JSON.parse(op.result); return result.project_slug === project.slug && result.template_id === project.templateId; } catch { return false; }
      });
      return <tr key={project.id}><td>{project.name}<br/><span className="mono">{project.slug}</span></td><td>{project.status}</td><td><div className="actions">
        <button className="small-button" disabled={busy} onClick={() => view(project)}>View project</button>
        <button className="small-button" disabled={busy} onClick={() => { setEditing(project.id); const { name, slug, description, templateId, provisioningOperationId } = project; setForm({ name, slug, description, templateId, provisioningOperationId }); }}>Edit project</button>
        <button className="small-button" disabled={busy} onClick={() => remove(project)}>Delete project</button>
        {!project.provisioningOperationId && <><button className="small-button" disabled={busy || !!pending[project.id]} onClick={() => provision(project)}>Provision</button>{candidates.map(op => <button className="small-button" key={op.id} disabled={busy} onClick={() => link(project, op.id)}>Link completed {op.id.slice(0, 8)}</button>)}</>}
      </div></td></tr>;
    })}</tbody></table></div>}
    {detail && <pre className="log-output" aria-label="Project details">{JSON.stringify(detail, null, 2)}</pre>}
  </section>;
}

export function DeploymentCreator({ token, onCreated }) {
  const [projects, setProjects] = useState([]);
  const [form, setForm] = useState({ name: '', project_id: '', image: 'nginxinc/nginx-unprivileged:stable-alpine', container_port: 8080, replicas: 1 });
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; request(API.projects, token).then(items => { if (active) setProjects(items); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, [token]);
  // CREATE: Validate a real owned project through Eureka, then create Kubernetes resources.
  async function create(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { await request(`${API.springDeployments}/deployments`, token, { method: 'POST', body: JSON.stringify(form) }); await onCreated(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel"><h3>Create Java-managed deployment</h3>{error && <div role="alert" className="error">{error}</div>}<form onSubmit={create} className="project-form">
    <label>Deployment name<input required minLength={3} maxLength={40} pattern="[a-z][a-z0-9]*(?:-[a-z0-9]+)*" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}/></label>
    <label>Project<select required value={form.project_id} onChange={e => setForm({ ...form, project_id: e.target.value })}><option value="">Select project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    <label>Image<input required value={form.image} onChange={e => setForm({ ...form, image: e.target.value })}/></label>
    <label>Container port<input required type="number" min={1} max={65535} value={form.container_port} onChange={e => setForm({ ...form, container_port: Number(e.target.value) })}/></label>
    <label>Replicas<select value={form.replicas} onChange={e => setForm({ ...form, replicas: Number(e.target.value) })}><option value={1}>1</option><option value={2}>2</option></select></label>
    <button disabled={busy} className="primary">{busy ? 'Deploying…' : 'Deploy application'}</button>
  </form></section>;
}

export function BuildActions({ build, token, onRefresh }) {
  const { confirm, prompt, dialog } = useDecisionDialog();
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [detail, setDetail] = useState(null);
  async function action(work) { setBusy(true); setError(''); try { await work(); await onRefresh(); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  // READ: Inspect the owned build with its full backend lifecycle details.
  async function view() { await action(async () => setDetail(await request(`${API.builds}/builds/${build.id}`, token))); }
  // UPDATE: Change display metadata only; queued state is checked atomically by the backend.
  async function edit() { const label = await prompt('Build label', build.label || ''); if (label === null) return; await action(() => request(`${API.builds}/builds/${build.id}`, token, { method: 'PUT', body: JSON.stringify({ label }) })); }
  // DELETE: Cancel a queued build or archive a terminal build while retaining database history.
  async function remove() { if (!await confirm(`${build.status === 'queued' ? 'Cancel' : 'Archive'} build ${build.id}?`)) return; await action(() => request(`${API.builds}/builds/${build.id}`, token, { method: 'DELETE' })); }
  return <div>{dialog}<span>{build.label}</span><div className="actions"><button className="small-button" disabled={busy} onClick={view}>View build</button>{build.status === 'queued' && <button className="small-button" disabled={busy} onClick={edit}>Edit label</button>}{['queued', 'completed', 'failed'].includes(build.status) && <button className="small-button" disabled={busy} onClick={remove}>{build.status === 'queued' ? 'Cancel build' : 'Archive build'}</button>}</div>{error && <div role="alert" className="error">{error}</div>}{detail && <pre className="log-output">{JSON.stringify(detail, null, 2)}</pre>}</div>;
}
