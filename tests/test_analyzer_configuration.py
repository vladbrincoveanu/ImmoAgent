from Project.Application.analyzer import StructuredAnalyzer


def test_structured_analyzer_preserves_outlines_wait_timeout():
    analyzer = StructuredAnalyzer(outlines_wait_timeout=1.75)

    assert analyzer.outlines_wait_timeout == 1.75
