package com.devsphere.deployment.discovery;
import com.devsphere.common.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.client.*;
@Component
public class ProjectDiscovery {
  private final RestClient client;
  public ProjectDiscovery(@Qualifier("projectClient") RestClient client) {
    this.client = client;
  }
  public Map<?, ?> verify(UUID id, AuthUser user, String token) {
    if (id == null)
      throw new ApiException(
          400, "project_id required on Java deployments; legacy builds remain on Python");
    try {
      // The logical hostname is resolved by Eureka + Spring Cloud LoadBalancer.
      var project = client.get()
                        .uri("http://PROJECT-SERVICE/projects/{id}", id)
                        .header("Authorization", token)
                        .retrieve()
                        .body(Map.class);
      if (project == null || !user.id().toString().equals(project.get("ownerId")))
        throw new ApiException(404, "Owned project not found");
      return project;
    } catch (HttpClientErrorException e) {
      int status = e.getStatusCode().value();
      throw new ApiException(status == 401 ? 401
              : status == 403              ? 403
              : status == 404              ? 404
                                           : 503,
          "Project lookup rejected");
    } catch (RestClientException | IllegalStateException e) {
      throw new ApiException(503, "Project service discovery unavailable");
    }
  }
}
