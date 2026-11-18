package com.devsphere.deployment.config;
import java.time.Duration;
import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.context.annotation.*;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
@Configuration
public class DiscoveryConfiguration {
  @Bean
  @LoadBalanced
  public RestClient.Builder discoveredClientBuilder() {
    var factory = new JdkClientHttpRequestFactory(
        java.net.http.HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build());
    factory.setReadTimeout(Duration.ofSeconds(5));
    return RestClient.builder().requestFactory(factory);
  }
  @Bean("projectClient")
  public RestClient projectClient(@LoadBalanced RestClient.Builder builder) {
    return builder.build();
  }
}
