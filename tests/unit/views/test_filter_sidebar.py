import sys
from PyQt6.QtWidgets import QApplication

from ai_content_classifier.views.widgets.specialized.filter_sidebar import (
    FilterSidebar,
    FlowLayout,
)


class TestFilterSidebar:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_set_filters_shows_contextual_filter_chips(self):
        widget = FilterSidebar()

        widget.set_filters(
            [
                {
                    "id": "category:space",
                    "label": "Space",
                    "type": "category",
                    "selected": True,
                },
                {
                    "id": "ext:png",
                    "label": ".png",
                    "type": "extension",
                    "selected": False,
                },
            ]
        )

        assert not widget.clear_button.isHidden()
        assert not widget.category_chip_host.isHidden()
        assert not widget.extension_chip_host.isHidden()

    def test_sidebar_hides_active_filters_section_when_empty(self):
        widget = FilterSidebar()

        widget.set_filters([])

        assert widget.clear_button.isHidden()
        assert widget.category_chip_host.isHidden()
        assert widget.date_chip_host.isHidden()
        assert widget.extension_chip_host.isHidden()

    def test_sidebar_renders_contextual_chips_and_removes_them_via_close_button(self):
        widget = FilterSidebar()

        widget.set_filters(
            [
                {
                    "id": "category_space",
                    "label": "Space",
                    "type": "category",
                    "selected": True,
                },
                {
                    "id": "extension_.png",
                    "label": ".png",
                    "type": "extension",
                    "selected": True,
                },
            ]
        )

        category_chip = widget.category_chip_host.chip_layout.itemAt(0).widget()
        remove_button = category_chip.layout().itemAt(1).widget()
        remove_button.click()

        assert "category_space" not in widget.filter_chips_container.chips

    def test_contextual_filter_chips_use_wrapping_flow_layout(self):
        widget = FilterSidebar()

        assert isinstance(widget.category_chip_host.chip_layout, FlowLayout)
        assert isinstance(widget.date_chip_host.chip_layout, FlowLayout)
        assert isinstance(widget.extension_chip_host.chip_layout, FlowLayout)

    def test_compact_mode_hides_secondary_filter_controls(self):
        widget = FilterSidebar()

        widget.set_compact_mode(True)

        assert not widget.actions_title.isHidden()
        assert widget.filter_chips_container.title_label.isHidden()
        assert widget.filter_chips_container.options_button.isHidden()
        assert widget.filter_chips_container.select_all_button.text() == "All"
        assert widget.filter_chips_container.clear_all_button.text() == "Clear"
        assert widget.clear_button.text() == "Clear"
