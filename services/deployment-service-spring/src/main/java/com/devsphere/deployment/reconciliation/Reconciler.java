package com.devsphere.deployment.reconciliation;
import com.devsphere.deployment.kubernetes.Workloads;
import com.devsphere.deployment.repository.DeploymentRepository;
import io.micrometer.core.instrument.MeterRegistry;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
@Component
public class Reconciler {
  private final DeploymentRepository repository;
  private final Workloads workloads;
  private final TransactionTemplate tx;
  private final boolean writes;
  private final MeterRegistry metrics;
  public Reconciler(DeploymentRepository repository, Workloads workloads,
      PlatformTransactionManager manager,
      @Value("${devsphere.deployment-writes:false}") boolean writes, MeterRegistry metrics) {
    this.repository = repository;
    this.workloads = workloads;
    this.tx = new TransactionTemplate(manager);
    this.writes = writes;
    this.metrics = metrics;
  }
  public static String classify(
      io.fabric8.kubernetes.api.model.apps.Deployment resource, String image, int replicas) {
    if (resource == null)
      return "missing";
    var spec = resource.getSpec();
    var status = resource.getStatus();
    if (!Objects.equals(spec.getReplicas(), replicas)
        || spec.getTemplate().getSpec().getContainers().stream().noneMatch(
            c -> "application".equals(c.getName()) && image.equals(c.getImage())))
      return null;
    if (status == null || status.getObservedGeneration() == null
        || resource.getMetadata().getGeneration() == null
        || status.getObservedGeneration() < resource.getMetadata().getGeneration())
      return "deploying";
    if (status.getConditions() != null
        && status.getConditions().stream().anyMatch(c
            -> "Progressing".equals(c.getType()) && "False".equals(c.getStatus())
                && "ProgressDeadlineExceeded".equals(c.getReason())))
      return "failed";
    return status.getReadyReplicas() != null && status.getReadyReplicas() >= replicas
            && status.getAvailableReplicas() != null && status.getAvailableReplicas() >= replicas
            && status.getUpdatedReplicas() != null && status.getUpdatedReplicas() >= replicas
        ? "running"
        : "deploying";
  }
  @Scheduled(fixedDelayString = "${devsphere.reconcile-ms:15000}")
  public void reconcile() {
    if (!writes)
      return;
    for (var snapshot : repository.findByManagementServiceAndStatusIn(
             "java", List.of("deploying", "running", "missing"))) {
      try {
        var resource = workloads.read(snapshot);
        String next = classify(resource, snapshot.image, snapshot.replicas);
        if (next == null)
          continue;
        tx.executeWithoutResult(s -> {
          var current = repository.lockOwned(snapshot.id, snapshot.ownerId).orElse(null);
          if (current != null && current.image.equals(snapshot.image)
              && current.replicas == snapshot.replicas && current.status.equals(snapshot.status)) {
            current.status = next;
            current.errorMessage =
                "failed".equals(next) ? "Kubernetes rollout deadline exceeded" : null;
            repository.saveAndFlush(current);
          }
        });
        metrics.counter("devsphere.reconciliation.total", "result", next).increment();
      } catch (RuntimeException e) {
        metrics.counter("devsphere.reconciliation.total", "result", "error").increment();
      }
    }
  }
}
