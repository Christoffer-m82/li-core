"""Reviewed EN/SV trigger aliases, not translation or an authority/intent classifier.

Match only at word boundaries after Unicode normalisation. Keep original messages
for providers, history and memory; aliases select existing runtime paths only.
"""

import re
import unicodedata


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


# Explicit inflections avoid substring matches (e.g. mat in matematik).
ALIASES: dict[str, tuple[str, ...]] = {
    "health": ("hälsa", "hälsan"), "medical": ("medicinsk", "medicinska", "medicinskt"),
    "medicine": ("medicin", "medicinen"), "symptom": ("symtom", "symtomen", "symptomen"),
    "medication": ("läkemedel", "läkemedlet", "läkemedlen", "medicinering"),
    "doctor": ("läkare", "läkaren"), "clinical": ("klinisk", "kliniska", "kliniskt"),
    "fitness": ("kondition", "konditionen"), "workout": ("träningspass", "träningspasset"),
    "training": ("träning", "träningen", "träna"),
    "exercise": ("motion", "motionen", "övning", "övningar"),
    "strength": ("styrka", "styrkan", "styrketräning"), "cardio": ("konditionsträning",),
    "recovery": ("återhämtning", "återhämtningen"),
    "nutrition": ("näring", "kost", "kosten", "näringslära"),
    "food": ("mat", "maten", "livsmedel"), "recipe": ("recept", "receptet"),
    "cooking": ("matlagning", "laga mat"), "meal": ("måltid", "måltiden", "måltider"),
    "wine": ("vin", "vinet"), "cocktail": ("drink", "drinkar"),
    "relationship": ("relation", "relationen", "relationer", "förhållande"),
    "dating": ("dejting", "dejta"), "friendship": ("vänskap", "vänskapen"),
    "social": ("socialt", "sociala"), "conflict": ("konflikt", "konflikten", "konflikter"),
    "communication": ("kommunikation", "kommunikationen"),
    "parenting": ("föräldraskap", "föräldraskapet"), "child": ("barn", "barnet"),
    "children": ("barnen",), "family": ("familj", "familjen"),
    "co-parent": ("medförälder",), "father": ("pappa", "pappan"),
    "mother": ("mamma", "mamman"),
    "legal": ("juridisk", "juridiska", "juridiskt", "juridik"),
    "law": ("lag", "lagen", "lagar", "lagarna", "lagstiftning"),
    "contract": ("avtal", "avtalet", "kontrakt", "kontraktet"),
    "regulation": ("reglering", "regleringen", "förordning", "förordningar"),
    "regulatory": ("regulatorisk", "regulatoriska"),
    "employment": ("anställning", "anställningen", "arbetsrätt"),
    "court": ("domstol", "domstolen"),
    "finance": ("ekonomi", "ekonomin", "finanser", "privatekonomi"),
    "investment": ("investering", "investeringen", "investeringar"),
    "wealth": ("förmögenhet", "förmögenheten"), "pension": ("pensionen",),
    "tax": ("skatt", "skatten", "skatter", "skatteregler"),
    "cash flow": ("kassaflöde", "kassaflödet"), "budget": ("budgeten",),
    "business": ("affärsverksamhet", "affärer"),
    "commercial": ("kommersiell", "kommersiella", "kommersiellt"),
    "sales": ("försäljning", "försäljningen"), "pricing": ("prissättning",),
    "revenue": ("intäkter", "omsättning"),
    "negotiation": ("förhandling", "förhandlingen", "förhandlingar"),
    "leadership": ("ledarskap", "ledarskapet"), "igaming": ("igaming",),
    "research": ("forskning", "forskningen", "efterforskning"),
    "evidence": ("evidens", "bevis", "belägg"), "sources": ("källor", "källorna"),
    "fact-check": ("faktakolla", "faktagranska", "faktagranskning"),
    "investigate": ("undersök", "utred"), "competitive intelligence": ("konkurrentanalys",),
    "travel": ("resa", "resor", "resande"), "trip": ("resan",),
    "hotel": ("hotell", "hotellet"), "flight": ("flyg", "flyget", "flygning"),
    "holiday": ("ledighet", "ledigheten"), "vacation": ("semester", "semestern"),
    "itinerary": ("resplan", "resplanen"), "tickets": ("biljetter", "biljetterna"),
    "home": ("hem", "hemmet", "hemma"), "interior": ("inredning", "inredningen"),
    "furniture": ("möbler", "möblerna"), "lighting": ("belysning", "belysningen"),
    "plants": ("växter", "växterna"), "garden": ("trädgård", "trädgården"),
    "renovation": ("renovering", "renoveringen"),
    "wellbeing": ("välmående", "välbefinnande"), "habit": ("vana", "vanor", "vanorna"),
    "stress": ("stressen", "stressad"), "routine": ("rutin", "rutinen", "rutiner"),
    "motivation": ("motivationen",), "resilience": ("motståndskraft",),
    "burnout": ("utmattning", "utbrändhet"),
    "latest": ("senaste", "nyaste"), "today": ("idag", "i dag"),
    "current": ("aktuell", "aktuella", "aktuellt", "nuvarande"),
    "right now": ("just nu",), "this week": ("den här veckan", "denna vecka"),
    "recent": ("nyligen", "nylig", "nyliga"), "as of": ("per dagens datum",),
    "guideline": ("riktlinje", "riktlinjer", "riktlinjerna"),
    "safety alert": ("säkerhetsvarning", "säkerhetsvarningar"),
    "recall": ("återkallelse", "återkallelsen"),
    "clinical guidance": ("kliniska riktlinjer", "klinisk vägledning"),
    "diagnosis": ("diagnos", "diagnosen"), "treatment": ("behandling", "behandlingen"),
    "dose": ("dos", "dosen", "dosering"), "pregnan": ("gravid", "graviditet", "graviditeten"),
    "emergency": ("nödsituation", "akutfall", "akut"),
    "sports rule": ("idrottsregel", "idrottsregler"), "event schedule": ("evenemangsschema",),
    "product recall": ("produktåterkallelse", "produktåterkallelser"),
    "current research": ("aktuell forskning",),
    "injury": ("skada", "skadan", "skador"), "chest pain": ("bröstsmärta", "ont i bröstet"),
    "rehabilitation": ("rehabilitering", "rehab"),
    "food recall": ("livsmedelsåterkallelse",), "allergen alert": ("allergenvarning",),
    "current guideline": ("aktuell riktlinje", "aktuella riktlinjer"),
    "product availability": ("produkttillgänglighet", "lagerstatus"),
    "allergy": ("allergi", "allergin", "allergier"), "eating disorder": ("ätstörning", "ätstörningar"),
    "current service": ("aktuell tjänst",), "current local resource": ("aktuell lokal resurs",),
    "safety resource": ("säkerhetsresurs",), "school rule": ("skolregel", "skolregler"),
    "benefit rule": ("bidragsregel", "bidragsregler"), "child safety": ("barnsäkerhet",),
    "custody": ("vårdnad", "vårdnaden"), "jurisdiction": ("jurisdiktion", "jurisdiktionen"),
    "filing": ("inlämning",), "deadline": ("tidsfrist", "sista datum"),
    "legal requirement": ("lagkrav", "lagstadgat krav"),
    "legal advice": ("juridisk rådgivning",), "liability": ("skadeståndsansvar",),
    "rate": ("ränta", "räntan", "räntor"), "market": ("marknad", "marknaden", "marknader"),
    "yield": ("avkastning", "avkastningen"), "inflation": ("inflationen",),
    "price": ("pris", "priset", "priser", "kurs", "kursen", "aktiekurs", "aktiepris"),
    "invest": ("investera", "investerar", "placera"),
    "financial advice": ("finansiell rådgivning", "ekonomisk rådgivning"),
    "mortgage": ("bolån", "bolånet", "bolåneränta"),
    "competitor": ("konkurrent", "konkurrenter"), "company": ("företag", "företaget", "bolag"),
    "operator launch": ("operatörslansering",), "verify": ("verifiera", "kontrollera"),
    "source": ("källa", "källan"), "claim": ("påstående", "påståendet"),
    "entry requirement": ("inresekrav", "inresekraven"), "visa": ("visum", "visumkrav"),
    "schedule": ("tidtabell", "tidtabellen", "schema", "schemat"),
    "strike": ("strejk", "strejken"), "closure": ("stängning", "avstängning"),
    "advisory": ("reseavrådan", "reseråd"), "weather": ("väder", "vädret"),
    "event": ("evenemang", "evenemanget"), "ticket": ("biljett", "biljetten"),
    "restaurant": ("restaurang", "restaurangen"), "plant season": ("växtsäsong",),
    "seasonal": ("säsongsbetonad", "säsongsanpassad", "säsong"),
    "safety": ("säkerhet", "säkerheten"), "workplace rule": ("arbetsplatsregel",),
    "self-harm": ("självskada", "självskadebeteende", "skada mig själv"),
    "suicide": ("självmord", "ta mitt liv"), "crisis": ("kris", "krisen"),
    "quote": ("börskurs",), "spot": ("spotpris",), "trading": ("värdepappershandel",),
    "ticker": ("aktiesymbol",), "bitcoin": ("bitcoin",), "stock": ("aktie", "aktien", "aktier"),
    "compare": ("jämför", "jämföra"), "trade-offs": ("avvägningar",),
    "options": ("alternativ", "alternativen"), "recommend": ("rekommendera", "rekommenderar"),
    "decision": ("beslut", "beslutet"), "choose": ("välj", "välja", "väljer"),
    "evaluate": ("utvärdera",), "plan": ("planera", "planen"),
    "strategy": ("strategi", "strategin"), "pros and cons": ("fördelar och nackdelar",),
    "my": ("min", "mitt", "mina"), "me": ("mig",),
    "based on what you know": ("utifrån vad du vet", "baserat på vad du vet"),
    "near me": ("nära mig",), "nearby": ("i närheten",), "local": ("lokal", "lokala"),
    "shop": ("butik", "butiken", "affär", "affären"), "service": ("tjänst", "tjänsten"),
    "insurance": ("försäkring", "försäkringen"), "delivery": ("leverans", "leveransen"),
    "currency": ("valuta", "valutan"), "permit": ("tillstånd", "tillståndet"),
    "government": ("regering", "regeringen"), "bank": ("banken",),
    "plant": ("växt", "växten"), "license": ("licens", "licensen"),
    "cafe": ("kafé", "kaféet", "café", "caféet"), "local service": ("lokal tjänst",),
    "hospital": ("sjukhus", "sjukhuset"), "airport": ("flygplats", "flygplatsen"),
    "garden center": ("handelsträdgård", "handelsträdgården"),
}


