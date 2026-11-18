package com.devsphere.project.entity;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
@Entity
@Table(name = "projects", uniqueConstraints = @UniqueConstraint(columnNames = {"owner_id", "slug"}))
public class Project {
  @Id public UUID id;
  @Column(name = "owner_id", nullable = false) public UUID ownerId;
  @Column(nullable = false, length = 100) public String name;
  @Column(nullable = false, length = 40) public String slug;
  @Column(nullable = false, columnDefinition = "text") public String description;
  @Column(name = "template_id", nullable = false, length = 50) public String templateId;
  @Column(name = "provisioning_operation_id", unique = true) public UUID provisioningOperationId;
  @Column(nullable = false, length = 30) public String status;
  @Column(name = "created_at", nullable = false) public Instant createdAt;
  @Column(name = "updated_at", nullable = false) public Instant updatedAt;
}
