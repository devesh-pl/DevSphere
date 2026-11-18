package com.devsphere.common;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.*;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.*;
@Configuration
@Import(ApiErrors.class)
public class AuthConfiguration {
  private static final org.slf4j.Logger LOG =
      org.slf4j.LoggerFactory.getLogger(AuthConfiguration.class);
  @Bean
  public RestClient authClient(@Value("${devsphere.auth-url:http://localhost:8001}") String url) {
    var factory = new JdkClientHttpRequestFactory(
        java.net.http.HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build());
    factory.setReadTimeout(Duration.ofSeconds(5));
    return RestClient.builder().baseUrl(url).requestFactory(factory).build();
  }
  @Bean
  public FilterRegistrationBean<Filter> authFilter(RestClient authClient) {
    Filter filter = (request, response, chain) -> {
      var req = (HttpServletRequest) request;
      var res = (HttpServletResponse) response;
      String path = req.getRequestURI();
      if (path.equals("/health") || path.equals("/ready") || path.equals("/actuator/health")
          || path.startsWith("/actuator/health/") || path.equals("/actuator/info")
          || path.equals("/actuator/prometheus")) {
        chain.doFilter(req, res);
        return;
      }
      String header = req.getHeader("Authorization");
      if (header == null || !header.startsWith("Bearer ") || header.length() < 8) {
        reject(res, 401, "Authentication required");
        return;
      }
      AuthUser user;
      try {
        var data = authClient.get()
                       .uri("/auth/me")
                       .header("Authorization", header)
                       .retrieve()
                       .body(Map.class);
        if (data == null || !Boolean.TRUE.equals(data.get("is_active"))) {
          reject(res, 401, "Inactive or invalid account");
          return;
        }
        String role = String.valueOf(data.get("role"));
        if (!role.equals("developer") && !role.equals("admin")) {
          reject(res, 403, "Developer access required");
          return;
        }
        user = new AuthUser(UUID.fromString(String.valueOf(data.get("id"))), role);
      } catch (HttpClientErrorException e) {
        reject(res,
            e.getStatusCode().value() == 401 || e.getStatusCode().value() == 403 ? 401 : 503,
            "Authentication failed");
        return;
      } catch (RestClientException | IllegalArgumentException e) {
        // Log only failure categories, never credentials or the Auth response body.
        Throwable cause = e;
        var categories = new java.util.ArrayList<String>();
        for (int i = 0; cause != null && i < 4; i++, cause = cause.getCause())
          categories.add(cause.getClass().getSimpleName());
        LOG.warn("Authentication dependency failed: {}", String.join(" -> ", categories));
        reject(res, 503, "Authentication service unavailable");
        return;
      }
      req.setAttribute("user", user);
      chain.doFilter(req, res);
    };
    var registration = new FilterRegistrationBean<>(filter);
    registration.setOrder(1);
    return registration;
  }
  private static void reject(HttpServletResponse response, int status, String detail)
      throws IOException {
    response.setStatus(status);
    response.setContentType("application/json");
    if (status == 401)
      response.setHeader("WWW-Authenticate", "Bearer");
    response.getWriter().write("{\"detail\":\"" + detail + "\"}");
  }
}
