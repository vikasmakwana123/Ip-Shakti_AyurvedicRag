package com.vikasmakwana.ipshakti_backend.service;

import com.vikasmakwana.ipshakti_backend.dto.RegisterRequest;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;

class AuthServiceTests {

    @Test
    void acceptsSixCharacterPassword() {
        AuthService authService = new AuthService(
                mock(JdbcTemplate.class),
                new PasswordHasher());

        assertNotNull(authService.register(
                new RegisterRequest("Example User", "user@example.com", "123456")));
    }

    @Test
    void rejectsPasswordShorterThanSixCharacters() {
        AuthService authService = new AuthService(
                mock(JdbcTemplate.class),
                new PasswordHasher());

        assertThrows(ResponseStatusException.class, () -> authService.register(
                new RegisterRequest("Example User", "user@example.com", "12345")));
    }
}
