import string
import unittest
import datetime
import pyparsing as pp
from .nodes import WordNode, PhraseNode, FieldNode, OrNode, AndNode, MustNode, NotNode, JoinNode, RangeNode, UnaryOperatorNode, MustNotNode


def dateify(string, location, tokens):
    return datetime.date(year=int(tokens[0]), month=int(tokens[1]), day=int(tokens[2])).strftime("%Y-%m-%d")


unicode_printables = ''.join(chr(c) for c in range(65536) if not chr(c).isspace())
reserved = "()\\"
unreserved_printables = ''.join(chr(c) for c in range(65536) if chr(c) not in reserved and not chr(c).isspace())


def get_parser(phrase_class=PhraseNode, word_class=WordNode, field_class=FieldNode):
    stack = []
    def push(string, location, tokens):
        for t in tokens:
            stack.append(t)
            break
        else:
            return

        # join nodes should merge adjacent word nodes if possible 
        if isinstance(t, JoinNode):
            a = stack[-2]
            b = stack[-3]
            if isinstance(a, word_class) and isinstance(b, word_class):
                stack.pop()
                stack.pop()
                stack.pop()
                stack.append(word_class(b.token + " " + a.token))
            else:
                stack[-1] = OrNode()

    def push_unary(string, location, tokens):
        for t in tokens:
            if isinstance(t, UnaryOperatorNode):
                stack.append(t)
            break

    phrase = phrase_class.wrap(pp.QuotedString('"', unquoteResults=True, escChar='\\'))
    #word = word_class.wrap(pp.Word(unicode_printables))

    and_ = AndNode.wrap(pp.CaselessKeyword("AND"))
    or_ = OrNode.wrap(pp.CaselessKeyword("OR"))
    not_ = NotNode.wrap(pp.CaselessKeyword("NOT"))

    must = MustNode.wrap(pp.CaselessLiteral("+"))
    must_not = NotNode.wrap(pp.CaselessLiteral("-"))
    musty = not_ | must_not | must

    escape = pp.Suppress(pp.Literal("\\")) + pp.Word(unicode_printables, exact=1)
    escape_word = word_class.wrap(pp.Combine(pp.OneOrMore(escape ^ pp.Word(unreserved_printables))))

    inclusive_left = pp.Literal("[")
    inclusive_right = pp.Literal("]")
    exclusive_left = pp.Literal("{")
    exclusive_right = pp.Literal("}")
    to_ = pp.CaselessKeyword("TO")
    year = pp.Regex("[0-9]{4}")
    month = pp.Regex("[0-9]{1,2}")
    day = pp.Regex("[0-9]{1,2}")
    lt = pp.Literal("<")
    gt = pp.Literal(">")
    gte = pp.Literal(">=")
    lte = pp.Literal("<=")
    fnumber = pp.Regex(r"[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")

    # range
    date = (year + pp.Suppress("-") + month + pp.Suppress("-") + day).addParseAction(dateify)
    compare = (lte | gte | lt | gt) + (date | fnumber).setResultsName("value")
    range_val = date | fnumber # | pp.Literal("*")
    range_ = compare | ((inclusive_left | exclusive_left) + range_val.setResultsName("left") + to_ + range_val.setResultsName("right") + (inclusive_right | exclusive_right))
    range_ = RangeNode.wrap(range_)

    # strand
    strand = pp.Forward()
    atom = ((musty*(0, 1)) + (pp.Group(pp.Suppress("(") + strand + pp.Suppress(")")) | (phrase | escape_word).addParseAction(push))).addParseAction(push_unary)
    factor = atom + pp.ZeroOrMore((and_ + atom).addParseAction(push))
    strand <<= factor + pp.ZeroOrMore((pp.Optional(or_, default=JoinNode()) + factor).addParseAction(push))

    # field
    field_value = (pp.Suppress("(") + strand + pp.Suppress(")")) | (phrase | range_ | escape_word).addParseAction(push)
    field_key = pp.Word(string.ascii_letters + "_.-" + string.digits, excludeChars=':') + pp.Suppress(":")
    field = (field_class.wrap(field_key) + field_value).addParseAction(lambda l, s, tokens: stack.append(tokens[0]))

    # query
    query = pp.Forward()
    atom = ((musty*(0, 1)) + (pp.Group(pp.Suppress("(") + query + pp.Suppress(")")) | field | (phrase | escape_word).addParseAction(push))).addParseAction(push_unary)
    factor = atom + pp.ZeroOrMore((and_ + atom).addParseAction(push))
    query <<= factor + pp.ZeroOrMore((pp.Optional(or_, default=JoinNode()) + factor).addParseAction(push))
    #all_query = pp.OneOrMore(query)

    return {
        "query": query,
        "range": range_,
        "word": escape_word,
        "strand": strand,
        "field": field,
        "stack": stack,
    }


