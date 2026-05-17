from ..types import VisualBrief, VisualBriefMode, VisualSceneMode

TECH_NEEDLES = (
    "ai",
    "artificial intelligence",
    "llm",
    "gpu",
    "tpu",
    "chip",
    "chips",
    "semiconductor",
    "model",
    "models",
    "training",
    "inference",
    "datacenter",
    "data center",
    "compute",
    "server",
    "agent",
    "agents",
    "research",
    "obscura",
    "browser",
    "브라우저",
    "headless",
    "javascript",
    "자바스크립트",
    "v8",
    "cdp",
    "fingerprint",
    "핑거프린트",
    "automation",
    "자동화",
    "scraping",
    "크롤링",
    "data extraction",
    "데이터 추출",
    "github",
    "open source",
    "오픈소스",
    "terminal",
    "console",
)

SYMBOLIC_NEEDLES = (
    "hope",
    "courage",
    "relationship",
    "마음",
    "용기",
    "희망",
    "불안",
    "관계",
)

LITERAL_NEEDLES = (
    "giant",
    "stone",
    "prayer",
    "phone",
    "clock",
    "money",
    "wave",
    "book",
    "browser",
    "브라우저",
    "javascript",
    "v8",
    "cdp",
)

TECH_AVOID = [
    "running fast",
    "under heavy rain",
    "standing in front of a large door",
    "inside a simple room",
    "holding one large clear symbol that represents the sentence keyword",
]

EV_BATTERY_AVOID = [
    "unrelated human portrait",
    "desert scene",
    "aircraft",
    "warrior",
    "medieval scene",
    "fantasy creature",
    "random road scene",
    "animal",
    "empty landscape",
]

EDITORIAL_SCENE_NEEDLES = (
    "bank",
    "banks",
    "financial",
    "finance",
    "investment",
    "investor",
    "committee",
    "analyst",
    "institution",
    "market",
    "portfolio",
    "volatility",
    "meeting",
    "desk",
    "board",
    "strategy",
    "finance desk",
    "금융",
    "은행",
    "투자",
    "시장",
    "기관",
    "위원회",
    "전략",
)

SYMBOLIC_CONCEPT_NEEDLES = (
    "barrier",
    "gap",
    "mismatch",
    "limit",
    "limitation",
    "slow",
    "delay",
    "pause",
    "challenge",
    "bottleneck",
    "obstacle",
    "한계",
    "벽",
    "격차",
    "과제",
    "느리",
    "지연",
)

DATA_DIAGRAM_NEEDLES = (
    "probability",
    "risk",
    "variable",
    "compare",
    "comparison",
    "allocation",
    "metric",
    "signal",
    "trend",
    "distribution",
    "portfolio",
    "volatility",
    "확률",
    "위험",
    "변수",
    "비교",
    "분배",
    "지표",
    "신호",
)

SIMPLE_EXPLAINER_NEEDLES = (
    "future",
    "expectation",
    "promise",
    "growth driver",
    "concept",
    "future driver",
    "전망",
    "기대",
    "미래",
    "동력",
    "개념",
)


def _detect_domain(text: str, visual_tokens: list[str], domain: str) -> str:
    if domain != "generic":
        return domain
    lowered = text.lower()
    joined = " ".join(visual_tokens).lower()
    if any(needle in lowered or needle in joined for needle in TECH_NEEDLES):
        return "tech"
    return "generic"


def _brief_mode(text: str, visual_tokens: list[str], domain: str) -> VisualBriefMode:
    if domain in {"tech", "ev_battery"}:
        return "keyword_image"
    lowered = text.lower()
    if any(needle in lowered for needle in LITERAL_NEEDLES):
        return "literal_scene"
    if any(needle in lowered for needle in SYMBOLIC_NEEDLES):
        return "symbolic_metaphor"
    if visual_tokens:
        return "keyword_image"
    return "symbolic_metaphor"


def _primary_prop(visual_tokens: list[str], domain: str) -> str:
    if visual_tokens:
        return visual_tokens[0]
    if domain == "ev_battery":
        return "electric vehicle beside a large battery cell"
    if domain == "tech":
        return "browser window with terminal panel and automation cursor"
    if domain == "food_trend":
        return "food product display tied to the sentence"
    return "concrete visual subject tied to the sentence"


def _action_from_tokens(text: str, visual_tokens: list[str], domain: str) -> str:
    joined = " ".join(visual_tokens).lower()
    lowered = text.lower()
    if domain == "tech":
        return "presenting the primary prop like a clear explainer diagram"
    if domain == "ev_battery":
        return "presenting the battery concept as a clean technology explainer"
    if "running" in joined or "run" in lowered:
        return "moving quickly toward the goal"
    if "kneeling" in joined or "prayer" in lowered:
        return "kneeling in prayer"
    if "holding" in joined or "book" in joined or "phone" in joined:
        return "holding the primary prop clearly"
    if "reaching" in joined:
        return "reaching toward the primary prop"
    if "standing up" in joined or "recover" in lowered:
        return "standing up again"
    if "studying" in joined or "study" in lowered:
        return "studying with focus"
    if "single everyday object" in joined or "concrete visual subject" in joined:
        return "arranged as a simple visual metaphor"
    return "showing one clear readable action"


