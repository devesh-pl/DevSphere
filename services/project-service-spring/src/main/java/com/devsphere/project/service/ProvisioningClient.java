package com.devsphere.project.service;
import com.devsphere.common.*;
import com.devsphere.project.dto.ProjectRequest;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.*;
@Component
public class ProvisioningClient {
  private final RestClient client;
  public ProvisioningClient(@Value("${devsphere.orchestrator-url}") String url) {
    var factory = new JdkClientHttpRequestFactory(java.net.http.HttpClient.newBuilder()
            .connectTimeout(java.time.Duration.ofSeconds(3))
            .build());
    factory.setReadTimeout(java.time.Duration.ofSeconds(5));
    client = RestClient.builder().baseUrl(url).requestFactory(factory).build();
  }
  public String verify(ProjectRequest request, AuthUser user, String token) {
    if (request.provisioningOperationId() == null)
      return "draft";
    try {
      var op = client.get()
                   .uri("/operations/{id}", request.provisioningOperationId())
                   .header("Authorization", token)
                   .retrieve()
                   .body(Map.class);
      if (op == null || !user.id().toString().equals(op.get("owner_id"))
          || !"provision_project".equals(op.get("operation_type")))
        throw new ApiException(404, "Owned provisioning operation not found");
      // Only completed results prove archive generation; never advertise a draft as provisioned.
      if (!"completed".equals(op.get("status")))
        throw new ApiException(409, "Completed provisioning required before linking");
      var result = new tools.jackson.databind.json.JsonMapper().readValue(
          String.valueOf(op.get("result")), Map.class);
      if (!request.slug().equals(result.get("project_slug"))
          || !request.templateId().equals(result.get("template_id")))
        throw new ApiException(409, "Provisioning result does not match project");
      return "provisioned";
    } catch (HttpClientErrorException e) {
      throw new ApiException(
          e.getStatusCode().value() == 404 ? 404 : 503, "Provisioning verification failed");
    } catch (RestClientException | tools.jackson.core.JacksonException e) {
      throw new ApiException(503, "Orchestrator unavailable or invalid response");
    }
  }
}
