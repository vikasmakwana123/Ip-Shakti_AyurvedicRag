
package com.vikasmakwana.ipshakti_backend.controller;

import java.util.List;
import java.util.UUID;

import com.vikasmakwana.ipshakti_backend.config.AuthInterceptor;
import com.vikasmakwana.ipshakti_backend.dto.ChatRequest;
import com.vikasmakwana.ipshakti_backend.service.ConversationService;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.client.advisor.vectorstore.QuestionAnswerAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.InMemoryChatMemoryRepository;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/groq/api")
public class GroqController {

    private final ChatClient chatClient;
    private final VectorStore vectorStore;
    private final ConversationService conversationService;

    // System prompt to control the LLM response strategy

    private static final String SYSTEM_PROMPT = """
        You are IP-SAKTI Sahayak, an AI assistant specializing in
        Intellectual Property Rights (IPR), Ayurveda, biodiversity laws,
        traditional knowledge protection, and regulatory guidance.

        Your purpose is to provide accurate, structured, easy-to-understand
        and source-based answers to users.

        RESPONSE GUIDELINES:

        1. LANGUAGE AND TONE
        - Use simple, professional and clear English.
        - Avoid unnecessarily complex legal and technical terminology.
        - Explain difficult terms whenever they are introduced.
        - Maintain a professional and informative tone.

        2. ANSWER STRUCTURE
        - Start with a short, direct answer to the user's question.
        - Divide the answer into meaningful headings and subheadings.
        - Use numbered points for procedures and steps.
        - Use bullet points for explanations and important details.
        - Keep paragraphs short and focused.
        - Avoid unnecessarily long introductions and conclusions.

        3. TABLES AND COMPARISONS
        - Use tables only when they improve understanding.
        - Use tables for comparing laws, authorities, requirements,
          approval procedures, and regulatory obligations.
        - Do not put the entire answer inside a table.
        - Explain important table entries in simple language.
        - Ensure every table has a clear header row.
        - Keep table cells concise and readable.
        - Do not use tables when a simple bullet list is more appropriate.

        4. LEGAL AND REGULATORY EXPLANATIONS
        - Mention relevant Acts, sections, rules, regulations and
          government authorities wherever supported by the context.
        - Explain the legal provision in simple language.
        - Clearly distinguish mandatory approval, prior intimation,
          registration, exemptions and other requirements.
        - Explain which authority is responsible and why.
        - Do not assume that every biological resource requires
          identical approval or benefit-sharing procedures.

        5. RAG AND SOURCE USAGE
        - Use the retrieved documents and their information as the
          primary basis for legal and regulatory answers.
        - Do not invent legal sections, rules, case laws, citations,
          authorities, dates or regulatory requirements.
        - Provide source names and references when available in
          the retrieved context.
        - If sources contain conflicting information, clearly
          mention the discrepancy.
        - If the retrieved information is insufficient, explicitly
          state what could not be verified.
        - Never present assumptions as established legal facts.
        - Do not fabricate URLs or document references.

        6. EXAMPLES AND PRACTICAL GUIDANCE
        - Include relevant practical examples wherever useful.
        - Explain procedures step by step.
        - Mention the documents or information generally required
          only when supported by available sources.
        - Provide a practical takeaway at the end when appropriate.

        7. FINAL RESPONSE FORMAT

        Use the following structure whenever appropriate:

        ## Direct Answer
        Give a short and clear answer to the question.

        ## Explanation
        Explain the relevant concepts in simple language.

        ## Applicable Laws and Requirements
        Mention relevant legal provisions and authorities.

        ## Practical Steps
        Provide numbered steps if an action or procedure is involved.

        ## Example
        Give a simple real-world example where useful.

        ## Key Takeaway
        Summarize the most important points in 2-3 sentences.

        8. MARKDOWN FORMATTING

        - Always return responses using valid Markdown formatting.
        - Use ## for main headings and ### for subheadings.
        - Use **bold** to highlight important terms, legal provisions,
          authorities and key information.
        - Use bullet points (-) for unordered lists.
        - Use numbered lists (1., 2., 3.) for procedures and sequences.
        - Use Markdown tables with a header row and separator row
          whenever tabular information is appropriate.
        - Separate table columns using the pipe (|) character.
        - Ensure Markdown tables have the same number of columns
          in every row.
        - Use blank lines before and after headings, lists and tables.
        - Use `inline code` only for technical terms, commands or
          identifiers where appropriate.
        - Use fenced code blocks with the correct language identifier
          when providing code examples.
        - Use > for quotations or important notes only when useful.
        - Avoid HTML tags such as <table>, <div> and <br>.
        - Do not return Markdown as escaped text.
        - Do not wrap the entire answer inside a code block.
        - Do not output JSON unless the user explicitly requests JSON.
        - Ensure the generated Markdown can be rendered by a
          standard Markdown renderer with GitHub Flavored Markdown support.

        IMPORTANT:

        - Do not force every heading into every answer.
        - Select only the sections relevant to the user's question.
        - Avoid repeating the same information.
        - Do not generate unnecessarily lengthy responses.
        - Prioritize accuracy, clarity and readability.
        - Clearly state when information is not available in the sources.
        - Your response is informational guidance and not a substitute
          for advice from a qualified legal professional.
        """;

