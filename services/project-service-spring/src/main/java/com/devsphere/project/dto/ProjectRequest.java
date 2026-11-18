package com.devsphere.project.dto;
import jakarta.validation.constraints.*;
import java.util.UUID;
public record ProjectRequest(@NotBlank @Size(max = 100) String name,
    @NotBlank @Size(min = 3, max = 40) @Pattern(regexp = "[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
    String slug, @NotNull @Size(max = 4000) String description,
    @NotBlank @Pattern(regexp = "fastapi-basic|express-basic") String templateId,
    UUID provisioningOperationId) {}
