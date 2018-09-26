from elasticparse import WordNode, PhraseNode, FieldNode, RangeNode, Parser, parse
import json

def pretty_print(result):
    print(json.dumps({"query": result}, indent=4))

# simple
pretty_print(parse("-title:District AND (actors:(sharlto copley) AND rating:>=6 action)"))

pretty_print(parse("a or b and c"))


"""
Complex
In this example, we have this elasticsearch mapping like:

{
  "corpus" : {
    "type" : "text",
    "fields" : {
      "ngram" : {
        "type" : "text",
        "analyzer" : "my_analyzer"
      }
    }
  },
  "images_count" : {
    "type" : "integer"
  },
  "items_count" : {
    "type" : "integer"
  },
  "name" : {
    "type" : "text",
    "fields" : {
      "ngram" : {
        "type" : "text",
        "analyzer" : "my_analyzer"
      }
    }
  },
  "words_count" : {
    "type" : "integer"
  }
}

(note the corpus.ngram, and name.ngram subfields)

We want to allow the user to search using friendly field aliases:

- "title" (which maps to the "name" Elasticsearch field)
- "words" (which maps to the "corpus" or "words_count" field, depending on the context)
- "images" (images_count)
- "count" (items_count)

If no field is specified, we want to search the corpus and name fields using a multi_match query.

The "words" (corpus) and "title" (name) fields should map to their respective subfields (corpus.ngram, name.ngram), except if the user's search term is wrapped in quotes (PhraseNode).

To achive all this, we need to implement our own WordNode, PhraseNode, and FieldNode class.
"""

class MyWordNode(WordNode):
    def to_query(self, field):
        # if this word is attached to the default field, use a multi_match query on the ngram subfields
        if field.is_default:
            return {
                "multi_match": {
                    "query": self.token,
                    "fields": ["name.ngram", "corpus.ngram"]
                }
            }
        else:
            return super().to_query(field)


class MyPhraseNode(WordNode):
    def to_query(self, field):
        # if this phrase is attached to the default field, use a multi_match query
        if field.is_default:
            return {
                "multi_match": {
                    "query": self.token,
                    "fields": ["name", "corpus"]
                }
            }
        else:
            return super().to_query(field)


class MyFieldNode(FieldNode):
    def get_name(self, node):
        # the user types in "friendly" field names, and we need to handle translating those to
        # the actual field name in ES.

        # For text fields, we have a subfield called ".ngram". For simple word queries,
        # we use the ngram subfield. For phrase queries, we use the field directly.
        if self.token == "title":
            if isinstance(node, WordNode):
                return "name.ngram"
            else:
                return "name"
        elif self.token == "count":
            return "items_count"
        elif self.token == "images":
            return "images_count"
        elif self.token == "words":
            if isinstance(node, RangeNode):
                # for range queries, use the words_count field
                return "words_count"
            elif isinstance(node, WordNode):
                # for word queries use the ngram
                return "corpus.ngram"
            elif isinstance(node, PhraseNode):
                # for phrase queries use base field
                return "corpus"
            else:
                raise ValueError("This shouldn't happen!")

        return super().get_name(node)


parser = Parser(field_class=MyFieldNode, word_class=MyWordNode, phrase_class=MyPhraseNode)
result = parser("title:weather AND words:>10 AND images:>=6 hurricane")
