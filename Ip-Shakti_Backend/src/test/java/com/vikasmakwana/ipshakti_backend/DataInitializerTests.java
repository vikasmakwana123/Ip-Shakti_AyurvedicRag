package com.vikasmakwana.ipshakti_backend;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.ai.document.Document;
import tools.jackson.databind.json.JsonMapper;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DataInitializerTests {

    @TempDir
    Path corpusDirectory;

    @Test
    void splitsCorpusSectionsAndKeepsJurisdictionAndCitationMetadata() throws Exception {
        JsonMapper jsonMapper = JsonMapper.builder().build();
        writeCorpus(
                jsonMapper,
                "india.json",
                "india",
                "india",
                "india_statute",
                "Indian test law",
                "Section 1",
                "https://example.test/india",
                repeatedLegalText()
        );
        writeCorpus(
                jsonMapper,
                "eu_herbal.json",
                "eu_herbal",
                "international",
                "herbal",
                "EU test monograph",
                "Section 4.2 (p. 3)",
                "https://example.test/eu",
                repeatedLegalText()
        );

        DataInitializer initializer = new DataInitializer(
                null,
                jsonMapper,
                corpusDirectory.toString(),
                false
        );

        List<Document> documents = initializer.loadCorpusDocuments();
        List<Document> repeatedLoad = initializer.loadCorpusDocuments();

        assertTrue(documents.size() > 2, "Long sections should be split into multiple embedding chunks");
        assertEquals(documents.size(), repeatedLoad.size());
        assertEquals(
                documents.stream().map(Document::getId).toList(),
                repeatedLoad.stream().map(Document::getId).toList(),
                "Chunk IDs should be stable across ingestion runs"
        );
        assertTrue(documents.stream().allMatch(document -> {
            try {
                UUID.fromString(document.getId());
                return true;
            } catch (IllegalArgumentException exception) {
                return false;
            }
        }));

        Map<?, ?> indiaMetadata = documents.stream()
                .map(Document::getMetadata)
                .filter(metadata -> "india".equals(metadata.get("jurisdiction")))
                .findFirst()
                .orElseThrow();
        assertEquals("india", indiaMetadata.get("region"));
        assertEquals("https://example.test/india", indiaMetadata.get("source_url"));
        assertEquals("Section 1", indiaMetadata.get("section_identifier"));

        Map<?, ?> euMetadata = documents.stream()
                .map(Document::getMetadata)
                .filter(metadata -> "international".equals(metadata.get("jurisdiction")))
                .findFirst()
                .orElseThrow();
        assertEquals("eu", euMetadata.get("region"));
        assertEquals("https://example.test/eu", euMetadata.get("source_url"));
        assertNotEquals(indiaMetadata.get("corpus_id"), euMetadata.get("corpus_id"));
        assertFalse(documents.stream().anyMatch(document ->
                document.getMetadata().get("jurisdiction") == null));
    }

    private void writeCorpus(
            JsonMapper jsonMapper,
            String fileName,
            String corpusId,
            String jurisdiction,
            String category,
            String title,
            String sectionIdentifier,
            String sourceUrl,
            String sourceText) throws Exception {
        Map<String, Object> chunk = Map.of(
                "section_identifier", sectionIdentifier,
                "title", "Test section",
                "source_url", sourceUrl,
                "verbatim_text", sourceText,
                "retrieval_context", "test context"
        );
        Map<String, Object> document = Map.of(
                "title", title,
                "document_type", "statute",
                "jurisdiction", jurisdiction,
                "category", category,
                "source_url", sourceUrl,
                "version_tag", "test-version",
                "verification_status", "pending_human_check",
                "chunks", List.of(chunk)
        );
        Map<String, Object> corpus = Map.of(
                "corpus_id", corpusId,
                "documents", List.of(document)
        );
        jsonMapper.writeValue(corpusDirectory.resolve(fileName), corpus);
    }

    private static String repeatedLegalText() {
        return "This statutory provision describes the rules, conditions, and obligations "
                .repeat(1200);
    }
}