def has_term(text: str, term: str, *, english_plural: bool = False) -> bool:
    text = normalize(text)
    suffix = r"(?:s|es)?" if english_plural else ""
    if term == "pregnan":
        english = r"(?<!\w)pregnan\w*"
    else:
        english = rf"(?<!\w){re.escape(term)}{suffix}(?!\w)"
    return bool(re.search(english, text)) or any(
        re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text)
        for alias in ALIASES.get(term, ())
    )


def requests_history(text: str) -> bool:
    phrases = (
        "we discussed", "previous conversation", "last year", "what was that",
        "do you remember", "earlier chat", "vi diskuterade", "vi pratade om",
        "tidigare samtal", "förra året", "vad var det", "minns du", "kommer du ihåg",
        "tidigare chatt", "förra samtalet",
    )
    return any(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", normalize(text)) for p in phrases)


UNICODE_WORD = re.compile(r"\b[^\W\d_][\w'’-]*\b")
SWEDISH_QUERY_STOPWORDS = frozenset({
    "att", "det", "den", "detta", "dessa", "vad", "vilken", "vilka", "hur", "varför",
    "när", "kan", "kunde", "skulle", "vill", "jag", "mig", "min", "mitt", "mina",
    "du", "dig", "din", "ditt", "dina", "med", "för", "från", "och", "eller", "som",
    "har", "hade", "är", "var", "berätta", "snälla", "utifrån", "baserat",
})
