import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { ProjectManager, DeploymentCreator, BuildActions } from './CrudPanels.jsx';
import { request } from './api.js';
vi.mock('./api.js', async original => ({ ...await original(), request: vi.fn() }));
afterEach(cleanup);
beforeEach(() => { vi.restoreAllMocks(); request.mockReset(); });
const project = { id: 'p1', name: 'API demo', slug: 'api-demo', description: 'Demo', templateId: 'fastapi-basic', provisioningOperationId: null, status: 'draft' };
test('project CRUD saves, reads details, edits and confirms deletion through APIs', async () => {
  let rows = [];
  request.mockImplementation(async (url, token, options = {}) => {
    if (options.method === 'POST') { rows = [{ ...JSON.parse(options.body), id: 'p1', status: 'draft' }]; return rows[0]; }
    if (options.method === 'PUT') { rows = [{ ...JSON.parse(options.body), id: 'p1' }]; return rows[0]; }
    if (options.method === 'DELETE') { rows = []; return {}; }
    return url.endsWith('/p1') ? rows[0] : rows;
  });
  render(<ProjectManager token="token" operations={[]} onProvisioned={vi.fn()} />);
  await screen.findByText('No project records yet.');
  fireEvent.change(screen.getByLabelText('Project name'), { target: { value: project.name } });
  fireEvent.change(screen.getByLabelText('Project slug'), { target: { value: project.slug } });
  fireEvent.click(screen.getByText('Create project record'));
  await screen.findByText(project.name);
  fireEvent.click(screen.getByText('View project'));
  await screen.findByLabelText('Project details');
  fireEvent.click(screen.getByText('Edit project'));
  fireEvent.change(screen.getByLabelText('Project name'), { target: { value: 'Edited demo' } });
  fireEvent.click(screen.getByText('Save project'));
  await screen.findByText('Edited demo');
  fireEvent.click(screen.getByText('Delete project'));
  fireEvent.click(await screen.findByText('Confirm'));
  await screen.findByText('No project records yet.');
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(request.mock.calls.some(call => call[2]?.method === 'PUT')).toBe(true);
});
test('project deletion cancellation sends no delete request', async () => {
  request.mockResolvedValue([project]);
  render(<ProjectManager token="token" operations={[]} onProvisioned={vi.fn()} />);
  fireEvent.click(await screen.findByText('Delete project'));
  fireEvent.click(await screen.findByText('Cancel'));
  expect(request.mock.calls.some(call => call[2]?.method === 'DELETE')).toBe(false);
});
test('project load error is visible', async () => {
  request.mockRejectedValue(new Error('Project service unavailable'));
  render(<ProjectManager token="token" operations={[]} onProvisioned={vi.fn()} />);
  expect((await screen.findByRole('alert')).textContent).toContain('unavailable');
});
test('deployment create forwards selected project and replica count', async () => {
  request.mockImplementation(async (url, token, options = {}) => options.method ? { id: 'd1' } : [project]);
  const refreshed = vi.fn(); render(<DeploymentCreator token="token" onCreated={refreshed} />);
  await screen.findByRole('option', { name: project.name });
  fireEvent.change(screen.getByLabelText('Deployment name'), { target: { value: 'demo-app' } });
  fireEvent.change(screen.getByLabelText('Project'), { target: { value: 'p1' } });
  fireEvent.click(screen.getByText('Deploy application'));
  await waitFor(() => expect(refreshed).toHaveBeenCalled());
  const call = request.mock.calls.find(call => call[2]?.method === 'POST');
  expect(JSON.parse(call[2].body)).toMatchObject({ project_id: 'p1', replicas: 1, container_port: 8080 });
});
test('queued build metadata edit and cancellation call real API contracts', async () => {
  request.mockResolvedValue({});
  render(<BuildActions token="token" build={{ id: 'b1', status: 'queued' }} onRefresh={vi.fn()} />);
  fireEvent.click(screen.getByText('Edit label'));
  fireEvent.change(await screen.findByLabelText('New value'), { target: { value: 'Practical' } });
  fireEvent.click(screen.getByText('Save value'));
  await waitFor(() => expect(request).toHaveBeenCalledWith('/api/build/builds/b1', 'token', { method: 'PUT', body: '{"label":"Practical"}' }));
  await waitFor(() => expect(screen.getByText('Cancel build').disabled).toBe(false));
  fireEvent.click(screen.getByText('Cancel build'));
  fireEvent.click(await screen.findByText('Confirm'));
  await waitFor(() => expect(request).toHaveBeenCalledWith('/api/build/builds/b1', 'token', { method: 'DELETE' }));
});
test('active build cannot be edited or deleted from the portal', () => {
  render(<BuildActions token="token" build={{ id: 'b1', status: 'building' }} onRefresh={vi.fn()} />);
  expect(screen.queryByText('Cancel build')).toBeNull(); expect(screen.queryByText('Edit label')).toBeNull(); expect(screen.queryByText('Archive build')).toBeNull();
});
