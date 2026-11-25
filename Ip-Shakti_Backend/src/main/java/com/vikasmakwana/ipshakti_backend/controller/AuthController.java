package com.vikasmakwana.ipshakti_backend.controller;

import com.vikasmakwana.ipshakti_backend.dto.AuthResponse;
import com.vikasmakwana.ipshakti_backend.dto.ConversationResponse;
import com.vikasmakwana.ipshakti_backend.dto.LoginRequest;
import com.vikasmakwana.ipshakti_backend.dto.RegisterRequest;
import com.vikasmakwana.ipshakti_backend.service.AuthService;
import com.vikasmakwana.ipshakti_backend.service.ConversationService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api")
public class AuthController {

    private final AuthService authService;
    private final ConversationService conversationService;

    public AuthController(AuthService authService, ConversationService conversationService) {
        this.authService = authService;
        this.conversationService = conversationService;
    }

    @PostMapping("/register")
    public AuthResponse register(@RequestBody RegisterRequest request) {
        return authService.register(request);
    }

    @PostMapping("/login")
    public AuthResponse login(@RequestBody LoginRequest request) {
        return authService.login(request);
    }

    @GetMapping("/conversations")
    public List<ConversationResponse> getConversations(
            @RequestAttribute("authenticatedUserId") UUID userId) {
        return conversationService.getConversations(userId);
    }
}
