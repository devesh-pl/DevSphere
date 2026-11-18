package com.devsphere.common;
import java.util.Map;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
@RestControllerAdvice
public class ApiErrors {
  @ExceptionHandler(ApiException.class)
  public ResponseEntity<?> api(ApiException e) {
    return ResponseEntity.status(e.status).body(Map.of("detail", e.getMessage()));
  }
  @ExceptionHandler(
      {MethodArgumentNotValidException.class, MethodArgumentTypeMismatchException.class,
          org.springframework.http.converter.HttpMessageNotReadableException.class})
  public ResponseEntity<?> invalid(Exception e) {
    return ResponseEntity.badRequest().body(Map.of("detail", "Invalid request fields"));
  }
  @ExceptionHandler(DataIntegrityViolationException.class)
  public ResponseEntity<?> duplicate(Exception e) {
    return ResponseEntity.status(409).body(
        Map.of("detail", "Record conflicts with an existing record"));
  }
}
