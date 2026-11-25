package com.vikasmakwana.ipshakti_backend.service;

import com.vikasmakwana.ipshakti_backend.dto.AuthResponse;
import com.vikasmakwana.ipshakti_backend.dto.LoginRequest;
import com.vikasmakwana.ipshakti_backend.dto.RegisterRequest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.sql.Timestamp;
import java.util.Base64;
import java.util.HexFormat;
import java.util.UUID;

@Service
public class AuthService {

    private static final int SESSION_DAYS = 30;
    private final JdbcTemplate jdbcTemplate;
    private final PasswordHasher passwordHasher;
    private final SecureRandom secureRandom = new SecureRandom();

    public AuthService(JdbcTemplate jdbcTemplate, PasswordHasher passwordHasher) {
        this.jdbcTemplate = jdbcTemplate;
        this.passwordHasher = passwordHasher;
    }

    public AuthResponse register(RegisterRequest request) {
        String name = request.name() == null ? "" : request.name().trim();
        String email = normalizeEmail(request.email());
        String password = request.password();
        if (name.isBlank() || name.length() > 200 || !isValidEmail(email)
                || password == null || password.length() < 6 || password.length() > 200) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "Provide a name, valid email, and password between 6 and 200 characters.");
        }

        UUID userId = UUID.randomUUID();
        try {
            jdbcTemplate.update(
                    "INSERT INTO users (id, name, email, password_hash) VALUES (?, ?, ?, ?)",
                    userId, name, email, passwordHasher.hash(password));
        } catch (DuplicateKeyException exception) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "An account with this email already exists.");
        }
        return createSession(userId, name, email);
    }

    public AuthResponse login(LoginRequest request) {
        String email = normalizeEmail(request.email());
        String password = request.password();
        if (!isValidEmail(email) || password == null || password.isEmpty()) {
            throw invalidCredentials();
        }

        return jdbcTemplate.query(
                "SELECT id, name, email, password_hash FROM users WHERE email = ?",
                resultSet -> {
                    if (!resultSet.next()
                            || !passwordHasher.matches(password, resultSet.getString("password_hash"))) {
                        throw invalidCredentials();
                    }
                    return createSession(
                            resultSet.getObject("id", UUID.class),
                            resultSet.getString("name"),
                            resultSet.getString("email"));
                },
                email);
    }

    public UUID findUserIdForToken(String token) {
        String tokenHash = sha256(token);
        return jdbcTemplate.query(
                "SELECT user_id FROM user_sessions WHERE token_hash = ? AND expires_at > CURRENT_TIMESTAMP",
                resultSet -> resultSet.next() ? resultSet.getObject("user_id", UUID.class) : null,
                tokenHash);
    }

    private AuthResponse createSession(UUID userId, String name, String email) {
        byte[] tokenBytes = new byte[32];
        secureRandom.nextBytes(tokenBytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(tokenBytes);
        Instant expiresAt = Instant.now().plus(SESSION_DAYS, ChronoUnit.DAYS);
        jdbcTemplate.update(
                "INSERT INTO user_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                sha256(token), userId, Timestamp.from(expiresAt));
        return new AuthResponse(userId, name, email, token, "Bearer", expiresAt);
    }

    private static String normalizeEmail(String email) {
        return email == null ? "" : email.trim().toLowerCase(java.util.Locale.ROOT);
    }

    private static boolean isValidEmail(String email) {
        return email.length() <= 320 && email.matches("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
    }

    private static ResponseStatusException invalidCredentials() {
        return new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid email or password.");
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
