package com.devsphere.deployment.entity;
import jakarta.persistence.*;
import java.time.Instant;
@Entity
@Table(name = "deployment_revisions", schema = "public")
public class Revision {
  @Id @GeneratedValue(strategy = GenerationType.IDENTITY) public Long id;
  @Column(name = "deployment_id", length = 36, nullable = false) public String deploymentId;
  @Column(name = "revision_number", nullable = false) public int revisionNumber;
  @Column(length = 255, nullable = false) public String image;
  @Column(nullable = false) public int replicas;
  @Column(name = "change_type", length = 20, nullable = false) public String changeType;
  @Column(name = "created_at", nullable = false) public Instant createdAt;
}
