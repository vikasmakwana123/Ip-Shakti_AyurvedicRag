package com.vikasmakwana.ipshakti_backend.config;

import com.vikasmakwana.ipshakti_backend.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.util.UUID;

@Component
public class AuthInterceptor implements HandlerInterceptor {

    public static final String USER_ID_ATTRIBUTE = "authenticatedUserId";
    private final AuthService authService;

    public AuthInterceptor(AuthService authService) {
        this.authService = authService;
    }

    @Override
    public boolean preHandle(
            HttpServletRequest request,
            HttpServletResponse response,
            Object handler) throws IOException {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }

        String authorization = request.getHeader("Authorization");
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "A valid bearer token is required.");
            return false;
        }

        String token = authorization.substring("Bearer ".length()).trim();
        UUID userId = token.isEmpty() ? null : authService.findUserIdForToken(token);
        if (userId == null) {
            response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "The bearer token is invalid or expired.");
            return false;
        }

        request.setAttribute(USER_ID_ATTRIBUTE, userId);
        return true;
    }
}