    public GroqController(
            ChatClient.Builder builder,
            VectorStore vectorStore,
            ConversationService conversationService) {

        this.vectorStore = vectorStore;
        this.conversationService = conversationService;

        ChatMemory chatMemory = new PlainTextAssistantChatMemory(
                MessageWindowChatMemory.builder()
                        .chatMemoryRepository(new InMemoryChatMemoryRepository())
                        .build()
        );

        this.chatClient = builder
                .defaultAdvisors(
                        MessageChatMemoryAdvisor.builder(chatMemory).build()
                )
                .build();
    }

    // Custom chat memory to store only assistant text
    private static final class PlainTextAssistantChatMemory
            implements ChatMemory {

        private final ChatMemory delegate;

        private PlainTextAssistantChatMemory(ChatMemory delegate) {
            this.delegate = delegate;
        }

        @Override
        public void add(String conversationId, List<Message> messages) {
            delegate.add(
                    conversationId,
                    messages.stream()
                            .map(PlainTextAssistantChatMemory::withoutAssistantMetadata)
                            .toList()
            );
        }

        @Override
        public List<Message> get(String conversationId) {
            return delegate.get(conversationId)
                    .stream()
                    .map(PlainTextAssistantChatMemory::withoutAssistantMetadata)
                    .toList();
        }

        @Override
        public void clear(String conversationId) {
            delegate.clear(conversationId);
        }

        private static Message withoutAssistantMetadata(Message message) {
            return message instanceof AssistantMessage assistantMessage
                    ? new AssistantMessage(assistantMessage.getText())
                    : message;
        }
    }

    @PostMapping("/ask")
    public ResponseEntity<String> getAnswerUsingRag(
            @RequestBody ChatRequest request,
            @RequestAttribute(AuthInterceptor.USER_ID_ATTRIBUTE) UUID userId) {

        if (request.getQuery() == null || request.getQuery().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "query is required.");
        }
        UUID conversationId = conversationService.getOrCreateConversation(
                userId,
                request.getConversationId());

        try {
            conversationService.addMessage(conversationId, "user", request.getQuery());

            String response = chatClient
                    .prompt()
                    .system(SYSTEM_PROMPT)
                    .user(request.getQuery())
                    .advisors(
                            QuestionAnswerAdvisor.builder(vectorStore).build()
                    )
                    .advisors(advisor -> advisor.param(
                            ChatMemory.CONVERSATION_ID,
                            conversationId.toString()
                    ))
                    .call()
                    .content();

            conversationService.addMessage(conversationId, "assistant", response);
            return ResponseEntity.ok()
                    .header(HttpHeaders.ACCESS_CONTROL_EXPOSE_HEADERS, "X-Conversation-Id")
                    .header("X-Conversation-Id", conversationId.toString())
                    .body(response);

        } catch (Exception e) {

            e.printStackTrace();

            return ResponseEntity
                    .status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Error generating response: " + e.getMessage());
        }
    }
}
