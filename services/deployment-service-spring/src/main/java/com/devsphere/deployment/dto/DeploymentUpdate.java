package com.devsphere.deployment.dto;
import jakarta.validation.constraints.*;
public record DeploymentUpdate(@Size(max = 255) String image, @Min(1) @Max(2) Integer replicas) {}
