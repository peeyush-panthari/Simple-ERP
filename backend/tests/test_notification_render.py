"""Port of the notification service's bespoke {{path}}/{{#each}}/{{#if}}
mini-language, exercised directly against app.services.notification_render -
no Node test file exists to port 1:1 from (both test/ directories are empty),
so this is fresh coverage of the ported behavior."""

import pytest

from app.core.errors import ProblemError
from app.services import notification_render


class TestPlainSubstitution:
    def test_dot_path_substitution(self):
        assert notification_render.render_block("Hello {{user.name}}!", {"user": {"name": "Ada"}}) == "Hello Ada!"

    def test_missing_path_renders_empty(self):
        assert notification_render.render_block("[{{missing.path}}]", {}) == "[]"


class TestEach:
    def test_each_over_array_spreads_item_over_outer_data(self):
        template = "{{#each items}}{{sku}}={{owner}};{{/each}}"
        data = {"owner": "warehouse-1", "items": [{"sku": "A"}, {"sku": "B"}]}
        assert notification_render.render_block(template, data) == "A=warehouse-1;B=warehouse-1;"

    def test_each_over_non_array_renders_empty(self):
        assert notification_render.render_block("[{{#each items}}x{{/each}}]", {"items": "not-a-list"}) == "[]"
        assert notification_render.render_block("[{{#each items}}x{{/each}}]", {"items": None}) == "[]"

    def test_this_inside_each_over_primitives(self):
        template = "{{#each tags}}({{this}}){{/each}}"
        assert notification_render.render_block(template, {"tags": ["a", "b", "c"]}) == "(a)(b)(c)"


class TestIfTruthiness:
    @pytest.mark.parametrize("value", [True, "0", 1, "x", ["a"], {"k": "v"}])
    def test_truthy_values_render_body(self, value):
        assert notification_render.render_block("{{#if v}}shown{{/if}}", {"v": value}) == "shown"

    @pytest.mark.parametrize("value", [False, 0, "", None, []])
    def test_falsy_values_render_empty(self, value):
        assert notification_render.render_block("{{#if v}}shown{{/if}}", {"v": value}) == ""

    def test_empty_array_is_falsy_even_though_nonempty_arrays_are_truthy(self):
        assert notification_render.render_block("{{#if v}}shown{{/if}}", {"v": []}) == ""
        assert notification_render.render_block("{{#if v}}shown{{/if}}", {"v": [0]}) == "shown"


class TestNestingDepth:
    def test_depth_8_still_renders(self):
        """depth=8 itself doesn't raise (only depth>8 does) - a template
        with no further nested block at this level renders normally."""
        assert notification_render.render_block("{{x}}", {"x": "deep"}, depth=8) == "deep"

    def test_a_block_that_would_push_recursion_to_depth_9_raises(self):
        """Entering render_block at depth=8 with a template that itself
        contains one more block recurses to depth+1=9 for that inner body,
        which is where TEMPLATE_TOO_DEEP actually fires."""
        with pytest.raises(ProblemError) as exc:
            notification_render.render_block("{{#if x}}deep{{/if}}", {"x": True}, depth=8)
        assert exc.value.code == "TEMPLATE_TOO_DEEP"

    def test_depth_9_raises_immediately_regardless_of_template_content(self):
        with pytest.raises(ProblemError) as exc:
            notification_render.render_block("plain text, no blocks at all", {}, depth=9)
        assert exc.value.code == "TEMPLATE_TOO_DEEP"

    def test_alternating_each_and_if_nest_correctly_end_to_end(self):
        """Different helper types close on different literal tags
        ({{/each}} vs {{/if}}), so real nesting works even though the block
        regex itself has no notion of matching same-named pairs - depth
        tracking, not regex bracket-matching, is what makes this safe."""
        template = "{{#each rows}}{{#if active}}<{{label}}>{{/if}}{{/each}}"
        data = {"rows": [{"label": "one", "active": True}, {"label": "two", "active": False}]}
        assert notification_render.render_block(template, data) == "<one>"


class TestEscaping:
    def test_same_escaper_applies_to_plain_text_body_not_just_html(self):
        """The deliberately-preserved quirk: a value containing an apostrophe
        renders as literal &#39; in the PLAIN-TEXT body too, because render()
        shares one escaper across both bodies - do not special-case text."""
        data = {"name": "O'Brien & Sons <ltd>"}
        rendered = notification_render.render(subject=None, body_text="Dear {{name}},", body_html="<p>Dear {{name}},</p>", data=data)
        assert "&#39;" in rendered["text"]
        assert "&amp;" in rendered["text"]
        assert "&lt;" in rendered["text"]
        assert "O'Brien" not in rendered["text"]  # the raw apostrophe never survives


class TestHeaderInjection:
    def test_subject_with_crlf_is_blocked(self):
        with pytest.raises(ProblemError) as exc:
            notification_render.render(subject="Hi {{x}}", body_text="body", body_html=None, data={"x": "there\r\nBcc: evil@example.com"})
        assert exc.value.code == "HEADER_INJECTION_BLOCKED"

    def test_recipient_with_newline_is_blocked(self):
        with pytest.raises(ProblemError) as exc:
            notification_render.assert_no_header_injection("recipient", "a@example.com\nBcc: evil@example.com")
        assert exc.value.code == "HEADER_INJECTION_BLOCKED"


class TestPlausibleEmail:
    @pytest.mark.parametrize("value", ["a@example.com", "first.last@sub.example.co.in"])
    def test_accepts_plausible_addresses(self, value):
        assert notification_render.is_plausible_email(value) is True

    @pytest.mark.parametrize("value", ["not-an-email", "a@b", "a b@example.com", "@example.com"])
    def test_rejects_implausible_addresses(self, value):
        assert notification_render.is_plausible_email(value) is False
