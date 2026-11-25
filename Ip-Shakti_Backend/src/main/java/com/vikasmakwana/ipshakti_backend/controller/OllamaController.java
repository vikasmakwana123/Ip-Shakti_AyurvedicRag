package com.vikasmakwana.ipshakti_backend.controller;

import com.vikasmakwana.ipshakti_backend.config.AuthInterceptor;
import com.vikasmakwana.ipshakti_backend.dto.ChatRequest;
import com.vikasmakwana.ipshakti_backend.service.ConversationService;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.vectorstore.QuestionAnswerAdvisor;
import org.springframework.ai.ollama.OllamaChatModel;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/ollama/api")
public class OllamaController {
    private final ChatClient chatClient;
    private final VectorStore vectorStore;
    private final ConversationService conversationService;

    public OllamaController(
            OllamaChatModel chatModel,
            VectorStore vectorStore,
            ConversationService conversationService) {

        this.chatClient = ChatClient.create(chatModel);
        this.vectorStore = vectorStore;
        this.conversationService = conversationService;
    }

    @PostMapping("/ask")
    public ResponseEntity<String> askModel(
            @RequestBody ChatRequest request,
            @RequestAttribute(AuthInterceptor.USER_ID_ATTRIBUTE) UUID userId) {
        if (request.getQuery() == null || request.getQuery().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "query is required.");
        }
        UUID conversationId = conversationService.getOrCreateConversation(
                userId,
                request.getConversationId());
        conversationService.addMessage(conversationId, "user", request.getQuery());

        String response = chatClient
                .prompt(request.getQuery())
                .advisors(QuestionAnswerAdvisor.builder(vectorStore).build())
                .call()
                .content();
        conversationService.addMessage(conversationId, "assistant", response);

        return ResponseEntity.ok()
                .header(HttpHeaders.ACCESS_CONTROL_EXPOSE_HEADERS, "X-Conversation-Id")
                .header("X-Conversation-Id", conversationId.toString())
                .body(response);
    }
}
