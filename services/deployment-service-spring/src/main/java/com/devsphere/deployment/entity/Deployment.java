package com.devsphere.deployment.entity;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
@Entity
@Table(name = "deployments", schema = "public")
public class Deployment {
  @Id @Column(length = 36) public String id;
  @Column(name = "owner_id", length = 36, nullable = false) public String ownerId;
  @Column(length = 63, nullable = false) public String name;
  @Column(length = 255, nullable = false) public String image;
  @Column(name = "container_port", nullable = false) public int containerPort;
  @Column(nullable = false) public int replicas;
  @Column(length = 63, nullable = false) public String namespace;
  @Column(length = 30, nullable = false) public String status;
  @Column(name = "error_message", columnDefinition = "text") public String errorMessage;
  @Column(name = "created_at", nullable = false) public Instant createdAt;
  @Column(name = "management_service", length = 20, nullable = false)
  public String managementService;
  @Column(name = "project_id") public UUID projectId;
}
