"""Authored reading text and explicit pair coverage; no dictionary claims for test strings."""
from string import ascii_lowercase, ascii_uppercase

PARAGRAPHS = [
    "Morning light was coming through the kitchen window when I began packing my bag. We were going somewhere new for the weekend, so I checked the address again before leaving. At the garden gate, a neighbor asked whether we could bring back a small jar of honey from the market.",
    "The library was changing its opening hours at the beginning of the month. Our group met there on Tuesday to plan a small reading event. We agreed to leave the main entrance clear, hang a sign near the stairs, and give visitors a quiet place to sit after lunch.",
    "On the way home, we stopped at the shop for eggs, rice, and a bag of apples. A dog was waiting beside the door while its owner paid for groceries. The bus arrived just as we reached the crossing, and I was glad to put the shopping down for a while.",
]
FOCUS_WORDS = "Morning beginning changing going"
CHECKPOINT_TEXT = (
    "Morning light was changing as we crossed the bridge. A good beginning meant "
    "going slowly, watching the garden and reading the signs."
)
CHECKPOINT_WEIGHTS = (100, 400, 700, 900)

# None means no sufficiently ordinary English word was selected, not that none exists.
INCOMING_WORDS = {
    "ag": ("again", "bag"), "bg": ("subgroup",), "cg": None,
    "dg": ("edge", "bridge"), "eg": ("begin", "regular"), "fg": ("afghan",),
    "gg": ("egg", "bigger"), "hg": ("churchgoer", "beachgoer"),
    "ig": ("big", "signal"), "jg": None, "kg": ("background", "backgammon"),
    "lg": ("bulge", "algae"), "mg": None, "ng": ("morning", "changing"),
    "og": ("dog", "together"), "pg": ("upgrade",), "qg": None,
    "rg": ("large", "target"), "sg": ("disguise", "disgust"),
    "tg": ("outgrow", "outgoing"), "ug": ("ugly", "sugar"), "vg": None,
    "wg": ("showgirl",), "xg": None, "yg": ("oxygen", "hygiene"), "zg": None,
}
OUTGOING_WORDS = {
    "ga": ("garden", "began"), "gb": ("rugby",), "gc": ("dogcatcher",),
    "gd": ("kingdom",), "ge": ("gentle", "page"), "gf": ("bagful", "dogfight"),
    "gg": ("egg", "bigger"), "gh": ("light", "doghouse"),
    "gi": ("give", "begin"), "gj": ("logjam",), "gk": None,
    "gl": ("glass", "ugly"), "gm": ("segment", "pigment"),
    "gn": ("sign", "signal"), "go": ("going", "ago"), "gp": ("bagpipes",),
    "gq": None, "gr": ("green", "group"), "gs": ("eggs", "bags"),
    "gt": ("length", "strength"), "gu": ("guide", "argue"), "gv": None,
    "gw": ("dogwood", "ragweed"), "gx": None, "gy": ("energy", "baggy"),
    "gz": ("zigzag",),
}


def pair_rows(direction):
    words = INCOMING_WORDS if direction == "incoming" else OUTGOING_WORDS
    expected = [letter + "g" if direction == "incoming" else "g" + letter
                for letter in ascii_lowercase]
    assert list(words) == expected
    rows = []
    for pair, examples in words.items():
        kind = "word" if examples else "synthetic"
        examples = list(examples) if examples else ["ha" + pair + "an"]
        assert all(pair in word and word.isascii() and word.islower() for word in examples)
        rows.append({"direction": direction, "pair": pair, "kind": kind,
                     "examples": examples, "text": " · ".join(examples)})
    return rows


ROWS = pair_rows("incoming") + pair_rows("outgoing")
CAPITAL_PAIRS = [letter + "g" for letter in ascii_uppercase]
BOUNDARIES = [
    {"label": "Spaces and word ends", "runs": [
        "g", "g g", "n g", "g n", "a dog went home", "a big green bag",
    ]},
    {"label": "Punctuation at either side", "runs": [
        "(g)", "[g]", "{g}", "‘g’", "“g”", "'g'", '"g"',
        "g, g.", "g: g;", "g! g?", "g-g", "g–g", "g—g",
    ]},
    {"label": "Fixed outgoing spacing and unchanged incoming controls", "runs": [
        "ng hg mg ug", "go ge gc gj", "ngj ngo nge ngc",
    ]},
]
PUNCTUATION_PAIRS = [mark + "g" for mark in "([{‘“'\""] + [
    "g" + mark for mark in ")]},.:;!?‘’“”'\"-–—"
]


def inventory():
    return {
        "scope": "Plain Latin lowercase pairs in both directions, capital-before-g and listed boundaries; not every glyph or language",
        "paragraphs": PARAGRAPHS, "focus_words": FOCUS_WORDS,
        "checkpoint_text": CHECKPOINT_TEXT, "checkpoint_weights": list(CHECKPOINT_WEIGHTS),
        "rows": ROWS, "capital_pairs": CAPITAL_PAIRS, "boundaries": BOUNDARIES,
        "counts": {
            "incoming_rows": 26, "outgoing_rows": 26,
            "unique_lowercase_pairs": len({row["pair"] for row in ROWS}),
            "word_rows": sum(row["kind"] == "word" for row in ROWS),
            "synthetic_rows": sum(row["kind"] == "synthetic" for row in ROWS),
            "capital_pairs": len(CAPITAL_PAIRS),
            "boundary_runs": sum(len(group["runs"]) for group in BOUNDARIES),
        },
        "lexical_note": "Authored examples, not an exhaustive dictionary search. Afghan denotes a blanket; closed compounds deliberately preserve the tested adjacent letters. Test strings are explicitly labeled and make no word claim.",
    }


def test_strings():
    strings = [*PARAGRAPHS, FOCUS_WORDS, CHECKPOINT_TEXT, *CAPITAL_PAIRS, *PUNCTUATION_PAIRS]
    for row in ROWS:
        strings.extend((row["pair"], row["text"], *row["examples"]))
    strings.extend(run for group in BOUNDARIES for run in group["runs"])
    return list(dict.fromkeys(strings))