class Parser():
    def __init__(self, *, field_class=FieldNode, word_class=WordNode, phrase_class=PhraseNode):
        parser = get_parser(field_class=field_class, word_class=word_class, phrase_class=phrase_class)
        self.query = parser['query']
        self.stack = parser['stack']
        self.field_class = field_class

    def __call__(self, query_string, default_field="_all"):
        self.stack.clear()
        result = self.query.parseString(query_string)
        self.default_field = self.field_class(default_field)
        self.default_field.is_default = True
        json_blob = self.eval()
        return json_blob

    def eval(self, field=None, top_level=True, field_level=False, must=None, must_not=None):
        if top_level:
            expr = {
                "bool": {
                    "should": [],
                    "must": [],
                    "must_not": []
                }
            }

        push_musts = top_level or field_level
        if top_level:
            must = expr['bool']['must']
            must_not = expr['bool']['must_not']
        elif field_level:
            must = []
            must_not = []

        new_field_level = field_level
        if field_level == True:
            new_field_level = False


        while len(self.stack) != 0:
            op = self.stack.pop()

            if isinstance(op, FieldNode):
                field = op
                val = self.eval(field, top_level=False, must=must, must_not=must_not, field_level=True)
                return val
            elif isinstance(op, WordNode) or isinstance(op, RangeNode) or isinstance(op, PhraseNode):
                return op.to_query(field or self.default_field)
            elif isinstance(op, OrNode):
                op1 = self.eval(field=field, top_level=False, must=must, must_not=must_not, field_level=new_field_level)
                op2 = self.eval(field=field, top_level=False, must=must, must_not=must_not, field_level=new_field_level)
                #if not top_level:
                return {
                    "bool": {
                        "should": [op1, op2],
                        "minimum_should_match": 1,
                        "must": must if push_musts else [],
                        "must_not": must_not if push_musts else []
                    }
                }
                    #else:
                    #expr['bool']['should'].extend([op1, op2])
            elif isinstance(op, AndNode):
                op1 = self.eval(field=field, top_level=False, must=must, must_not=must_not, field_level=new_field_level)
                op2 = self.eval(field=field, top_level=False, must=must, must_not=must_not, field_level=new_field_level)
                #if not top_level:
                return {
                    "bool": {
                        "must": [op1, op2] + (must if push_musts else []),
                        "must_not": (must_not if push_musts else [])
                    }
                }
            elif isinstance(op, NotNode):
                op1 = self.eval(field=field, top_level=False, must=must, must_not=must_not, field_level=new_field_level)
                return {
                    "bool": {
                        "must_not": [op1] + (must_not if push_musts else []),
                        "must": (must if push_musts else [])
                    }
                }
            elif isinstance(op, MustNode):
                op1 = self.eval(field=field, top_level=False, must=must, must_not=must_not, field_level=new_field_level)
                must.append(op1)
                return None 
            elif isinstance(op, MustNotNode):
                op1 = self.eval(field=field, top_level=False, must=must, must_not=must_not, field_level=new_field_level)
                must_not.append(op1)
                return None 
            else:
                print("WRONG")

        return expr


if __name__ == '__main__':
    #reserved = "()\\"
    #unreserved_printables = ''.join(chr(c) for c in range(65536) if chr(c) not in reserved and not chr(c).isspace())
    #escape = pp.Suppress(pp.Literal("\\")) + pp.Word(unicode_printables, exact=1)
    #word = pp.Combine(pp.OneOrMore(escape ^ pp.Word(unreserved_printables)))
    #print(word.parseString("as\\(\\dfj\\dca\\t\\"))
    #import pdb; pdb.set_trace()
    #unittest.main()
    #query.parseString("name:>10")
    parser = Parser(field_class=MyFieldNode, word_class=MyWordNode, phrase_class=MyPhraseNode)
    result = parser("title:weather AND words:>10 AND im ages:>=6 \"foo\"")
    import json

    ##result = MyStackEvaluator(stack, "corpus")
    #result = result.eval()
    print(json.dumps({"query": result}, indent=4))
