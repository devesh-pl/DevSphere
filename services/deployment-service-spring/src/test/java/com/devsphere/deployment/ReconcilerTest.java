package com.devsphere.deployment;
import static org.junit.jupiter.api.Assertions.*;

import com.devsphere.deployment.kubernetes.Workloads;
import com.devsphere.deployment.reconciliation.Reconciler;
import io.fabric8.kubernetes.api.model.apps.*;
import org.junit.jupiter.api.Test;
class ReconcilerTest {
  @Test
  void reconcilesObservedMatchingRolloutOnly() {
    var d = new DeploymentBuilder()
                .withNewMetadata()
                .withGeneration(2L)
                .endMetadata()
                .withNewSpec()
                .withReplicas(1)
                .withNewTemplate()
                .withNewSpec()
                .addNewContainer()
                .withName("application")
                .withImage("image:v1")
                .endContainer()
                .endSpec()
                .endTemplate()
                .endSpec()
                .withNewStatus()
                .withObservedGeneration(2L)
                .withReadyReplicas(1)
                .withAvailableReplicas(1)
                .withUpdatedReplicas(1)
                .endStatus()
                .build();
    assertEquals("running", Reconciler.classify(d, "image:v1", 1));
    assertNull(Reconciler.classify(d, "image:v2", 1));
    assertNull(Reconciler.classify(d, "image:v1", 2));
    d.getStatus().setObservedGeneration(1L);
    assertEquals("deploying", Reconciler.classify(d, "image:v1", 1));
    d.getStatus().setObservedGeneration(2L);
    d.getStatus().setConditions(java.util.List.of(new DeploymentConditionBuilder()
            .withType("Progressing")
            .withStatus("False")
            .withReason("ProgressDeadlineExceeded")
            .build()));
    assertEquals("failed", Reconciler.classify(d, "image:v1", 1));
    assertEquals("missing", Reconciler.classify(null, "image:v1", 1));
  }
  @Test
  void imageAllowlistMatchesPythonPolicy() {
    assertTrue(Workloads.allowed("nginxinc/nginx-unprivileged:stable-alpine"));
    assertTrue(Workloads.allowed("devsphere-built/demo-api:abcdef12"));
    assertFalse(Workloads.allowed("nginx:latest"));
    assertFalse(Workloads.allowed("devsphere-built/../../evil:abcdef12"));
  }
}
