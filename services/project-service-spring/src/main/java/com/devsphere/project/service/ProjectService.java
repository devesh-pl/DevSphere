package com.devsphere.project.service;
import com.devsphere.common.*;
import com.devsphere.project.dto.ProjectRequest;
import com.devsphere.project.entity.Project;
import com.devsphere.project.repository.ProjectRepository;
import java.time.Instant;
import java.util.*;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
@Transactional
public class ProjectService {
  private final ProjectRepository repository;
  private final ProvisioningClient provisioning;
  public ProjectService(ProjectRepository repository, ProvisioningClient provisioning) {
    this.repository = repository;
    this.provisioning = provisioning;
  }
  public Project create(ProjectRequest request, AuthUser user, String token) {
    var p = new Project();
    p.id = UUID.randomUUID();
    p.ownerId = user.id();
    p.createdAt = Instant.now();
    return apply(p, request, user, token);
  }
  @Transactional(readOnly = true)
  public Project get(UUID id, AuthUser user) {
    return repository.findByIdAndOwnerId(id, user.id())
        .orElseThrow(() -> new ApiException(404, "Project not found"));
  }
  @Transactional(readOnly = true)
  public List<Project> list(AuthUser user, int page, int size) {
    return repository.findByOwnerIdOrderByCreatedAtDesc(
        user.id(), PageRequest.of(page, Math.min(size, 100)));
  }
  public Project update(UUID id, ProjectRequest request, AuthUser user, String token) {
    var p = get(id, user);
    if (p.provisioningOperationId != null
        && (!p.slug.equals(request.slug()) || !p.templateId.equals(request.templateId())
            || !p.provisioningOperationId.equals(request.provisioningOperationId())))
      throw new ApiException(409, "Linked project identity is immutable");
    return apply(p, request, user, token);
  }
  private Project apply(Project p, ProjectRequest r, AuthUser user, String token) {
    p.status = provisioning.verify(r, user, token);
    p.name = r.name().trim();
    p.slug = r.slug();
    p.description = r.description();
    p.templateId = r.templateId();
    p.provisioningOperationId = r.provisioningOperationId();
    p.updatedAt = Instant.now();
    return repository.saveAndFlush(p);
  }
  public void delete(UUID id, AuthUser user) {
    repository.delete(get(id, user));
  }
}
