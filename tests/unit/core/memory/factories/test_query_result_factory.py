"""
Tests unitaires complets pour QueryResultFactory - Couverture 100%.
"""

import sys
from unittest.mock import Mock

from ai_content_classifier.core.memory.factories.query_result_factory import (
    QueryResultFactory,
)


class TestQueryResultFactory:
    """Tests complets pour QueryResultFactory"""

    def setup_method(self):
        """Setup pour chaque test"""
        self.factory = QueryResultFactory()

    def test_create_empty_list(self):
        """Test création d'une liste vide"""
        result = self.factory.create()

        assert isinstance(result, list)
        assert len(result) == 0
        assert result == []

    def test_create_multiple_lists(self):
        """Test création de plusieurs listes indépendantes"""
        list1 = self.factory.create()
        list2 = self.factory.create()
        list3 = self.factory.create()

        # Chaque création doit retourner une nouvelle liste
        assert list1 is not list2
        assert list2 is not list3
        assert list1 is not list3

        # Modifier une liste ne doit pas affecter les autres
        list1.append({"test": "data"})
        assert len(list1) == 1
        assert len(list2) == 0
        assert len(list3) == 0

    def test_create_list_type_consistency(self):
        """Test cohérence du type créé"""
        for _ in range(5):
            result = self.factory.create()
            assert isinstance(result, list)
            assert hasattr(result, "append")
            assert hasattr(result, "clear")
            assert hasattr(result, "extend")

    def test_reset_empty_list(self):
        """Test reset d'une liste vide"""
        empty_list = []

        result = self.factory.reset(empty_list)

        assert result is True
        assert len(empty_list) == 0

    def test_reset_populated_list(self):
        """Test reset d'une liste avec données"""
        populated_list = [
            {"id": 1, "name": "John"},
            {"id": 2, "name": "Jane"},
            {"id": 3, "name": "Bob"},
        ]

        # Vérifier qu'elle contient des données
        assert len(populated_list) == 3

        result = self.factory.reset(populated_list)

        assert result is True
        assert len(populated_list) == 0
        assert populated_list == []

    def test_reset_different_list_types(self):
        """Test reset avec différents types de contenus"""
        # Liste de dictionnaires
        dict_list = [{"key": "value"}, {"another": "item"}]
        result1 = self.factory.reset(dict_list)
        assert result1 is True
        assert len(dict_list) == 0

        # Liste mixte
        mixed_list = [{"dict": True}, "string", 123, [1, 2, 3]]
        result2 = self.factory.reset(mixed_list)
        assert result2 is True
        assert len(mixed_list) == 0

        # Liste de listes
        nested_list = [[1, 2], [3, 4], [5, 6]]
        result3 = self.factory.reset(nested_list)
        assert result3 is True
        assert len(nested_list) == 0

    def test_reset_large_list(self):
        """Test reset d'une grande liste"""
        large_list = [{"id": i, "data": f"item_{i}"} for i in range(1000)]

        assert len(large_list) == 1000

        result = self.factory.reset(large_list)

        assert result is True
        assert len(large_list) == 0

    def test_reset_exception_handling(self):
        """Test gestion d'exception dans reset"""
        # Mock qui lève une exception sur clear()
        mock_list = Mock()
        mock_list.clear.side_effect = AttributeError("Clear failed")

        result = self.factory.reset(mock_list)

        assert result is False
        mock_list.clear.assert_called_once()

    def test_reset_with_invalid_objects(self):
        """Test reset avec objets invalides"""
        # String (pas de méthode clear)
        result1 = self.factory.reset("not_a_list")
        assert result1 is False

        # None
        result2 = self.factory.reset(None)
        assert result2 is False

        # Integer
        result3 = self.factory.reset(123)
        assert result3 is False

        # Dict (a une méthode clear mais c'est pas une liste)
        test_dict = {"key": "value"}
        result4 = self.factory.reset(test_dict)
        assert result4 is True  # Dict.clear() existe et fonctionne
        assert test_dict == {}

    def test_validate_valid_lists(self):
        """Test validation de listes valides"""
        # Liste vide
        assert self.factory.validate([]) is True

        # Liste avec données
        assert self.factory.validate([{"id": 1}, {"id": 2}]) is True

        # Liste avec types mixtes
        assert self.factory.validate([1, "string", {"dict": True}]) is True

        # Liste de listes
        assert self.factory.validate([[1, 2], [3, 4]]) is True

    def test_validate_invalid_types(self):
        """Test validation d'objets invalides"""
        assert self.factory.validate(None) is False
        assert self.factory.validate("string") is False
        assert self.factory.validate(123) is False
        assert self.factory.validate({"dict": "value"}) is False
        assert self.factory.validate((1, 2, 3)) is False  # Tuple, pas liste
        assert self.factory.validate(set([1, 2, 3])) is False

    def test_validate_list_subclasses(self):
        """Test validation avec sous-classes de list"""

        class CustomList(list):
            pass

        custom_list = CustomList([1, 2, 3])
        assert self.factory.validate(custom_list) is True

    def test_validate_edge_cases(self):
        """Test validation cas limites"""
        # Liste très grande
        big_list = list(range(10000))
        assert self.factory.validate(big_list) is True

        # Liste avec None à l'intérieur
        list_with_none = [None, None, None]
        assert self.factory.validate(list_with_none) is True

    def test_get_key_consistency(self):
        """Test cohérence de génération de clé"""
        # Tous les appels doivent retourner la même clé
        keys = [self.factory.get_key() for _ in range(10)]
        expected_key = "query_result_list"

        assert all(key == expected_key for key in keys)

    def test_get_key_independence(self):
        """Test indépendance de la génération de clé"""
        # La clé ne doit pas dépendre de l'état de la factory
        key1 = self.factory.get_key()

        # Effectuer diverses opérations
        self.factory.create()
        self.factory.reset([1, 2, 3])
        self.factory.validate("test")

        key2 = self.factory.get_key()

        assert key1 == key2 == "query_result_list"

    def test_estimate_size_empty_list(self):
        """Test estimation taille liste vide"""
        empty_list = []

        result = self.factory.estimate_size(empty_list)
        expected = sys.getsizeof([])

        assert result == expected
        assert result > 0

    def test_estimate_size_populated_lists(self):
        """Test estimation taille listes avec données"""
        # Liste avec 1 élément
        list_1 = [{"id": 1}]
        size_1 = self.factory.estimate_size(list_1)

        # Liste avec 5 éléments
        list_5 = [{"id": i} for i in range(5)]
        size_5 = self.factory.estimate_size(list_5)

        # Liste avec 10 éléments
        list_10 = [{"id": i} for i in range(10)]
        size_10 = self.factory.estimate_size(list_10)

        # La taille doit augmenter avec le nombre d'éléments
        assert size_1 < size_5 < size_10

        # Vérifier la formule: list_overhead + len(obj) * 100
        list_overhead = sys.getsizeof([])
        assert size_1 == list_overhead + 1 * 100
        assert size_5 == list_overhead + 5 * 100
        assert size_10 == list_overhead + 10 * 100

    def test_estimate_size_calculation_accuracy(self):
        """Test précision du calcul d'estimation"""
        # Test avec différentes tailles
        test_cases = [
            ([], sys.getsizeof([]) + 0 * 100),
            ([{}], sys.getsizeof([]) + 1 * 100),
            ([{}, {}], sys.getsizeof([]) + 2 * 100),
            ([{} for _ in range(50)], sys.getsizeof([]) + 50 * 100),
            ([{} for _ in range(100)], sys.getsizeof([]) + 100 * 100),
        ]

        for test_list, expected_size in test_cases:
            actual_size = self.factory.estimate_size(test_list)
            assert actual_size == expected_size

    def test_estimate_size_with_different_content_types(self):
        """Test estimation avec différents types de contenu"""
        # Le calcul utilise une estimation fixe de 100 bytes par item
        # peu importe le contenu réel

        list_dicts = [{"key": "value"} for _ in range(3)]
        list_strings = ["string1", "string2", "string3"]
        list_ints = [1, 2, 3]
        list_mixed = [{"dict": True}, "string", 123]

        size_dicts = self.factory.estimate_size(list_dicts)
        size_strings = self.factory.estimate_size(list_strings)
        size_ints = self.factory.estimate_size(list_ints)
        size_mixed = self.factory.estimate_size(list_mixed)

        # Toutes doivent avoir la même taille estimée (3 items * 100 + overhead)
        expected = sys.getsizeof([]) + 3 * 100
        assert size_dicts == expected
        assert size_strings == expected
        assert size_ints == expected
        assert size_mixed == expected

    def test_comprehensive_workflow(self):
        """Test workflow complet"""
        # Créer une liste
        query_results = self.factory.create()
        assert len(query_results) == 0

        # Ajouter des données (simulation d'utilisation)
        query_results.extend(
            [
                {"id": 1, "name": "Alice", "age": 30},
                {"id": 2, "name": "Bob", "age": 25},
                {"id": 3, "name": "Charlie", "age": 35},
            ]
        )
        assert len(query_results) == 3

        # Valider
        is_valid = self.factory.validate(query_results)
        assert is_valid is True

        # Estimer la taille
        estimated_size = self.factory.estimate_size(query_results)
        expected_size = sys.getsizeof([]) + 3 * 100
        assert estimated_size == expected_size

        # Générer une clé
        key = self.factory.get_key()
        assert key == "query_result_list"

        # Reset pour réutilisation
        reset_success = self.factory.reset(query_results)
        assert reset_success is True
        assert len(query_results) == 0

        # Valider après reset
        is_still_valid = self.factory.validate(query_results)
        assert is_still_valid is True

    def test_factory_immutability(self):
        """Test que la factory n'est pas modifiée par les opérations"""
        # Effectuer diverses opérations et vérifier que la factory reste intacte
        original_factory_dict = self.factory.__dict__.copy()

        # Opérations diverses
        self.factory.create()
        self.factory.reset([1, 2, 3])
        self.factory.validate("test")
        self.factory.get_key()
        self.factory.estimate_size([{"test": "data"}])

        # La factory ne doit pas avoir changé
        assert self.factory.__dict__ == original_factory_dict

    def test_multiple_factory_instances(self):
        """Test avec plusieurs instances de factory"""
        factory1 = QueryResultFactory()
        factory2 = QueryResultFactory()

        # Elles doivent se comporter de manière identique
        list1 = factory1.create()
        list2 = factory2.create()

        assert isinstance(list1, list) and isinstance(list2, list)
        assert len(list1) == len(list2) == 0
        assert factory1.get_key() == factory2.get_key()

        # Valider cross-factory
        assert factory1.validate(list2) is True
        assert factory2.validate(list1) is True

    def test_realistic_query_result_simulation(self):
        """Test simulation réaliste de résultats de requête"""
        # Simuler des résultats de requête SQL typiques
        query_results = self.factory.create()

        # Simuler ajout de résultats
        simulated_results = [
            {
                "user_id": 1,
                "username": "alice",
                "email": "alice@example.com",
                "created_at": "2023-01-01",
            },
            {
                "user_id": 2,
                "username": "bob",
                "email": "bob@example.com",
                "created_at": "2023-01-02",
            },
            {
                "user_id": 3,
                "username": "charlie",
                "email": "charlie@example.com",
                "created_at": "2023-01-03",
            },
        ]

        query_results.extend(simulated_results)

        # Valider la structure
        assert self.factory.validate(query_results) is True
        assert len(query_results) == 3

        # Vérifier le contenu
        for result in query_results:
            assert isinstance(result, dict)
            assert "user_id" in result
            assert "username" in result
            assert "email" in result

        # Estimer la taille
        size = self.factory.estimate_size(query_results)
        assert size > sys.getsizeof([])

        # Nettoyer pour réutilisation
        assert self.factory.reset(query_results) is True
        assert len(query_results) == 0
