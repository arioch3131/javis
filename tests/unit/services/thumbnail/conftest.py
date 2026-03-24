# tests/services/thumbnail/conftest.py

import pytest
import sys

@pytest.fixture(autouse=True, scope="function")
def reset_qt_modules():
    """Reset PyQt6 modules before each test to avoid contamination"""
    # Modules PyQt6 à surveiller
    qt_modules = [
        'PyQt6',
        'PyQt6.QtCore', 
        'PyQt6.QtGui',
        'PyQt6.QtSvg',
        'PyQt6.QtWidgets'
    ]
    
    # Sauvegarder l'état initial
    original_modules = {}
    for module_name in qt_modules:
        original_modules[module_name] = sys.modules.get(module_name)
    
    yield  # Exécuter le test
    
    # Nettoyer après le test
    for module_name in qt_modules:
        original_value = original_modules[module_name]
        if original_value is None:
            # Le module n'existait pas avant, le supprimer s'il existe maintenant
            if module_name in sys.modules:
                del sys.modules[module_name]
        else:
            # Restaurer la valeur originale
            sys.modules[module_name] = original_value


# Classe factice pour les specs QPixmap
class FakeQPixmap:
    """Fake QPixmap class for testing purposes"""
    def __init__(self, *args, **kwargs):
        pass
    
    def save(self, *args, **kwargs):
        return True
    
    def isNull(self):
        return False
    
    def scaled(self, *args, **kwargs):
        return self
    
    def size(self):
        return FakeQSize(100, 100)


class FakeQSize:
    """Fake QSize class for testing purposes"""
    def __init__(self, width, height):
        self._width = width
        self._height = height
    
    def width(self):
        return self._width
    
    def height(self):
        return self._height


# Fixture pour fournir des classes factices
@pytest.fixture
def fake_qpixmap():
    return FakeQPixmap


@pytest.fixture  
def fake_qsize():
    return FakeQSize