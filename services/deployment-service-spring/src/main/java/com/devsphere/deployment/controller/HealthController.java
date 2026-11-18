package com.devsphere.deployment.controller;
import com.devsphere.deployment.kubernetes.Workloads;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
@RestController
public class HealthController {
  private final JdbcTemplate db;
  private final Workloads workloads;
  public HealthController(JdbcTemplate db, Workloads workloads) {
    this.db = db;
    this.workloads = workloads;
  }
  @GetMapping("/health")
  public Map<String, String> health() {
    return Map.of("status", "ok", "service", "deployment-service-spring");
  }
  @GetMapping("/ready")
  public Map<String, String> ready() {
    try {
      db.queryForObject("SELECT 1", Integer.class);
      workloads.ready();
      return Map.of("status", "ready");
    } catch (RuntimeException e) {
      throw new com.devsphere.common.ApiException(503, "Deployment dependencies unavailable");
    }
  }
}
