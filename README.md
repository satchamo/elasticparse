# elasticparse

Safely turn user search strings into safe elasticsearch queries.

# The Problem

You want to give users the ability to input complex search queries to run on your elasticsearch cluster. Using the <a href="https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html">query_string</a> is not a good option for several reasons:

1. Users can DoS your cluster with wildcard queries and regular expressions
2. You don't want to expose your non-human friendly field names to users 
3. You want to adjust the query before it runs (for example, to make sure quoted strings don't use your ngram analyzed field)

# The Solution

elasticparse parses lucene style query strings, and generates elasticsearch queries.

```python
from elasticparse import parse
import json

query = parse("-title:District AND (actors:(sharlto copley) AND rating:>=6 action)")

print(json.dumps(query, indent=4))
```

```json
{
    "bool": {
        "should": [],
        "must": [
            {
                "bool": {
                    "should": [
                        {
                            "match": {
                                "_all": {
                                    "query": "action"
                                }
                            }
                        },
                        {
                            "bool": {
                                "must": [
                                    {
                                        "range": {
                                            "rating": {
                                                "gte": "6"
                                            }
                                        }
                                    },
                                    {
                                        "match": {
                                            "actors": {
                                                "query": "sharlto copley"
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            {
                "bool": {
                    "must_not": {
                        "match": {
                            "title": {
                                "query": "District"
                            }
                        }
                    }
                }
            }
        ]
    }
}

```