def _emotion_from_text(text: str, visual_tokens: list[str], domain: str) -> str:
    lowered = text.lower()
    joined = " ".join(visual_tokens).lower()
    if domain == "tech":
        if any(needle in lowered for needle in ("security", "warning", "risk", "privacy", "보안", "위험")):
            return "focused and cautious"
        return "calm and analytical"
    if domain == "ev_battery":
        return "calm and analytical"
    if any(needle in lowered for needle in ("fear", "afraid", "불안", "두려")) or "anxious" in joined:
        return "anxious"
    if any(needle in lowered for needle in ("hope", "용기", "희망")) or "hopeful" in joined:
        return "hopeful"
    if any(needle in lowered for needle in ("joy", "smile", "기쁨")) or "joy" in joined:
        return "joyful"
    if any(needle in lowered for needle in ("decision", "choose", "결단", "선택")):
        return "hesitating but decisive"
    return "calm and focused"


def _scene_from_template(template_key: str, domain: str) -> str:
    if domain == "tech":
        return "clean software workspace"
    if domain == "ev_battery":
        return "clean electric vehicle battery explainer setting"
    if domain == "food_trend":
        return "clear food trend editorial setting"
    if template_key == "default":
        return "grounded editorial environment"
    return template_key.replace("_", " ")


def _visual_mode(text: str, visual_tokens: list[str], domain: str, template_key: str) -> VisualSceneMode:
    lowered = f"{text} {' '.join(visual_tokens)}".lower()
    if domain in {"news_explainer", "ai_policy_conflict"}:
        return "simple_explainer"
    if domain == "ev_battery":
        return "data_diagram" if any(needle in lowered for needle in ("compare", "comparison", "비교", "가격", "cost", "density", "밀도")) else "editorial_scene"
    if domain == "tech":
        return "editorial_scene"
    if template_key == "default" and any(needle in lowered for needle in DATA_DIAGRAM_NEEDLES):
        return "data_diagram"
    if any(needle in lowered for needle in SYMBOLIC_CONCEPT_NEEDLES):
        return "symbolic_concept"
    if any(needle in lowered for needle in SIMPLE_EXPLAINER_NEEDLES):
        return "simple_explainer"
    if any(needle in lowered for needle in EDITORIAL_SCENE_NEEDLES):
        return "editorial_scene"
    if visual_tokens:
        return "symbolic_concept"
    return "editorial_scene"


def _main_subject_for_visual_mode(visual_mode: VisualSceneMode, domain: str) -> str:
    if domain == "tech":
        return "technology interface scene"
    if domain == "ev_battery":
        return "electric vehicle battery explainer scene"
    if visual_mode == "editorial_scene":
        return "grounded editorial scene with one dominant subject"
    if visual_mode == "symbolic_concept":
        return "editorial symbolic concept scene"
    if visual_mode == "data_diagram":
        return "clean comparative data explainer composition"
    return "simple centered explainer icon composition"


def _scene_for_visual_mode(visual_mode: VisualSceneMode, fallback_scene: str) -> str:
    if visual_mode == "editorial_scene":
        return fallback_scene
    if visual_mode == "symbolic_concept":
        return "clean editorial setting with one grounded symbolic anchor"
    if visual_mode == "data_diagram":
        return "plain warm background with large comparison elements"
    return "plain warm background with generous empty space"


def _allow_objects_for_visual_mode(visual_mode: VisualSceneMode) -> list[str]:
    if visual_mode in {"simple_explainer", "data_diagram"}:
        return ["icon", "arrows", "comparison bars", "probability lines"]
    if visual_mode == "symbolic_concept":
        return ["symbolic object", "arrows", "path marker"]
    return []


def build_visual_brief(
    *,
    text: str,
    visual_tokens: list[str],
    template_key: str,
    domain: str = "generic",
) -> VisualBrief:
    resolved_domain = _detect_domain(text, visual_tokens, domain)
    visual_mode = _visual_mode(text, visual_tokens, resolved_domain, template_key)
    primary_prop = _primary_prop(visual_tokens, resolved_domain)
    secondary_prop = visual_tokens[1] if len(visual_tokens) > 1 else ""
    must_show = [primary_prop]
    if secondary_prop:
        must_show.append(secondary_prop)
    mode = _brief_mode(text, visual_tokens, resolved_domain)
    avoid = ["text", "logo", "crowd", "multiple characters", "tiny subject", "clutter"]
    if resolved_domain == "tech":
        avoid.extend(TECH_AVOID)
    if resolved_domain == "ev_battery":
        avoid.extend(EV_BATTERY_AVOID)
    if visual_mode in {"simple_explainer", "data_diagram"}:
        avoid.extend(["office desk", "monitor wall", "laptop-only scene", "conference room"])
    elif visual_mode == "symbolic_concept":
        avoid.extend(["monitor wall", "dashboard-only scene", "generic office cubicle"])
    return {
        "mode": mode,
        "main_subject": _main_subject_for_visual_mode(visual_mode, resolved_domain),
        "action": _action_from_tokens(text, visual_tokens, resolved_domain),
        "primary_prop": primary_prop,
        "secondary_prop": secondary_prop,
        "scene": _scene_for_visual_mode(visual_mode, _scene_from_template(template_key, resolved_domain)),
        "emotion": _emotion_from_text(text, visual_tokens, resolved_domain),
        "must_show": must_show,
        "avoid": avoid,
        "rationale": f"template={template_key}; domain={resolved_domain}; tokens={', '.join(visual_tokens) if visual_tokens else 'fallback'}",
        "domain": resolved_domain,
        "visual_mode": visual_mode,
        "allow_objects": _allow_objects_for_visual_mode(visual_mode),
    }
