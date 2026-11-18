package com.devsphere.project.repository;
import com.devsphere.project.entity.Project;
import java.util.*;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
public interface ProjectRepository extends JpaRepository<Project, UUID> {
  Optional<Project> findByIdAndOwnerId(UUID id, UUID ownerId);
  List<Project> findByOwnerIdOrderByCreatedAtDesc(UUID ownerId, Pageable page);
}
