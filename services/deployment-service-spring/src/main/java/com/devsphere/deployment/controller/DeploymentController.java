package com.devsphere.deployment.controller;
import com.devsphere.common.*;
import com.devsphere.deployment.discovery.ProjectDiscovery;
import com.devsphere.deployment.dto.*;
import com.devsphere.deployment.entity.Revision;
import com.devsphere.deployment.service.DeploymentService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
@RestController
@Validated
public class DeploymentController {
  private final DeploymentService service;
  private final ProjectDiscovery projects;
  public DeploymentController(DeploymentService service, ProjectDiscovery projects) {
    this.service = service;
    this.projects = projects;
  }
  // CREATE: Deploy application to Kubernetes
  @PostMapping("/deployments")
  @ResponseStatus(HttpStatus.CREATED)
  public Map<String, Object> create(@Valid @RequestBody DeploymentCreate request,
      @RequestAttribute AuthUser user, @RequestHeader("Authorization") String token) {
    return service.response(service.create(request, user, token), false);
  }
  // READ: List deployments
  @GetMapping("/deployments")
  public List<Map<String, Object>> list(@RequestAttribute AuthUser user) {
    return service.list(user).stream().map(d -> service.response(d, false)).toList();
  }
  // READ: Get deployment details
  @GetMapping("/deployments/{id}")
  public Map<String, Object> get(@PathVariable String id, @RequestAttribute AuthUser user) {
    return service.response(service.get(id, user), true);
  }
  // UPDATE: Scale or update deployment
  @RequestMapping(value = "/deployments/{id}", method = {RequestMethod.PUT, RequestMethod.PATCH})
  public Map<String, Object> update(@PathVariable String id,
      @Valid @RequestBody DeploymentUpdate request, @RequestAttribute AuthUser user) {
    return service.response(service.update(id, request, user), false);
  }
  // DELETE: Remove deployment from Kubernetes
  @DeleteMapping("/deployments/{id}")
  public Map<String, String> delete(@PathVariable String id, @RequestAttribute AuthUser user) {
    service.delete(id, user);
    return Map.of("id", id, "status", "deleted");
  }
  @GetMapping("/deployments/{id}/revisions")
  public List<Map<String, Object>> revisions(
      @PathVariable String id, @RequestAttribute AuthUser user) {
    return service.history(id, user)
        .stream()
        .map(r
            -> Map.<String, Object>of("revision_number", r.revisionNumber, "image", r.image,
                "replicas", r.replicas, "change_type", r.changeType, "created_at", r.createdAt))
        .toList();
  }
  public record Rollback(@Min(1) int revision) {}
  @PostMapping("/deployments/{id}/rollback")
  public Map<String, Object> rollback(@PathVariable String id, @Valid @RequestBody Rollback request,
      @RequestAttribute AuthUser user) {
    return service.response(service.rollback(id, request.revision(), user), false);
  }
  @GetMapping("/deployments/{id}/pods")
  public Map<String, Object> pods(@PathVariable String id, @RequestAttribute AuthUser user) {
    return service.pods(id, user);
  }
  @GetMapping("/deployments/{id}/logs")
  public Map<String, Object> logs(@PathVariable String id, @RequestAttribute AuthUser user,
      @RequestParam(name = "tail_lines", defaultValue = "100") @Min(1) @Max(200) int tail) {
    return service.logs(id, user, tail);
  }
  @GetMapping("/discovery/projects/{id}")
  public Map<?, ?> discovery(@PathVariable UUID id, @RequestAttribute AuthUser user,
      @RequestHeader("Authorization") String token) {
    return projects.verify(id, user, token);
  }
}
