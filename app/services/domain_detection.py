from ..types import ProjectRecord

TECH_NEEDLES = (
    "ai",
    "artificial intelligence",
    "llm",
    "gpu",
    "tpu",
    "chip",
    "chips",
    "semiconductor",
    "inference",
    "datacenter",
    "data center",
    "compute",
    "server",
    "agent",
    "agents",
    "obscura",
    "browser",
    "headless",
    "javascript",
    "v8",
    "cdp",
    "fingerprint",
    "automation",
    "scraping",
    "data extraction",
    "github",
    "open source",
    "terminal",
    "console",
)

BROAD_TECH_NEEDLES = (
    "research",
    "model",
    "models",
    "training",
)

TECH_CONTEXT_NEEDLES = (
    "ai",
    "artificial intelligence",
    "llm",
    "gpu",
    "tpu",
    "inference",
    "model training",
    "neural",
    "chip",
    "semiconductor",
    "datacenter",
    "data center",
    "browser",
    "headless",
    "automation",
    "javascript",
)

AGRICULTURE_ENVIRONMENT_NEEDLES = (
    "agriculture",
    "agricultural",
    "farm",
    "field",
    "soil",
    "crop",
    "crops",
    "leaf",
    "leaves",
    "mulch",
    "mulching",
    "biodegradable",
    "microplastic",
    "plastic waste",
    "plant",
    "sprout",
    "seed",
    "germination",
    "water retention",
    "moisture",
    "compost",
)

SCIENCE_MATERIALS_NEEDLES = (
    "polymer",
    "nanocellulose",
    "cellulose",
    "material",
    "materials",
    "film",
    "thin film",
    "composite",
    "biopolymer",
    "lab",
    "laboratory",
    "extraction",
    "decomposition",
    "degrade",
    "degradation",
    "water-based",
    "sample",
)

NEWS_EXPLAINER_NEEDLES = (
    "news",
    "article",
    "comment",
    "comments",
    "reply",
    "likes",
    "dislikes",
    "election",
    "public opinion",
    "media company",
    "press",
    "newsroom",
    "sort order",
    "sorting",
    "notification",
    "email",
    "anomaly",
    "spike",
    "manipulation",
    "coordinated",
    "뉴스",
    "기사",
    "댓글",
    "답글",
    "공감",
    "비공감",
    "선거",
    "대선",
    "여론",
    "언론사",
    "언론",
    "정렬",
    "알림",
    "메일",
    "이상 징후",
    "급증",
    "폭증",
    "좌표찍기",
    "조직적",
    "왜곡",
)

NEWS_EXPLAINER_STRONG_NEEDLES = (
    "comment",
    "comments",
    "reply",
    "likes",
    "dislikes",
    "election",
    "public opinion",
    "media company",
    "press",
    "newsroom",
    "sort order",
    "sorting",
    "notification",
    "email",
    "anomaly",
    "spike",
    "manipulation",
    "coordinated",
    "\ub313\uae00",
    "\uacf5\uac10",
    "\ube44\uacf5\uac10",
    "\uc120\uac70",
    "\uc5ec\ub860",
    "\uc5b8\ub860\uc0ac",
    "\uc54c\ub9bc",
    "\uba54\uc77c",
    "\uc774\uc0c1 \uc9d5\ud6c4",
    "\uae09\uc99d",
    "\uc870\uc9c1\uc801",
)

AI_POLICY_CONFLICT_NEEDLES = (
    "anthropic",
    "claude",
    "openai",
    "google",
    "white house",
    "defense department",
    "defense secretary",
    "senate",
    "hearing",
    "government",
    "federal",
    "national security",
    "lawsuit",
    "restriction",
    "access restriction",
    "regulation",
    "policy",
    "intervention",
    "criticism",
    "\uc564\uc2a4\ub85c\ud53d",
    "\ud074\ub85c\ub4dc",
    "\ubc31\uc545\uad00",
    "\uad6d\ubc29\ubd80",
    "\uad6d\ubc29\uc7a5\uad00",
    "\uc0c1\uc6d0",
    "\uccad\ubb38\ud68c",
    "\uc815\ubd80",
    "\uc5f0\ubc29",
    "\uad6d\uac00 \uc548\ubcf4",
    "\uc548\ubcf4",
    "\uc18c\uc1a1",
    "\uc81c\ub3d9",
    "\uc81c\ud55c",
    "\uaddc\uc81c",
    "\uac1c\uc785",
    "\ube44\ud310",
)

AI_POLICY_CONFLICT_CONTEXT_NEEDLES = (
    "ai",
    "artificial intelligence",
    "model",
    "models",
    "llm",
    "\uc778\uacf5\uc9c0\ub2a5",
    "\ubaa8\ub378",
)

FOOD_TREND_NEEDLES = (
    "food",
    "foods",
    "dessert",
    "desserts",
    "beverage",
    "drink",
    "drinks",
    "cafe",
    "bakery",
    "retail",
    "supermarket",
    "convenience store",
    "mart",
    "grocery",
    "product",
    "products",
    "snack",
    "ice cream",
    "cake",
    "latte",
    "ube",
    "purple yam",
    "matcha",
    "export",
    "식품",
    "음식",
    "디저트",
    "음료",
    "카페",
    "베이커리",
    "편의점",
    "대형마트",
    "마트",
    "소비자",
    "트렌드",
    "제품",
    "출시",
    "수출",
    "우베",
    "말차",
    "자색",
    "참마",
    "보라색",
    "아이스크림",
    "케이크",
    "라떼",
)

