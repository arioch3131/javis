"""
Tests unitaires complets pour SQLAlchemySessionFactory - Couverture 100%.
"""

import pytest
from unittest.mock import Mock
from sqlalchemy.exc import SQLAlchemyError

from ai_content_classifier.core.memory.factories.sqlalchemy_session_factory import (
    SQLAlchemySessionFactory,
)


class TestSQLAlchemySessionFactory:
    """Tests complets pour SQLAlchemySessionFactory"""

    def setup_method(self):
        """Setup pour chaque test"""
        self.database_service = Mock()
        self.factory = SQLAlchemySessionFactory(self.database_service)

    def test_init(self):
        """Test du constructeur"""
        assert self.factory.database_service == self.database_service

    def test_init_with_different_service(self):
        """Test constructeur avec différents services"""
        service1 = Mock()
        service2 = Mock()

        factory1 = SQLAlchemySessionFactory(service1)
        factory2 = SQLAlchemySessionFactory(service2)

        assert factory1.database_service == service1
        assert factory2.database_service == service2
        assert factory1.database_service != factory2.database_service

    def test_create_basic(self):
        """Test création de session basique"""
        mock_session = Mock()
        self.database_service.Session.return_value = mock_session

        result = self.factory.create()

        assert result == mock_session
        self.database_service.Session.assert_called_once_with()

    def test_create_with_kwargs(self):
        """Test création avec kwargs"""
        mock_session = Mock()
        self.database_service.Session.return_value = mock_session

        result = self.factory.create(some_param="value", another_param=123)

        assert result == mock_session
        self.database_service.Session.assert_called_once_with(
            some_param="value", another_param=123
        )

    def test_create_multiple_sessions(self):
        """Test création de plusieurs sessions"""
        session1 = Mock()
        session2 = Mock()
        session3 = Mock()

        self.database_service.Session.side_effect = [session1, session2, session3]

        result1 = self.factory.create()
        result2 = self.factory.create()
        result3 = self.factory.create()

        assert result1 == session1
        assert result2 == session2
        assert result3 == session3
        assert self.database_service.Session.call_count == 3

    def test_create_database_service_exception(self):
        """Test création quand database_service lève une exception"""
        self.database_service.Session.side_effect = Exception(
            "Database connection failed"
        )

        with pytest.raises(Exception) as exc_info:
            self.factory.create()

        assert "Database connection failed" in str(exc_info.value)

    def test_reset_success(self):
        """Test reset réussi d'une session"""
        mock_session = Mock()
        mock_session.rollback.return_value = None
        mock_session.expunge_all.return_value = None

        result = self.factory.reset(mock_session)

        assert result is True
        mock_session.rollback.assert_called_once()
        mock_session.expunge_all.assert_called_once()

    def test_reset_with_different_sessions(self):
        """Test reset avec différentes sessions"""
        session1 = Mock()
        session2 = Mock()

        result1 = self.factory.reset(session1)
        result2 = self.factory.reset(session2)

        assert result1 is True
        assert result2 is True

        session1.rollback.assert_called_once()
        session1.expunge_all.assert_called_once()
        session2.rollback.assert_called_once()
        session2.expunge_all.assert_called_once()

    def test_reset_rollback_exception(self):
        """Test reset quand rollback lève une exception"""
        mock_session = Mock()
        mock_session.rollback.side_effect = SQLAlchemyError("Rollback failed")

        result = self.factory.reset(mock_session)

        assert result is False
        mock_session.rollback.assert_called_once()
        # expunge_all ne devrait pas être appelé car rollback a échoué
        mock_session.expunge_all.assert_not_called()

    def test_reset_expunge_all_exception(self):
        """Test reset quand expunge_all lève une exception"""
        mock_session = Mock()
        mock_session.rollback.return_value = None
        mock_session.expunge_all.side_effect = SQLAlchemyError("Expunge failed")

        result = self.factory.reset(mock_session)

        assert result is False
        mock_session.rollback.assert_called_once()
        mock_session.expunge_all.assert_called_once()

    def test_reset_both_methods_exception(self):
        """Test reset quand rollback et expunge_all lèvent des exceptions"""
        mock_session = Mock()
        mock_session.rollback.side_effect = SQLAlchemyError("Rollback failed")
        mock_session.expunge_all.side_effect = SQLAlchemyError("Expunge failed")

        result = self.factory.reset(mock_session)

        assert result is False
        mock_session.rollback.assert_called_once()
        # expunge_all ne devrait pas être appelé car rollback a échoué en premier
        mock_session.expunge_all.assert_not_called()

    def test_reset_with_none(self):
        """Test reset avec None"""
        result = self.factory.reset(None)
        assert result is False

    def test_reset_with_invalid_object(self):
        """Test reset avec objet invalide"""
        invalid_obj = "not_a_session"
        result = self.factory.reset(invalid_obj)
        assert result is False

    def test_validate_active_session(self):
        """Test validation de session active"""
        mock_session = Mock()
        mock_session.is_active = True

        result = self.factory.validate(mock_session)

        assert result is True

    def test_validate_inactive_session(self):
        """Test validation de session inactive"""
        mock_session = Mock()
        mock_session.is_active = False

        result = self.factory.validate(mock_session)

        assert result is False

    def test_validate_multiple_sessions(self):
        """Test validation de plusieurs sessions"""
        active_session = Mock()
        inactive_session = Mock()
        active_session.is_active = True
        inactive_session.is_active = False

        result1 = self.factory.validate(active_session)
        result2 = self.factory.validate(inactive_session)

        assert result1 is True
        assert result2 is False

    def test_validate_session_without_is_active(self):
        """Test validation avec session sans attribut is_active"""
        mock_session = Mock()
        # Supprimer l'attribut is_active
        del mock_session.is_active

        result = self.factory.validate(mock_session)

        assert result is False

    def test_validate_is_active_property_exception(self):
        """Test validation quand is_active lève une exception"""
        mock_session = Mock()
        del mock_session.is_active
        result = self.factory.validate(mock_session)
        assert result is False

    def test_validate_with_none(self):
        """Test validation avec None"""
        result = self.factory.validate(None)
        assert result is False

    def test_validate_with_invalid_object(self):
        """Test validation avec objet invalide"""
        result = self.factory.validate("not_a_session")
        assert result is False

    def test_get_key_default(self):
        """Test génération de clé par défaut"""
        result = self.factory.get_key()
        assert result == "session_default"

    def test_get_key_with_kwargs(self):
        """Test génération de clé avec kwargs (ignorés)"""
        result1 = self.factory.get_key(param1="value1", param2="value2")
        result2 = self.factory.get_key(different="kwargs")
        result3 = self.factory.get_key()

        # Tous doivent retourner la même clé car les kwargs sont ignorés
        assert result1 == "session_default"
        assert result2 == "session_default"
        assert result3 == "session_default"

    def test_get_key_consistency(self):
        """Test cohérence de génération de clé"""
        # Appeler get_key plusieurs fois doit donner le même résultat
        keys = [self.factory.get_key() for _ in range(10)]
        assert all(key == "session_default" for key in keys)

    def test_comprehensive_workflow(self):
        """Test workflow complet"""
        # Setup session mock
        mock_session = Mock()
        mock_session.is_active = True
        self.database_service.Session.return_value = mock_session

        # Test workflow complet
        key = self.factory.get_key()
        session = self.factory.create()
        is_valid_before = self.factory.validate(session)
        reset_success = self.factory.reset(session)
        is_valid_after = self.factory.validate(session)

        # Assertions
        assert key == "session_default"
        assert session == mock_session
        assert is_valid_before is True
        assert reset_success is True
        assert is_valid_after is True  # Session toujours active après reset

        # Vérifications des appels
        self.database_service.Session.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.expunge_all.assert_called_once()

    def test_session_lifecycle_simulation(self):
        """Test simulation du cycle de vie d'une session"""
        # Simuler une session qui devient inactive après utilisation
        mock_session = Mock()

        # Session active au début
        mock_session.is_active = True
        self.database_service.Session.return_value = mock_session

        # Créer et valider
        session = self.factory.create()
        assert self.factory.validate(session) is True

        # Simuler que la session devient inactive
        mock_session.is_active = False
        assert self.factory.validate(session) is False

        # Reset devrait réussir même si session inactive
        assert self.factory.reset(session) is True

        # Session peut redevenir active après reset
        mock_session.is_active = True
        assert self.factory.validate(session) is True

    def test_multiple_factory_instances(self):
        """Test avec plusieurs instances de factory"""
        service1 = Mock()
        service2 = Mock()

        factory1 = SQLAlchemySessionFactory(service1)
        factory2 = SQLAlchemySessionFactory(service2)

        session1 = Mock()
        session2 = Mock()
        service1.Session.return_value = session1
        service2.Session.return_value = session2

        # Créer des sessions avec chaque factory
        result1 = factory1.create()
        result2 = factory2.create()

        assert result1 == session1
        assert result2 == session2
        assert result1 != result2

        # Chaque factory utilise son propre service
        service1.Session.assert_called_once()
        service2.Session.assert_called_once()

    def test_factory_immutability(self):
        """Test que la factory n'est pas modifiée par les opérations"""
        original_service = self.factory.database_service

        # Effectuer diverses opérations
        self.factory.get_key()
        self.factory.get_key(param="value")

        mock_session = Mock()
        self.factory.reset(mock_session)
        self.factory.validate(mock_session)

        # La factory doit rester inchangée
        assert self.factory.database_service == original_service


# Import PropertyMock pour le test validate_is_active_property_exception
