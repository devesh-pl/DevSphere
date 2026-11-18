package com.devsphere.deployment.service;
import com.devsphere.common.*;
import com.devsphere.deployment.discovery.ProjectDiscovery;
import com.devsphere.deployment.dto.*;
import com.devsphere.deployment.entity.*;
import com.devsphere.deployment.kubernetes.Workloads;
import com.devsphere.deployment.repository.*;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
@Service
public class DeploymentService {
  private final DeploymentRepository repository;
  private final RevisionRepository revisions;
  private final Workloads workloads;
  private final ProjectDiscovery projects;
  private final TransactionTemplate tx;
  private final boolean writes;
  public DeploymentService(DeploymentRepository repository, RevisionRepository revisions,
      Workloads workloads, ProjectDiscovery projects, PlatformTransactionManager manager,
      @Value("${devsphere.deployment-writes:false}") boolean writes) {
    this.repository = repository;
    this.revisions = revisions;
    this.workloads = workloads;
    this.projects = projects;
    this.tx = new TransactionTemplate(manager);
    this.writes = writes;
  }
  public Deployment get(String id, AuthUser user) {
    return repository.findByIdAndOwnerId(id, user.id().toString())
        .orElseThrow(() -> new ApiException(404, "Deployment not found"));
  }
  public List<Deployment> list(AuthUser user) {
    return repository.findByOwnerIdAndManagementServiceOrderByCreatedAtDesc(
        user.id().toString(), "java", PageRequest.of(0, 100));
  }
  private void writable(Deployment d) {
    if (!writes)
      throw new ApiException(409, "Java deployment writes are disabled");
    if (!"java".equals(d.managementService) || !d.name.startsWith("ds-java-")
        || !Workloads.NS.equals(d.namespace))
      throw new ApiException(409, "Python remains authoritative for this deployment");
  }
  private void image(String image) {
    if (!Workloads.allowed(image))
      throw new ApiException(422, "Image not in development allowlist");
  }
  public Deployment create(DeploymentCreate request, AuthUser user, String token) {
    if (!writes)
      throw new ApiException(409, "Java deployment writes are disabled");
    image(request.image());
    projects.verify(request.projectId(), user, token);
    var d = new Deployment();
    d.id = UUID.randomUUID().toString();
    d.ownerId = user.id().toString();
    d.name = "ds-java-" + d.id.substring(0, 12);
    d.image = request.image();
    d.containerPort = request.port();
    d.replicas = request.count();
    d.namespace = Workloads.NS;
    d.status = "deploying";
    d.createdAt = Instant.now();
    d.managementService = "java";
    d.projectId = request.projectId();
    tx.executeWithoutResult(s -> {
      repository.saveAndFlush(d);
      revision(d, "initial");
    });
    try {
      workloads.create(d);
    } catch (ApiException e) {
      // Preserve the failed record and exact ownership metadata; compensation touches only this
      // request's resources.
      try {
        workloads.delete(d);
      } catch (ApiException cleanup) {
        d.errorMessage = "Partial resource cleanup required";
      }
      d.status = "failed";
      if (d.errorMessage == null)
        d.errorMessage = e.getMessage();
      repository.saveAndFlush(d);
      throw e;
    }
    return d;
  }
  private Deployment lock(String id, AuthUser user) {
    return repository.lockOwned(id, user.id().toString())
        .orElseThrow(() -> new ApiException(404, "Deployment not found"));
  }
  public Deployment update(String id, DeploymentUpdate request, AuthUser user) {
    if (request.image() == null && request.replicas() == null)
      throw new ApiException(400, "Specify image or replicas");
    if (request.image() != null)
      image(request.image());
    return tx.execute(s -> {
      var d = lock(id, user);
      writable(d);
      if ("deleted".equals(d.status))
        throw new ApiException(404, "Active deployment not found");
      return apply(d, request.image() == null ? d.image : request.image(),
          request.replicas() == null ? d.replicas : request.replicas(), "update");
    });
  }
  private Deployment apply(Deployment d, String image, int replicas, String change) {
    if (image.equals(d.image) && replicas == d.replicas)
      return d;
    workloads.update(d, image, replicas);
    d.image = image;
    d.replicas = replicas;
    d.status = "deploying";
    d.errorMessage = null;
    revision(d, change);
    return repository.saveAndFlush(d);
  }
  private void revision(Deployment d, String change) {
    var history = revisions.findByDeploymentIdOrderByRevisionNumberDesc(d.id);
    var r = new Revision();
    r.deploymentId = d.id;
    r.revisionNumber = history.isEmpty() ? 1 : history.getFirst().revisionNumber + 1;
    r.image = d.image;
    r.replicas = d.replicas;
    r.changeType = change;
    r.createdAt = Instant.now();
    revisions.saveAndFlush(r);
  }
  public List<Revision> history(String id, AuthUser user) {
    get(id, user);
    return revisions.findByDeploymentIdOrderByRevisionNumberDesc(id);
  }
  public Deployment rollback(String id, int revision, AuthUser user) {
    return tx.execute(s -> {
      var d = lock(id, user);
      writable(d);
      if ("deleted".equals(d.status))
        throw new ApiException(404, "Active deployment not found");
      var r = revisions.findByDeploymentIdAndRevisionNumber(id, revision)
                  .orElseThrow(() -> new ApiException(404, "Revision not found"));
      image(r.image);
      return apply(d, r.image, r.replicas, "rollback");
    });
  }
  public void delete(String id, AuthUser user) {
    tx.executeWithoutResult(s -> {
      var d = lock(id, user);
      writable(d);
      if ("deleted".equals(d.status))
        return;
      workloads.delete(d);
      d.status = "deleted";
      d.errorMessage = null;
      repository.saveAndFlush(d);
    });
  }
  public Map<String, Object> response(Deployment d, boolean live) {
    var result = new LinkedHashMap<String, Object>();
    result.put("id", d.id);
    result.put("name", d.name);
    result.put("image", d.image);
    result.put("namespace", d.namespace);
    result.put("status", d.status);
    result.put("container_port", d.containerPort);
    result.put("replicas", d.replicas);
    result.put("created_at", d.createdAt);
    result.put("project_id", d.projectId);
    result.put("management_service", d.managementService);
    result.put("error_message", d.errorMessage);
    result.put("service_dns", d.name + "." + d.namespace + ".svc.cluster.local");
    if (live && "java".equals(d.managementService)
        && !List.of("failed", "deleted").contains(d.status)) {
      var resource = workloads.read(d);
      int ready = resource == null || resource.getStatus() == null
              || resource.getStatus().getReadyReplicas() == null
          ? 0
          : resource.getStatus().getReadyReplicas();
      result.put("ready_replicas", ready);
      result.put("desired_replicas", d.replicas);
      if (resource == null)
        result.put("status", "missing");
    }
    return result;
  }
  public Map<String, Object> pods(String id, AuthUser user) {
    var d = get(id, user);
    writable(d);
    var result =
        workloads.pods(d)
            .stream()
            .map(p -> {
              var statuses = p.getStatus().getContainerStatuses();
              if (statuses == null)
                statuses = List.<io.fabric8.kubernetes.api.model.ContainerStatus>of();
              return Map.of("name", p.getMetadata().getName(), "phase", p.getStatus().getPhase(),
                  "ready",
                  !statuses.isEmpty()
                      && statuses.stream().allMatch(c -> Boolean.TRUE.equals(c.getReady())),
                  "restarts",
                  statuses.stream()
                      .mapToInt(c -> c.getRestartCount() == null ? 0 : c.getRestartCount())
                      .sum());
            })
            .toList();
    return Map.of("deployment_id", id, "pods", result);
  }
  public Map<String, Object> logs(String id, AuthUser user, int tail) {
    var d = get(id, user);
    writable(d);
    return Map.of("deployment_id", id, "logs", workloads.logs(d, tail));
  }
}
