package com.vikasmakwana.ipshakti_backend;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.ai.transformer.splitter.TokenTextSplitter;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Component
public class DataInitializer implements ApplicationRunner {

    private static final Logger logger = LoggerFactory.getLogger(DataInitializer.class);
    private static final int ADD_BATCH_SIZE = 64;

    private final VectorStore vectorStore;
    private final JsonMapper jsonMapper;
    private final Path corpusDirectory;
    private final boolean ingestOnStartup;
    private final TokenTextSplitter textSplitter;

    public DataInitializer(
            VectorStore vectorStore,
            JsonMapper jsonMapper,
            @Value("${app.knowledge-base.corpus-path:../Ayushakti/knowledge-base/corpus}")
            String corpusDirectory,
            @Value("${app.knowledge-base.ingest-on-startup:false}")
            boolean ingestOnStartup) {
        this.vectorStore = vectorStore;
        this.jsonMapper = jsonMapper;
        this.corpusDirectory = Path.of(corpusDirectory).toAbsolutePath().normalize();
        this.ingestOnStartup = ingestOnStartup;
        this.textSplitter = TokenTextSplitter.builder()
                .withChunkSize(400)
                .withMinChunkSizeChars(200)
                .withMinChunkLengthToEmbed(50)
                .withMaxNumChunks(10000)
                .withKeepSeparator(true)
                .build();
    }

    @Override
    public void run(ApplicationArguments args) throws IOException {
        if (!ingestOnStartup) {
            logger.info("Knowledge-base ingestion is disabled. Set app.knowledge-base.ingest-on-startup=true to enable it.");
            return;
        }

        List<Document> documents = loadCorpusDocuments();
        if (documents.isEmpty()) {
            throw new IllegalStateException("No chunks found in corpus directory: " + corpusDirectory);
        }

        for (int start = 0; start < documents.size(); start += ADD_BATCH_SIZE) {
            int end = Math.min(start + ADD_BATCH_SIZE, documents.size());
            vectorStore.add(documents.subList(start, end));
            logger.info("Indexed chunks {}-{} of {}", start + 1, end, documents.size());
        }

        logger.info("Knowledge-base ingestion completed: {} vector chunks", documents.size());
    }

    List<Document> loadCorpusDocuments() throws IOException {
        if (!Files.isDirectory(corpusDirectory)) {
            throw new IOException("Corpus directory does not exist: " + corpusDirectory);
        }

        List<Path> corpusFiles;
        try (var paths = Files.list(corpusDirectory)) {
            corpusFiles = paths
                    .filter(Files::isRegularFile)
                    .filter(path -> path.getFileName().toString().toLowerCase().endsWith(".json"))
                    .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                    .toList();
        }

        if (corpusFiles.isEmpty()) {
            throw new IOException("No corpus JSON files found in: " + corpusDirectory);
        }

        List<Document> indexedChunks = new ArrayList<>();
        for (Path corpusFile : corpusFiles) {
            JsonNode corpus = jsonMapper.readTree(corpusFile);
            JsonNode sourceDocuments = corpus.path("documents");
            if (!sourceDocuments.isArray()) {
                throw new IOException("Missing documents array in corpus file: " + corpusFile);
            }

            String corpusId = textOrDefault(corpus, "corpus_id",
                    removeJsonExtension(corpusFile.getFileName().toString()));
            for (JsonNode sourceDocument : sourceDocuments) {
                appendDocumentChunks(
                        indexedChunks,
                        corpusFile.getFileName().toString(),
                        corpusId,
                        sourceDocument
                );
            }

            logger.info("Loaded corpus file {}: {} chunks so far",
                    corpusFile.getFileName(), indexedChunks.size());
        }

        return indexedChunks;
    }

    private void appendDocumentChunks(
            List<Document> output,
            String corpusFileName,
            String corpusId,
            JsonNode sourceDocument) throws IOException {
        String title = requiredText(sourceDocument, "title", corpusFileName);
        JsonNode chunks = sourceDocument.path("chunks");
        if (!chunks.isArray()) {
            throw new IOException("Missing chunks array for document '" + title + "' in " + corpusFileName);
        }

        String jurisdiction = requiredText(sourceDocument, "jurisdiction", corpusFileName);
        if (!jurisdiction.equals("india") && !jurisdiction.equals("international")) {
            throw new IOException("Unsupported jurisdiction '" + jurisdiction + "' in " + corpusFileName);
        }

        String region = jurisdiction.equals("india")
                ? "india"
                : corpusId.equalsIgnoreCase("eu_herbal") ? "eu" : "international";

        for (int sourceChunkIndex = 0; sourceChunkIndex < chunks.size(); sourceChunkIndex++) {
            JsonNode sourceChunk = chunks.get(sourceChunkIndex);
            String sourceText = requiredText(sourceChunk, "verbatim_text", corpusFileName);
            String sectionIdentifier = textOrDefault(sourceChunk, "section_identifier", "Unlabeled section");
            String chunkTitle = textOrDefault(sourceChunk, "title", sectionIdentifier);
            String sourceUrl = textOrDefault(sourceChunk, "source_url",
                    textOrDefault(sourceDocument, "source_url", ""));
            String retrievalContext = textOrDefault(sourceChunk, "retrieval_context", "");

            Map<String, Object> metadata = createMetadata(
                    sourceDocument,
                    sourceChunk,
                    corpusFileName,
                    corpusId,
                    jurisdiction,
                    region,
                    title,
                    sectionIdentifier,
                    chunkTitle,
                    sourceUrl,
                    retrievalContext,
                    sourceChunkIndex
            );

            String contextualText = buildContextualText(
                    title,
                    sectionIdentifier,
                    retrievalContext,
                    sourceText
            );
            Document toSplit = new Document(contextualText, metadata);
            List<Document> splitDocuments = textSplitter.apply(List.of(toSplit));

            for (int partIndex = 0; partIndex < splitDocuments.size(); partIndex++) {
                String text = splitDocuments.get(partIndex).getText();
                if (text == null || text.isBlank()) {
                    continue;
                }

                Map<String, Object> splitMetadata = new HashMap<>(metadata);
                splitMetadata.put("source_chunk_index", sourceChunkIndex);
                splitMetadata.put("chunk_part", partIndex);

                String stableId = stableId(
                        corpusFileName,
                        title,
                        textOrDefault(sourceDocument, "version_tag", ""),
                        sectionIdentifier,
                        sourceChunkIndex,
                        partIndex
                );
                output.add(new Document(stableId, text, splitMetadata));
            }
        }
    }

