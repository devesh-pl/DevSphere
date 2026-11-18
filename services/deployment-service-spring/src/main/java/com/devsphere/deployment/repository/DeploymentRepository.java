package com.devsphere.deployment.repository;
import com.devsphere.deployment.entity.Deployment;
import jakarta.persistence.LockModeType;
import java.util.*;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.*;
public interface DeploymentRepository extends JpaRepository<Deployment, String> {
  Optional<Deployment> findByIdAndOwnerId(String id, String ownerId);
  List<Deployment> findByOwnerIdAndManagementServiceOrderByCreatedAtDesc(
      String ownerId, String managementService, Pageable page);
  List<Deployment> findByManagementServiceAndStatusIn(
      String authority, Collection<String> statuses);
  @Lock(LockModeType.PESSIMISTIC_WRITE)
  @Query("select d from Deployment d where d.id=:id and d.ownerId=:owner")
  Optional<Deployment> lockOwned(String id, String owner);
}
