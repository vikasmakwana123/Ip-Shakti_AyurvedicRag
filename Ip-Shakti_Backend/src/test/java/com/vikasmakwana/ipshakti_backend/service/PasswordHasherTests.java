package com.vikasmakwana.ipshakti_backend.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PasswordHasherTests {

    private final PasswordHasher passwordHasher = new PasswordHasher();

    @Test
    void hashesPasswordsWithUniqueSaltsAndVerifiesCredentials() {
        String firstHash = passwordHasher.hash("correct horse battery");
        String secondHash = passwordHasher.hash("correct horse battery");

        assertNotEquals(firstHash, secondHash);
        assertTrue(passwordHasher.matches("correct horse battery", firstHash));
        assertFalse(passwordHasher.matches("incorrect password", firstHash));
    }
}
