import unittest


from realtime_stt_writer.inject.formatting import format_for_insert


class FormattingTests(unittest.TestCase):
    def test_formats_sentence_with_trailing_newline_for_obsidian_default(self) -> None:
        formatted = format_for_insert("I want to ask about the homework")

        self.assertEqual(formatted, "I want to ask about the homework.\n")

    def test_preserves_existing_terminal_punctuation(self) -> None:
        formatted = format_for_insert("Can I join tomorrow?", separator="\n")

        self.assertEqual(formatted, "Can I join tomorrow?\n")


if __name__ == "__main__":
    unittest.main()
