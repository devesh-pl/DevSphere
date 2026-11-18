package com.devsphere.project.controller;
import com.devsphere.common.AuthUser;
import com.devsphere.project.dto.ProjectRequest;
import com.devsphere.project.entity.Project;
import com.devsphere.project.service.ProjectService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/projects")
@Validated
public class ProjectController {
  private final ProjectService service;
  public ProjectController(ProjectService service) {
    this.service = service;
  }
  // CREATE: Create a project
  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  public Project create(@Valid @RequestBody ProjectRequest request, @RequestAttribute AuthUser user,
      @RequestHeader("Authorization") String token) {
    return service.create(request, user, token);
  }
  // READ: Retrieve projects
  @GetMapping
  public List<Project> list(@RequestAttribute AuthUser user,
      @RequestParam(defaultValue = "0") @Min(0) int page,
      @RequestParam(defaultValue = "50") @Min(1) @Max(100) int size) {
    return service.list(user, page, size);
  }
  // READ: Retrieve one project
  @GetMapping("/{id}")
  public Project get(@PathVariable UUID id, @RequestAttribute AuthUser user) {
    return service.get(id, user);
  }
  // UPDATE: Modify a project
  @PutMapping("/{id}")
  public Project update(@PathVariable UUID id, @Valid @RequestBody ProjectRequest request,
      @RequestAttribute AuthUser user, @RequestHeader("Authorization") String token) {
    return service.update(id, request, user, token);
  }
  // DELETE: Remove a project
  @DeleteMapping("/{id}")
  @ResponseStatus(HttpStatus.NO_CONTENT)
  public void delete(@PathVariable UUID id, @RequestAttribute AuthUser user) {
    service.delete(id, user);
  }
}
