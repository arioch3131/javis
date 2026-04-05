import unittest
from unittest.mock import Mock, patch, MagicMock
import re
import logging

from ai_content_classifier.services.llm.category_analyzer import (
    CategoryAnalyzer,
    CategoryExtractionConfig,
    CategoryExtractionResult,
)


# Mock LoggableMixin pour les tests
class MockLoggableMixin:
    def __init_logger__(self, log_level):
        self.logger = MagicMock()


class TestCategoryExtractionConfig(unittest.TestCase):
    """Tests pour la classe CategoryExtractionConfig."""

    def test_default_initialization(self):
        """Test l'initialisation par défaut de la configuration."""
        config = CategoryExtractionConfig()

        # Vérification des valeurs par défaut
        self.assertIsInstance(config.explicit_patterns, list)
        self.assertIsInstance(config.emphasis_patterns, list)
        self.assertIsInstance(config.positive_context_patterns, list)
        self.assertIsInstance(config.negative_patterns, list)
        self.assertEqual(config.min_confidence_score, 0.3)
        self.assertEqual(config.max_category_length, 50)

        # Vérification que les listes ne sont pas vides
        self.assertGreater(len(config.explicit_patterns), 0)
        self.assertGreater(len(config.emphasis_patterns), 0)
        self.assertGreater(len(config.positive_context_patterns), 0)
        self.assertGreater(len(config.negative_patterns), 0)

    def test_custom_initialization(self):
        """Test l'initialisation avec des valeurs personnalisées."""
        custom_patterns = ["test_pattern"]
        config = CategoryExtractionConfig(
            explicit_patterns=custom_patterns,
            min_confidence_score=0.5,
            max_category_length=100,
        )

        self.assertEqual(config.explicit_patterns, custom_patterns)
        self.assertEqual(config.min_confidence_score, 0.5)
        self.assertEqual(config.max_category_length, 100)


class TestCategoryExtractionResult(unittest.TestCase):
    """Tests pour la classe CategoryExtractionResult."""

    def test_initialization(self):
        """Test l'initialisation du résultat d'extraction."""
        result = CategoryExtractionResult(
            category="test_category",
            confidence=0.8,
            method="test_method",
            details="test_details",
        )

        self.assertEqual(result.category, "test_category")
        self.assertEqual(result.confidence, 0.8)
        self.assertEqual(result.method, "test_method")
        self.assertEqual(result.details, "test_details")

    def test_default_details(self):
        """Test l'initialisation avec details par défaut."""
        result = CategoryExtractionResult(
            category="test_category", confidence=0.8, method="test_method"
        )

        self.assertEqual(result.details, "")