    private Map<String, Object> createMetadata(
            JsonNode sourceDocument,
            JsonNode sourceChunk,
            String corpusFileName,
            String corpusId,
            String jurisdiction,
            String region,
            String title,
            String sectionIdentifier,
            String chunkTitle,
            String sourceUrl,
            String retrievalContext,
            int sourceChunkIndex) {
        Map<String, Object> metadata = new HashMap<>();
        metadata.put("corpus_file", corpusFileName);
        metadata.put("corpus_id", corpusId);
        metadata.put("jurisdiction", jurisdiction);
        metadata.put("region", region);
        metadata.put("title", title);
        metadata.put("document_type", textOrDefault(sourceDocument, "document_type", ""));
        metadata.put("authority", textOrDefault(sourceDocument, "authority", ""));
        metadata.put("category", textOrDefault(sourceDocument, "category", ""));
        metadata.put("section_identifier", sectionIdentifier);
        metadata.put("chunk_title", chunkTitle);
        metadata.put("retrieval_context", retrievalContext);
        metadata.put("source_chunk_index", sourceChunkIndex);
        metadata.put("verification_status",
                textOrDefault(sourceDocument, "verification_status", "pending_human_check"));

        putIfPresent(metadata, "source_file", sourceDocument.path("source_file"));
        putIfPresent(metadata, "source_url", sourceUrl);
        putIfPresent(metadata, "version_tag", sourceDocument.path("version_tag"));
        putIfPresent(metadata, "retrieved_date", sourceDocument.path("retrieved_date"));
        putIfPresent(metadata, "page_start", sourceChunk.path("page_start"));
        putIfPresent(metadata, "page_end", sourceChunk.path("page_end"));
        putIfPresent(metadata, "part", sourceChunk.path("part"));
        putIfPresent(metadata, "herb_latin_name", sourceChunk.path("herb_latin_name"));

        return metadata;
    }

    private static String buildContextualText(
            String documentTitle,
            String sectionIdentifier,
            String retrievalContext,
            String sourceText) {
        StringBuilder text = new StringBuilder()
                .append("Document: ").append(documentTitle)
                .append("\nSection: ").append(sectionIdentifier);
        if (!retrievalContext.isBlank()) {
            text.append("\nContext: ").append(retrievalContext);
        }
        return text.append("\n\n").append(sourceText).toString();
    }

    private static String stableId(
            String corpusFileName,
            String title,
            String versionTag,
            String sectionIdentifier,
            int sourceChunkIndex,
            int partIndex) {
        String identity = String.join("|",
                corpusFileName,
                title,
                versionTag,
                sectionIdentifier,
                Integer.toString(sourceChunkIndex),
                Integer.toString(partIndex));
        return UUID.nameUUIDFromBytes(identity.getBytes(StandardCharsets.UTF_8)).toString();
    }

    private static void putIfPresent(Map<String, Object> metadata, String key, JsonNode value) {
        if (value != null && !value.isMissingNode() && !value.isNull() && !value.asText().isBlank()) {
            metadata.put(key, value.isNumber() ? value.numberValue() : value.asText());
        }
    }

    private static void putIfPresent(Map<String, Object> metadata, String key, String value) {
        if (value != null && !value.isBlank()) {
            metadata.put(key, value);
        }
    }

    private static String requiredText(JsonNode node, String field, String fileName) throws IOException {
        String value = textOrDefault(node, field, "");
        if (value.isBlank()) {
            throw new IOException("Missing required '" + field + "' value in " + fileName);
        }
        return value;
    }

    private static String textOrDefault(JsonNode node, String field, String defaultValue) {
        JsonNode value = node.path(field);
        return value.isMissingNode() || value.isNull() ? defaultValue : value.asText(defaultValue);
    }

    private static String removeJsonExtension(String fileName) {
        return fileName.replaceFirst("(?i)\\.json$", "");
    }
}
