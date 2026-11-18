package com.devsphere.deployment.repository;
import com.devsphere.deployment.entity.Revision;
import java.util.*;
import org.springframework.data.jpa.repository.JpaRepository;
public interface RevisionRepository extends JpaRepository<Revision, Long> {
  List<Revision> findByDeploymentIdOrderByRevisionNumberDesc(String deploymentId);
  Optional<Revision> findByDeploymentIdAndRevisionNumber(String deploymentId, int revisionNumber);
}
