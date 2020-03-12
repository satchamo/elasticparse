class Node:
    def __init__(self, string=None, location=None, tokens=None):
        # We want to handle instantiation from a pyparsing expression, or just
        # passing in a token like: `Node('foo')`
        if location == None:
            self.token = string or self.TOKEN
        else:
            # create from a pyparsing expression
            for t in tokens:
                self.token = t
                break
            else:
                raise ValueError("This shouldn't happen")
        
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, repr(self.token))

    @classmethod
    def wrap(cls, expr):
        expr = expr.copy()
        expr.addParseAction(cls)
        return expr

    def __eq__(self, other):
        return other.__class__ == self.__class__ and self.token == other.token

    def to_query(self, field):
        raise NotImplementedError("You need to implement to_query")


class WordNode(Node):
    def to_query(self, field):
        return {
            "match": {
                field.get_name(self): {
                    "query": self.token
                }
            }
        }


class PhraseNode(Node):
    def to_query(self, field):
        return {
            "match_phrase": {
                field.get_name(self): self.token
            }
        }


class FieldNode(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_default = False

    def get_name(self, node):
        return self.token

    @property
    def is_default(self):
        return self._is_default

    @is_default.setter
    def is_default(self, val):
        self._is_default = val


class OperatorNode(Node):
    def __repr__(self):
        return '%s()' % (self.__class__.__name__)


class BooleanOperatorNode(OperatorNode):
    pass


class UnaryOperatorNode(OperatorNode):
    pass


class OrNode(BooleanOperatorNode):
    TOKEN = "OR"


class JoinNode(BooleanOperatorNode):
    TOKEN = ">-<"


class AndNode(BooleanOperatorNode):
    TOKEN = "AND"


class NotNode(UnaryOperatorNode):
    TOKEN = "NOT"


class MustNotNode(UnaryOperatorNode):
    TOKEN = "-"


class MustNode(UnaryOperatorNode):
    TOKEN = "+"


class RangeNode(Node):
    def __init__(self, string=None, location=None, tokens=None):
        if location == None:
            self.token = string
        else:
            first = tokens[0]
            last = tokens[-1]
            if first == ">":
                self.token = {"gt": tokens.get("value")[0]}
            elif first == ">=":
                self.token = {"gte": tokens.get("value")[0]}
            elif first == "<":
                self.token = {"lt": tokens.get("value")[0]}
            elif first == "<=":
                self.token = {"lte": tokens.get("value")[0]}
            else:
                left = tokens['left'][0]
                right = tokens['right'][0]
                stop = "lte" if last == "]" else "lt"
                start = "gte" if first == "[" else "gt"
                self.token = {start: left, stop: right}

    def to_query(self, field):
        return {
            "range": {
                field.get_name(self): self.token
            }
        }