EV_BATTERY_NEEDLES = (
    "ev",
    "electric vehicle",
    "electric vehicles",
    "battery",
    "batteries",
    "lfp",
    "ncm",
    "solid-state",
    "solid state",
    "energy density",
    "driving range",
    "range anxiety",
    "fire risk",
    "charging",
    "k-battery",
    "전기차",
    "배터리",
    "lfp",
    "ncm",
    "전고체",
    "에너지 밀도",
    "주행거리",
    "주행 거리",
    "화재 위험",
    "충전",
    "k-배터리",
    "한국형 lfp",
    "기술 주권",
)

EV_BATTERY_STRONG_NEEDLES = (
    "lfp",
    "ncm",
    "solid-state",
    "solid state",
    "energy density",
    "k-battery",
    "전고체",
    "에너지 밀도",
    "k-배터리",
    "한국형 lfp",
)

_FOOD_TREND_STRONG_NEEDLES = (
    "ube",
    "purple yam",
    "matcha",
    "우베",
    "말차",
    "자색",
    "참마",
    "보라색",
)


def project_domain_haystack(project: ProjectRecord, text: str, *, note_limit: int = 4) -> str:
    haystacks = [text.lower()]
    title = project["title"].strip().lower()
    if title:
        haystacks.append(title)
    compiled = (project["compiled_script"] or project["script"]).strip().lower()
    if compiled:
        haystacks.append(compiled[:1200])
    for note in project["source_draft_fact_notes"][:note_limit]:
        note_text = note.get("note", "").strip().lower()
        if note_text:
            haystacks.append(note_text)
    source = project["source_draft_sources"][0] if project["source_draft_sources"] else None
    if source is not None:
        haystacks.append(str(source.get("title", "")).lower())
        haystacks.append(str(source.get("excerpt", "")).lower())
    return " ".join(haystacks)


def is_tech_domain(project: ProjectRecord, text: str) -> bool:
    joined = project_domain_haystack(project, text)
    if any(needle in joined for needle in TECH_NEEDLES):
        return True
    has_broad_term = any(needle in joined for needle in BROAD_TECH_NEEDLES)
    has_tech_context = any(needle in joined for needle in TECH_CONTEXT_NEEDLES)
    return has_broad_term and has_tech_context


def is_news_explainer_domain(project: ProjectRecord, text: str) -> bool:
    joined = project_domain_haystack(project, text)
    if any(needle in joined for needle in NEWS_EXPLAINER_STRONG_NEEDLES):
        return True
    hits = [needle for needle in NEWS_EXPLAINER_NEEDLES if needle in joined]
    weak_only = {"news", "article", "\ub274\uc2a4", "\uae30\uc0ac"}
    strong_hits = [needle for needle in hits if needle not in weak_only]
    return len(strong_hits) >= 2


def is_ai_policy_conflict_domain(project: ProjectRecord, text: str) -> bool:
    joined = project_domain_haystack(project, text)
    policy_hits = sum(1 for needle in AI_POLICY_CONFLICT_NEEDLES if needle in joined)
    if policy_hits >= 2:
        return True
    has_policy = policy_hits >= 1
    has_ai_context = any(needle in joined for needle in AI_POLICY_CONFLICT_CONTEXT_NEEDLES)
    return has_policy and has_ai_context


def is_food_trend_domain(project: ProjectRecord, text: str) -> bool:
    joined = project_domain_haystack(project, text)
    hits = [needle for needle in FOOD_TREND_NEEDLES if needle in joined]
    if any(needle in joined for needle in _FOOD_TREND_STRONG_NEEDLES):
        return len(hits) >= 1
    return len(hits) >= 2


def is_ev_battery_domain(project: ProjectRecord, text: str) -> bool:
    joined = project_domain_haystack(project, text)
    hits = [needle for needle in EV_BATTERY_NEEDLES if needle in joined]
    if any(needle in joined for needle in EV_BATTERY_STRONG_NEEDLES):
        return len(hits) >= 1
    has_ev = any(needle in joined for needle in ("ev", "electric vehicle", "전기차"))
    has_battery = any(needle in joined for needle in ("battery", "batteries", "배터리"))
    return has_ev and has_battery


def is_agriculture_environment_domain(project: ProjectRecord, text: str) -> bool:
    joined = project_domain_haystack(project, text)
    if any(needle in joined for needle in AGRICULTURE_ENVIRONMENT_NEEDLES):
        return True
    has_broad_research = any(needle in joined for needle in BROAD_TECH_NEEDLES)
    has_agriculture_context = any(
        needle in joined
        for needle in (
            "soil",
            "crop",
            "leaf",
            "leaves",
            "mulch",
            "farm",
            "field",
            "plant",
        )
    )
    return has_broad_research and has_agriculture_context


def is_science_materials_domain(project: ProjectRecord, text: str) -> bool:
    joined = project_domain_haystack(project, text)
    if any(needle in joined for needle in SCIENCE_MATERIALS_NEEDLES):
        return True
    has_broad_research = any(needle in joined for needle in BROAD_TECH_NEEDLES)
    has_materials_context = any(
        needle in joined
        for needle in (
            "polymer",
            "cellulose",
            "film",
            "material",
            "composite",
            "decomposition",
        )
    )
    return has_broad_research and has_materials_context