class TestCategoryAnalyzer(unittest.TestCase):
    """Tests pour la classe CategoryAnalyzer."""

    def setUp(self):
        """Configuration initiale pour chaque test."""
        # Configuration de test
        self.test_config = CategoryExtractionConfig(
            explicit_patterns=[
                r"(?:the\s+)?category(?:\s+is)?:?\s*(\w+)",  # Capture seulement un mot
                r"(?:the\s+)?category\s+is\s+(\w+)",  # Pattern spécifique pour "category is X"
                r"classification(?:\s+is)?:?\s*(\w+)",  # Pattern pour classification
            ],
            emphasis_patterns=[r"\*\*([^*]+)\*\*", r'"([^"]+)"'],
            positive_context_patterns=[
                r"this\s+is\s+(\w+)",
                r"appears\s+to\s+be\s+(\w+)",
            ],
            negative_patterns=[r"not\s+(\w+)", r"isn't\s+(\w+)"],
            min_confidence_score=0.3,
            max_category_length=30,
        )

        # Catégories de test
        self.test_categories = [
            "sports",
            "technology",
            "health",
            "education",
            "entertainment",
        ]

        # Créer l'analyzer et mock le logger après création
        self.analyzer = CategoryAnalyzer(
            config=self.test_config, log_level=logging.DEBUG
        )
        # Forcer l'assignation du logger mock
        self.analyzer.logger = MagicMock()

    def tearDown(self):
        """Nettoyage après chaque test."""
        pass

    # === TESTS D'INITIALISATION ===

    def test_initialization_with_config(self):
        """Test l'initialisation avec une configuration personnalisée."""
        analyzer = CategoryAnalyzer(config=self.test_config)

        self.assertEqual(analyzer.config, self.test_config)
        self.assertIsNotNone(analyzer._compiled_patterns)
        self.assertIn("explicit", analyzer._compiled_patterns)
        self.assertIn("emphasis", analyzer._compiled_patterns)
        self.assertIn("positive_context", analyzer._compiled_patterns)
        self.assertIn("negative", analyzer._compiled_patterns)

    def test_initialization_without_config(self):
        """Test l'initialisation sans configuration (utilise la config par défaut)."""
        analyzer = CategoryAnalyzer()

        self.assertIsInstance(analyzer.config, CategoryExtractionConfig)
        self.assertIsNotNone(analyzer._compiled_patterns)
        self.assertIsNotNone(analyzer.logger)  # Vérifier que le logger existe

    def test_initialization_with_log_level(self):
        """Test l'initialisation avec un niveau de log spécifique."""
        analyzer = CategoryAnalyzer(log_level=logging.ERROR)

        # Vérifier que l'analyzer a bien été créé avec un logger
        self.assertIsNotNone(analyzer.logger)

    # === TESTS DE COMPILATION DES PATTERNS ===

    def test_compile_patterns_success(self):
        """Test la compilation réussie des patterns regex."""
        self.analyzer._compile_patterns()

        # Vérifier que tous les groupes de patterns sont compilés
        expected_groups = ["explicit", "emphasis", "positive_context", "negative"]
        for group in expected_groups:
            self.assertIn(group, self.analyzer._compiled_patterns)
            self.assertIsInstance(self.analyzer._compiled_patterns[group], list)
            self.assertGreater(len(self.analyzer._compiled_patterns[group]), 0)

    @patch("re.compile")
    def test_compile_patterns_with_invalid_regex(self, mock_compile):
        """Test la compilation avec un pattern regex invalide."""
        # Configuration simple : premier appel échoue, les autres réussissent
        mock_compile.side_effect = [re.error("Invalid regex")] + [MagicMock()] * 50

        # Créer un analyzer avec un pattern invalide simple
        test_config = CategoryExtractionConfig(explicit_patterns=["invalid[regex"])

        # Créer l'analyzer - l'erreur devrait être gérée sans exception
        analyzer = CategoryAnalyzer(config=test_config)

        # Vérifier que l'analyzer a été créé malgré l'erreur
        self.assertIsInstance(analyzer, CategoryAnalyzer)

        # Vérifier que la liste explicit contient moins d'éléments à cause de l'erreur
        self.assertEqual(len(analyzer._compiled_patterns["explicit"]), 0)

    # === TESTS DE VALIDATION D'ENTRÉE ===

    def test_validate_inputs_valid(self):
        """Test la validation avec des entrées valides."""
        result = self.analyzer._validate_inputs("test response", self.test_categories)
        self.assertTrue(result)

    def test_validate_inputs_empty_response(self):
        """Test la validation avec une réponse vide."""
        result = self.analyzer._validate_inputs("", self.test_categories)
        self.assertFalse(result)
        self.analyzer.logger.warning.assert_called()

    def test_validate_inputs_none_response(self):
        """Test la validation avec une réponse None."""
        result = self.analyzer._validate_inputs(None, self.test_categories)
        self.assertFalse(result)

    def test_validate_inputs_non_string_response(self):
        """Test la validation avec une réponse non-string."""
        result = self.analyzer._validate_inputs(123, self.test_categories)
        self.assertFalse(result)

    def test_validate_inputs_empty_categories(self):
        """Test la validation avec des catégories vides."""
        result = self.analyzer._validate_inputs("test response", [])
        self.assertFalse(result)

    def test_validate_inputs_none_categories(self):
        """Test la validation avec des catégories None."""
        result = self.analyzer._validate_inputs("test response", None)
        self.assertFalse(result)

    def test_validate_inputs_invalid_categories(self):
        """Test la validation avec des catégories invalides."""
        invalid_categories = ["valid", "", None, 123]
        result = self.analyzer._validate_inputs("test response", invalid_categories)
        self.assertFalse(result)

    # === TESTS D'EXTRACTION AVEC CONFIDENCE ===

    def test_extract_category_with_confidence_explicit_statement(self):
        """Test l'extraction par déclaration explicite."""
        response_text = "The category is technology"
        result = self.analyzer.extract_category_with_confidence(
            response_text, self.test_categories
        )

        self.assertEqual(result.category, "technology")
        self.assertGreater(result.confidence, 0.3)
        self.assertEqual(result.method, "explicit_statement")
        self.assertIn("technology", result.details)

    def test_extract_category_with_confidence_emphasis(self):
        """Test l'extraction par emphasis."""
        response_text = "This is clearly **sports** related content."
        result = self.analyzer.extract_category_with_confidence(
            response_text, self.test_categories
        )

        self.assertEqual(result.category, "sports")
        self.assertGreater(result.confidence, 0.3)
        self.assertEqual(result.method, "emphasis")

    def test_extract_category_with_confidence_positive_context(self):
        """Test l'extraction par contexte positif."""
        response_text = "This appears to be health related information."
        result = self.analyzer.extract_category_with_confidence(
            response_text, self.test_categories
        )

        self.assertEqual(result.category, "health")
        self.assertGreater(result.confidence, 0.3)
        self.assertEqual(result.method, "positive_context")

    def test_extract_category_with_confidence_validation_failed(self):
        """Test l'extraction avec validation échouée."""
        result = self.analyzer.extract_category_with_confidence(
            "", self.test_categories
        )

        self.assertEqual(result.category, "unknown")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.method, "validation_failed")

    def test_extract_category_with_confidence_low_confidence(self):
        """Test l'extraction avec confiance trop faible."""
        # Configurer un seuil de confiance élevé
        self.analyzer.config.min_confidence_score = 0.9

        response_text = "Maybe this could be sports related."
        result = self.analyzer.extract_category_with_confidence(
            response_text, self.test_categories
        )

        self.assertEqual(result.category, "unknown")
        self.assertEqual(result.method, "all_strategies_failed")

    # === TESTS D'EXTRACTION PAR DÉCLARATION EXPLICITE ===

    def test_extract_by_explicit_statement_success(self):
        """Test l'extraction réussie par déclaration explicite."""
        normalized_text = "the category is sports content here"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_explicit_statement(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "sports")
        self.assertEqual(result.method, "explicit_statement")

    def test_extract_by_explicit_statement_no_match(self):
        """Test l'extraction par déclaration explicite sans correspondance."""
        normalized_text = "some random text without explicit category"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_explicit_statement(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNone(result)

    def test_extract_by_explicit_statement_invalid_text(self):
        """Test l'extraction par déclaration explicite avec texte invalide."""
        normalized_text = "category: this_is_way_too_long_to_be_a_valid_category_name_and_should_be_rejected"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_explicit_statement(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNone(result)

    # === TESTS D'EXTRACTION PAR EMPHASIS ===

    def test_extract_by_emphasis_bold_text(self):
        """Test l'extraction par texte en gras."""
        normalized_text = "this content is about **sports** and activities"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_emphasis(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "sports")
        self.assertEqual(result.method, "emphasis")

    def test_extract_by_emphasis_quoted_text(self):
        """Test l'extraction par texte entre guillemets."""
        normalized_text = 'the topic is "technology" development'
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_emphasis(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "technology")

    def test_extract_by_emphasis_first_line_bonus(self):
        """Test le bonus de confiance pour la première ligne."""
        normalized_text = "**sports**\nsome other content here"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_emphasis(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "sports")
        self.assertIn("first_line", result.details)

    # === TESTS D'EXTRACTION PAR CONTEXTE POSITIF ===

    def test_extract_by_positive_context_success(self):
        """Test l'extraction réussie par contexte positif."""
        normalized_text = "this is health information about wellness"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_positive_context(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "health")
        self.assertEqual(result.method, "positive_context")

    def test_extract_by_positive_context_with_negatives(self):
        """Test l'extraction par contexte positif en présence de mentions négatives."""
        normalized_text = "this is not sports but it is definitely health related"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_positive_context(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "health")

    def test_extract_by_positive_context_single_remaining_category(self):
        """Test l'extraction avec une seule catégorie restante non niée."""
        normalized_text = "this is not sports and not technology but mentions health"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_positive_context(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "health")

    # === TESTS D'EXTRACTION PAR ANALYSE DE FRÉQUENCE ===

    def test_extract_by_frequency_analysis_single_word(self):
        """Test l'analyse de fréquence pour catégories d'un mot."""
        normalized_text = "sports sports technology sports health"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_frequency_analysis(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.category, "sports")
        self.assertEqual(result.method, "frequency_analysis")

    def test_extract_by_frequency_analysis_no_matches(self):
        """Test l'analyse de fréquence sans correspondances."""
        normalized_text = "random text without any category mentions"
        normalized_categories = [cat.lower() for cat in self.test_categories]

        result = self.analyzer._extract_by_frequency_analysis(
            normalized_text, normalized_categories, self.test_categories
        )

        self.assertIsNone(result)

    # === TESTS DE MÉTHODES UTILITAIRES ===

    def test_match_extracted_to_categories_direct_match(self):
        """Test la correspondance directe avec cache."""
        normalized_categories = tuple([cat.lower() for cat in self.test_categories])
        original_categories = tuple(self.test_categories)

        result = self.analyzer._match_extracted_to_categories(
            "sports", normalized_categories, original_categories
        )

        self.assertEqual(result, "sports")

    def test_match_extracted_to_categories_with_multi_word(self):
        """Test la correspondance avec catégories multi-mots."""
        # Ajoutons une catégorie multi-mots pour tester cette logique
        extended_categories = self.test_categories + ["artificial intelligence"]
        normalized_categories = tuple([cat.lower() for cat in extended_categories])
        original_categories = tuple(extended_categories)

        # Test avec un texte qui contient tous les mots de la catégorie
        result = self.analyzer._match_extracted_to_categories(
            "this is about artificial intelligence research",
            normalized_categories,
            original_categories,
        )

        self.assertEqual(result, "artificial intelligence")

    def test_match_extracted_to_categories_no_match(self):
        """Test la correspondance sans résultat."""
        normalized_categories = tuple([cat.lower() for cat in self.test_categories])
        original_categories = tuple(self.test_categories)

        result = self.analyzer._match_extracted_to_categories(
            "unknown_category", normalized_categories, original_categories
        )

        self.assertIsNone(result)

    def test_find_negative_mentions(self):
        """Test la recherche de mentions négatives."""
        text = "this is not sports and isn't technology"
        patterns = self.analyzer._compiled_patterns["negative"]
        normalized_categories = [cat.lower() for cat in self.test_categories]

        negative_mentions = self.analyzer._find_negative_mentions(
            text, patterns, normalized_categories
        )

        self.assertIn("sports", negative_mentions)
        self.assertIn("technology", negative_mentions)

    def test_get_negative_spans(self):
        """Test la récupération des spans de contexte négatif."""
        text = "this is not sports related content"
        patterns = self.analyzer._compiled_patterns["negative"]

        spans = self.analyzer._get_negative_spans(text, patterns)

        self.assertIsInstance(spans, list)
        if spans:  # Si des patterns correspondent
            self.assertIsInstance(spans[0], tuple)
            self.assertEqual(len(spans[0]), 2)

    def test_is_in_negative_context(self):
        """Test la vérification de contexte négatif."""
        negative_spans = [(0, 10), (20, 30)]

        # Test span dans le contexte négatif
        self.assertTrue(self.analyzer._is_in_negative_context((5, 8), negative_spans))

        # Test span hors contexte négatif
        self.assertFalse(
            self.analyzer._is_in_negative_context((15, 18), negative_spans)
        )

    def test_is_valid_extracted_text_valid(self):
        """Test la validation de texte extrait valide."""
        self.assertTrue(self.analyzer._is_valid_extracted_text("sports"))
        self.assertTrue(self.analyzer._is_valid_extracted_text("health care"))
        self.assertTrue(self.analyzer._is_valid_extracted_text("tech-news"))

    def test_is_valid_extracted_text_invalid(self):
        """Test la validation de texte extrait invalide."""
        # Texte vide
        self.assertFalse(self.analyzer._is_valid_extracted_text(""))

        # Texte trop long
        long_text = "a" * (self.test_config.max_category_length + 1)
        self.assertFalse(self.analyzer._is_valid_extracted_text(long_text))

        # Caractères invalides
        self.assertFalse(self.analyzer._is_valid_extracted_text("sports@#$"))

    def test_calculate_explicit_confidence(self):
        """Test le calcul de confiance pour les patterns explicites."""
        # Mock d'un match au début du texte
        mock_match = Mock()
        mock_match.start.return_value = 5
        mock_match.group.return_value = "category is sports"

        full_text = "The category is sports and related activities"
        confidence = self.analyzer._calculate_explicit_confidence(mock_match, full_text)

        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0.8)
        self.assertLessEqual(confidence, 0.95)

    # === TESTS DE STATISTIQUES ===

    def test_get_extraction_statistics_valid_input(self):
        """Test la récupération de statistiques avec entrée valide."""
        response_text = "The category is sports and not technology"
        stats = self.analyzer.get_extraction_statistics(
            response_text, self.test_categories
        )

        self.assertIsInstance(stats, dict)
        self.assertIn("text_length", stats)
        self.assertIn("pattern_matches", stats)
        self.assertIn("category_frequencies", stats)
        self.assertIn("negative_mentions", stats)

        self.assertEqual(stats["text_length"], len(response_text))
        self.assertEqual(stats["available_categories"], len(self.test_categories))

    def test_get_extraction_statistics_invalid_input(self):
        """Test la récupération de statistiques avec entrée invalide."""
        stats = self.analyzer.get_extraction_statistics("", self.test_categories)

        self.assertIn("error", stats)
        self.assertEqual(stats["error"], "Invalid inputs")

    # === TESTS D'EXCEPTIONS ET CAS D'ERREUR ===

    def test_extract_category_with_confidence_exception_in_strategy(self):
        """Test la gestion d'exception dans une stratégie d'extraction."""
        # Mock une méthode pour lever une exception
        with patch.object(
            self.analyzer,
            "_extract_by_explicit_statement",
            side_effect=Exception("Test error"),
        ):
            response_text = "Category: sports"
            result = self.analyzer.extract_category_with_confidence(
                response_text, self.test_categories
            )

            # Devrait continuer avec les autres stratégies
            self.assertIsInstance(result, CategoryExtractionResult)
            self.analyzer.logger.error.assert_called()

    def test_extract_category_with_confidence_all_strategies_fail(self):
        """Test quand toutes les stratégies échouent."""
        # Mock toutes les stratégies pour retourner None
        with (
            patch.object(
                self.analyzer, "_extract_by_explicit_statement", return_value=None
            ),
            patch.object(self.analyzer, "_extract_by_emphasis", return_value=None),
            patch.object(
                self.analyzer, "_extract_by_positive_context", return_value=None
            ),
            patch.object(
                self.analyzer, "_extract_by_frequency_analysis", return_value=None
            ),
        ):
            response_text = "Some random text"
            result = self.analyzer.extract_category_with_confidence(
                response_text, self.test_categories
            )

            self.assertEqual(result.category, "unknown")
            self.assertEqual(result.method, "all_strategies_failed")
            self.assertEqual(result.confidence, 0.0)

    # === TESTS DE PERFORMANCE ET CACHE ===

    def test_match_extracted_to_categories_cache_usage(self):
        """Test l'utilisation du cache LRU."""
        normalized_categories = tuple([cat.lower() for cat in self.test_categories])
        original_categories = tuple(self.test_categories)

        # Premier appel
        result1 = self.analyzer._match_extracted_to_categories(
            "sports", normalized_categories, original_categories
        )

        # Deuxième appel (devrait utiliser le cache)
        result2 = self.analyzer._match_extracted_to_categories(
            "sports", normalized_categories, original_categories
        )

        self.assertEqual(result1, result2)
        self.assertEqual(result1, "sports")

    # === TESTS DE CAS RÉELS ===

    def test_realistic_llm_response_positive(self):
        """Test avec une réponse LLM réaliste positive."""
        response_text = """
        Based on the content provided, I would classify this as **sports** related material.
        The document contains information about athletic activities, training schedules, 
        and competitive events. This clearly falls under the sports category.
        """

        result = self.analyzer.extract_category_with_confidence(
            response_text, self.test_categories
        )

        self.assertEqual(result.category, "sports")
        self.assertGreater(result.confidence, 0.3)

    def test_realistic_llm_response_with_negation(self):
        """Test avec une réponse LLM contenant des négations."""
        response_text = """
        This content is not sports related and isn't about entertainment either.
        However, it appears to be technology focused, discussing software development
        and programming concepts. I would categorize this as technology.
        """

        result = self.analyzer.extract_category_with_confidence(
            response_text, self.test_categories
        )

        self.assertEqual(result.category, "technology")

    def test_realistic_llm_response_ambiguous(self):
        """Test avec une réponse LLM ambigüe."""
        response_text = """
        This is an interesting document that could potentially fit into multiple categories.
        It mentions sports, technology, and health topics throughout the text.
        However, if I had to choose, I would say it's primarily about sports.
        """

        result = self.analyzer.extract_category_with_confidence(
            response_text, self.test_categories
        )

        # Devrait extraire "sports" même dans un contexte ambigu
        self.assertIn(result.category, self.test_categories)

    # === TESTS DE CONFIGURATION EDGE CASES ===

    def test_empty_pattern_lists(self):
        """Test avec des listes de patterns vides."""
        empty_config = CategoryExtractionConfig(
            explicit_patterns=[],
            emphasis_patterns=[],
            positive_context_patterns=[],
            negative_patterns=[],
        )

        analyzer = CategoryAnalyzer(config=empty_config)
        analyzer.logger = MagicMock()  # Mock le logger

        response_text = "Category: sports"
        result = analyzer.extract_category_with_confidence(
            response_text, self.test_categories
        )

        # Devrait fallback sur frequency analysis ou retourner unknown
        self.assertIsInstance(result, CategoryExtractionResult)

    def test_malformed_pattern_handling(self):
        """Test la gestion de patterns regex malformés."""
        # Cette partie est déjà testée dans test_compile_patterns_with_invalid_regex
        # mais on peut ajouter un test plus spécifique ici
        malformed_config = CategoryExtractionConfig(
            explicit_patterns=["[unclosed_bracket", "valid_pattern"]
        )

        # Ne devrait pas lever d'exception
        analyzer = CategoryAnalyzer(config=malformed_config)
        analyzer.logger = MagicMock()  # Mock le logger
        self.assertIsInstance(analyzer, CategoryAnalyzer)


if __name__ == "__main__":
    # Configuration pour les tests
    unittest.TestLoader.sortTestMethodsUsing = None
    unittest.main(verbosity=2)
