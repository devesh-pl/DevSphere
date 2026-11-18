package com.devsphere.deployment.dto;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.*;
import java.util.UUID;
public record DeploymentCreate(@NotBlank @Size(min = 3, max = 40) @Pattern(
                                   regexp = "[a-z][a-z0-9]*(?:-[a-z0-9]+)*") String name,
    @NotBlank @Size(max = 255) String image,
    @JsonProperty("container_port") @Min(1) @Max(65535) Integer containerPort,
    @Min(1) @Max(2) Integer replicas, @JsonProperty("project_id") UUID projectId) {
  public int port() {
    return containerPort == null ? 80 : containerPort;
  }
  public int count() {
    return replicas == null ? 1 : replicas;
  }
}
