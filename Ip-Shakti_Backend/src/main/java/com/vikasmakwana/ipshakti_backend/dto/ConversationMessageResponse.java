package com.vikasmakwana.ipshakti_backend.dto;

import java.time.Instant;
import java.util.UUID;

public record ConversationMessageResponse(
        UUID id,
        String role,
        String content,
        Instant createdAt) {
}
