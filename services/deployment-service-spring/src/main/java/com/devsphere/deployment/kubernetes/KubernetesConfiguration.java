package com.devsphere.deployment.kubernetes;
import io.fabric8.kubernetes.client.*;
import java.nio.file.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;
@Configuration
public class KubernetesConfiguration {
  @Bean(destroyMethod = "close")
  public KubernetesClient kubernetesClient(@Value("${devsphere.kubeconfig:}") String file)
      throws java.io.IOException {
    // Compose must mount only a namespace-scoped service-account kubeconfig.
    Config config = file.isBlank() ? Config.autoConfigure(null)
                                   : Config.fromKubeconfig(Files.readString(Path.of(file)));
    config.setNamespace("devsphere-apps");
    config.setConnectionTimeout(3000);
    config.setRequestTimeout(8000);
    return new KubernetesClientBuilder()
        .withConfig(config)
        .withHttpClientFactory(new io.fabric8.kubernetes.client.jetty.JettyHttpClientFactory())
        .build();
  }
}
