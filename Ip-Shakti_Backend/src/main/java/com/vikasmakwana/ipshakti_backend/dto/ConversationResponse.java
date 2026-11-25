package com.vikasmakwana.ipshakti_backend.dto;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record ConversationResponse(
        UUID id,
        Instant createdAt,
        List<ConversationMessageResponse> messages) {
}
