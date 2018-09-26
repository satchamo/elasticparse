import datetime
import json
import pyparsing as pp
import unittest

from .grammar import get_parser
from .nodes import WordNode, PhraseNode, FieldNode, OrNode, AndNode, MustNode, NotNode, JoinNode, RangeNode, UnaryOperatorNode
from . import parse


def pretty_print(result):
    print(json.dumps({"query": result}, indent=4))


class ParserTestCase(unittest.TestCase):
    def setUp(self):
        for k, v in get_parser().items():
            setattr(self, k, v)

    def assertMatch(self, parser, input):
        self.stack.clear()
        parser.parseString(input, parseAll=True)

    def assertNoMatch(self, parser, input):
        self.stack.clear()
        try:
            parser.parseString(input, parseAll=True)
        except pp.ParseException:
            pass
        else:
            raise ValueError('match should fail', input)

    def assertStack(self, result):
        self.assertEqual(self.stack, result)

    def test_word(self):
        self.assertMatch(self.word, "foo")
        self.assertMatch(self.word, "bar")
        self.assertMatch(self.word, "bar.fog")
        self.assertMatch(self.word, "bar-fog")

    def test_range(self):
        self.assertMatch(self.range, "[5 TO 10}")
        result = self.range.parseString("[5 TO 10]")
        self.assertEqual(result[0], RangeNode({
            "lte": '10',
            "gte": '5'
        }))

        result = self.range.parseString("[5 TO 10}")
        self.assertEqual(result[0], RangeNode({
            "lt": '10',
            "gte": '5'
        }))
        result = self.range.parseString("{5 TO 10}")
        self.assertEqual(result[0], RangeNode({
            "lt": '10',
            "gt": '5'
        }))
        result = self.range.parseString(">10")
        self.assertEqual(result[0], RangeNode({
            "gt": '10'
        }))
        result = self.range.parseString("<10")
        self.assertEqual(result[0], RangeNode({
            "lt": '10'
        }))
        result = self.range.parseString("<=10")
        self.assertEqual(result[0], RangeNode({
            "lte": '10'
        }))
        result = self.range.parseString(">= 10.5")
        self.assertEqual(result[0], RangeNode({
            "gte": '10.5'
        }))

        result = self.range.parseString(">= 2012-12-10")
        self.assertEqual(result[0], RangeNode({
            "gte": datetime.date(2012, 12, 10)
        }))

    def test_strand(self):
        self.assertMatch(self.strand, "a or b")
        self.assertStack([WordNode("a"), WordNode("b"), OrNode()])

        self.assertMatch(self.strand, "a and b")
        self.assertStack([WordNode("a"), WordNode("b"), AndNode()])

        self.assertMatch(self.strand, "a and b or c")
        self.assertStack([WordNode("a"), WordNode("b"), AndNode(), WordNode("c"), OrNode()])

        self.assertMatch(self.strand, "a and (b or c)")
        self.assertStack([WordNode("a"), WordNode("b"), WordNode("c"), OrNode(), AndNode()])

        self.assertMatch(self.strand, "(a and (b or c))")
        self.assertStack([WordNode("a"), WordNode("b"), WordNode("c"), OrNode(), AndNode()])

        self.assertMatch(self.strand, "(a and (b or c)) or d")
        self.assertStack([WordNode("a"), WordNode("b"), WordNode("c"), OrNode(), AndNode(), WordNode("d"), OrNode()])

        self.assertMatch(self.strand, "(a and (b or c)) or (d)")

        self.assertMatch(self.strand, '"a" or ("c")')
        self.assertStack([PhraseNode("a"), PhraseNode("c"), OrNode()])

        self.assertMatch(self.strand, '("a" or ("c"))')
        self.assertStack([PhraseNode("a"), PhraseNode("c"), OrNode()])

        self.assertMatch(self.strand, '(a b)')
        self.assertStack([WordNode("a b")])

        self.assertMatch(self.strand, "(a b\\))")
        self.assertStack([WordNode("a b)")])

        self.assertMatch(self.strand, "(\"a)")
        self.assertStack([WordNode("\"a")])

        self.assertMatch(self.strand, "(k OR a OR b OR c AND d)")
        #print(stack)

        self.assertMatch(self.strand, "(k a b c AND d)")
        self.assertMatch(self.strand, "NOT a")
        self.assertStack([WordNode("a"), NotNode()])

        self.assertMatch(self.strand, "a NOT b c")
        self.assertStack([WordNode("a"), WordNode("b"), NotNode(), OrNode(), WordNode("c"), OrNode()])

        self.assertMatch(self.strand, "NOT (a b)")
        self.assertStack([WordNode('a b'), NotNode()])

    def test_field(self):
        self.assertMatch(self.field, "foo:a")
        self.assertNoMatch(self.field, "foo:a or b")
        self.assertMatch(self.field, "foo:>10")
        self.assertMatch(self.field, "foo:(a b or d)")
        self.assertMatch(self.field, "foo:(a b d)")
        self.assertNoMatch(self.field, "foo\\:a")

    def test_query(self):
        self.assertMatch(self.query, "foo:a")
        self.assertStack([WordNode('a'), FieldNode("foo")])

        self.assertMatch(self.query, "foo:a or b")
        self.assertStack([WordNode('a'), FieldNode("foo"), WordNode("b"), OrNode()])

        self.assertMatch(self.query, "foo:>10")
        self.assertStack([RangeNode({"gt": "10"}), FieldNode("foo")])

        self.assertMatch(self.query, "foo:(a b or d)")
        self.assertMatch(self.query, "foo:(a b d)")
        self.assertMatch(self.query, "a b")
        self.assertMatch(self.query, "foo:f bar:b c")
        self.assertStack([WordNode("f"), FieldNode("foo"), WordNode("b"), FieldNode("bar"), OrNode(), WordNode("c"), OrNode()])

        self.assertMatch(self.query, "foo\\:f")
        self.assertStack([WordNode("foo:f")])

        self.assertMatch(self.query, "(a:b c:d)")
        #print(self.stack)

    def test_es(self):
        #pretty_print(parse("field:(foo +bar)"))
        pretty_print(parse("name:(hi -asdfjasdf lame sdf) corpus:butt"))

if __name__ == '__main__':
    unittest.main()
