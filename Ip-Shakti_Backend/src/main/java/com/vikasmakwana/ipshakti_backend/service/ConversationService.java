package com.vikasmakwana.ipshakti_backend.service;

import com.vikasmakwana.ipshakti_backend.dto.ConversationMessageResponse;
import com.vikasmakwana.ipshakti_backend.dto.ConversationResponse;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ConversationService {

    private final JdbcTemplate jdbcTemplate;

    public ConversationService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public UUID getOrCreateConversation(UUID userId, String conversationId) {
        if (conversationId == null || conversationId.isBlank()) {
            UUID newId = UUID.randomUUID();
            jdbcTemplate.update("INSERT INTO conversations (id, user_id) VALUES (?, ?)", newId, userId);
            return newId;
        }

        UUID id;
        try {
            id = UUID.fromString(conversationId);
        } catch (IllegalArgumentException exception) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "conversationId must be a UUID.");
        }

        Integer ownedCount = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM conversations WHERE id = ? AND user_id = ?",
                Integer.class,
                id,
                userId);
        if (ownedCount == null || ownedCount == 0) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Conversation not found.");
        }
        return id;
    }

    public void addMessage(UUID conversationId, String role, String content) {
        jdbcTemplate.update(
                "INSERT INTO chat_messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
                UUID.randomUUID(),
                conversationId,
                role,
                content);
    }

    public List<ConversationResponse> getConversations(UUID userId) {
        return jdbcTemplate.query(
                """
                SELECT c.id AS conversation_id,
                       c.created_at AS conversation_created_at,
                       m.id AS message_id,
                       m.role AS message_role,
                       m.content AS message_content,
                       m.created_at AS message_created_at
                FROM conversations c
                LEFT JOIN chat_messages m ON m.conversation_id = c.id
                WHERE c.user_id = ?
                ORDER BY c.created_at DESC, m.created_at ASC
                """,
                resultSet -> {
                    Map<UUID, ConversationBuilder> conversations = new LinkedHashMap<>();
                    while (resultSet.next()) {
                        UUID conversationId = resultSet.getObject("conversation_id", UUID.class);
                        ConversationBuilder conversation = conversations.get(conversationId);
                        if (conversation == null) {
                            conversation = new ConversationBuilder(
                                    conversationId,
                                    toInstant(resultSet.getTimestamp("conversation_created_at")));
                            conversations.put(conversationId, conversation);
                        }
                        UUID messageId = resultSet.getObject("message_id", UUID.class);
                        if (messageId != null) {
                            conversation.messages.add(new ConversationMessageResponse(
                                    messageId,
                                    resultSet.getString("message_role"),
                                    resultSet.getString("message_content"),
                                    toInstant(resultSet.getTimestamp("message_created_at"))));
                        }
                    }
                    return conversations.values().stream()
                            .map(conversation -> new ConversationResponse(
                                    conversation.id,
                                    conversation.createdAt,
                                    List.copyOf(conversation.messages)))
                            .toList();
                },
                userId);
    }

    private static Instant toInstant(Timestamp timestamp) {
        return timestamp == null ? null : timestamp.toInstant();
    }

    private static final class ConversationBuilder {
        private final UUID id;
        private final Instant createdAt;
        private final List<ConversationMessageResponse> messages = new ArrayList<>();

        private ConversationBuilder(UUID id, Instant createdAt) {
            this.id = id;
            this.createdAt = createdAt;
        }
    }
}
