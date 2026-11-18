package com.devsphere.deployment;
import com.devsphere.common.AuthConfiguration;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;
import org.springframework.scheduling.annotation.EnableScheduling;
@SpringBootApplication
@EnableScheduling
@Import(AuthConfiguration.class)
public class DeploymentApplication {
  public static void main(String[] args) {
    SpringApplication.run(DeploymentApplication.class, args);
  }
}
